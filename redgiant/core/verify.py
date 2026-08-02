"""Verifica deterministica (piano F1.6, D10): il trust boundary del sistema.

Tutto a monte PROPONE; questo modulo CONSTATA. Tutti i check girano sempre
(il quadro completo serve alla diagnosi), nell'ordine:
  1. report.status == 'done' (un blocked non passa mai di qui)
  2. evidenze non vuote
  3. ogni expected_output esiste nello scope
  4. ogni voce di verification nota come cmd_id -> run_tests exit 0
  5. voci di verification sconosciute -> FAIL ("unknown check"): una verifica
     non eseguibile e' una verifica fallita, non saltata. Silenzio != successo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from redgiant.roles.worker import FinishReport
from redgiant.state.models import SubtaskSpec
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    ok: bool
    detail: str


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["pass", "fail"]
    checks: list[CheckResult]


def verify_subtask(spec: SubtaskSpec, report: FinishReport, scope: Scope,
                   router: ToolRouter, task_id: str) -> Verdict:
    checks: list[CheckResult] = []

    checks.append(CheckResult(
        name="worker_done", ok=report.status == "done",
        detail=f"worker status={report.status}"))

    checks.append(CheckResult(
        name="evidence_present", ok=bool(report.evidence),
        detail=f"{len(report.evidence)} evidence items"))

    for out in spec.expected_outputs:
        try:
            exists = scope.check_read(out).exists()
            detail = out
        except Exception as e:
            exists, detail = False, f"{out}: {e}"
        checks.append(CheckResult(name=f"output:{out}", ok=exists, detail=detail))

    known_cmds = {name for name, s in router.catalog.items()}
    for check in spec.verification:
        if _is_cmd_id(router, check):
            res = router.dispatch(task_id, spec.id, "run_tests", {"cmd_id": check})
            checks.append(CheckResult(
                name=f"test:{check}", ok=res.ok,
                detail=res.data.get("output_tail", res.error or "")[-400:]))
        else:
            checks.append(CheckResult(
                name=f"unknown:{check}", ok=False,
                detail=f"unknown check '{check}' (known tools: {sorted(known_cmds)}) - "
                       f"a non-executable verification is a failed verification"))

    # F2.5 (retest D3): gli oracoli battono le dichiarazioni IN ENTRAMBE le
    # direzioni. Se TUTTI i check oggettivi passano (output esistenti + test verdi,
    # con almeno un test eseguito), il lavoro e' fatto anche se il worker si
    # crede blocked: i check soggettivi (worker_done, evidence) diventano warning.
    subjective = {"worker_done", "evidence_present"}
    objective = [c for c in checks if c.name not in subjective]
    ran_tests = any(c.name.startswith("test:") for c in objective)
    if objective and ran_tests and all(c.ok for c in objective):
        return Verdict(verdict="pass", checks=checks)
    verdict: Literal["pass", "fail"] = "pass" if all(c.ok for c in checks) else "fail"
    return Verdict(verdict=verdict, checks=checks)


def _is_cmd_id(router: ToolRouter, check: str) -> bool:
    """Un check e' eseguibile se run_tests lo riconosce come cmd_id registrato."""
    spec = router.catalog.get("run_tests")
    if spec is None:
        return False
    # il dict test_commands e' chiuso nella partial del handler (router.default_catalog)
    test_commands = spec.handler.args[1] if hasattr(spec.handler, "args") else {}
    return check in test_commands
