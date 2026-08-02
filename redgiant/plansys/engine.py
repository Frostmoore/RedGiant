"""PlanSysEngine (PS5.3): il driver della vertical slice §PS-A5.

Eredita dall'Orchestrator tutto cio' che F1/F2 hanno gia' collaudato (ripresa
degli orfani, esecuzione sottofase con resume in-place, budget come checkpoint
di consenso, finalize onesto) e vi monta sopra S/M/J + i gate: entry, micro,
retry, synthesis, coverage. In v1 NIENTE replanning: una fase che fallisce e'
un fallimento esplicito con post-mortem (il rilancio guidato F2.4-bis resta).
"""

from __future__ import annotations

import json
import os

from pydantic import ValidationError

from redgiant.core.budget import BudgetTracker
from redgiant.core.orchestrator import Orchestrator, TaskLog
from redgiant.core.verify import CheckResult, verify_subtask
from redgiant.llm.client import LlmError, LlmTruncated
from redgiant.plansys.artifacts import (GateReport, MacroPhase, MacroPlan,
                                        MicroPhase, PhaseBlueprint,
                                        VerificationBlueprint)
from redgiant.plansys.compiler import (CompileFailed, NeedsDecision,
                                       PhaseAlreadySatisfied, PhaseCompiler)
from redgiant.plansys.gates import (_module_names, _run_probe,
                                    failure_signature, micro_gate, retry_gate)
from redgiant.plansys.ledger import build_ledger, render_ledger
from redgiant.plansys.render import render_macro_plan, write_plan_doc
from redgiant.plansys.roles import MacroRejected, SeniorPlanner
from redgiant.roles.base import RoleContext
from redgiant.roles.worker import Worker
from redgiant.state.models import SubtaskSpec, TaskState
from redgiant.tools.base import Scope


def work_order(micro: MicroPhase, vbp: VerificationBlueprint,
               importable: list[str] | None = None) -> SubtaskSpec:
    """PS5.1 — MicroPhase+prove -> SubtaskSpec per il Worker ESISTENTE.
    verification = SOLO le prove della micro (comandi proof:*, registrati dal
    control plane): perimetro=verifica by design, mai la suite intera."""
    obs = [o for o in vbp.obligations if o.micro_id == micro.id]
    objective = (f"{micro.work.goal}\nBOUNDARY: {micro.work.boundary}")
    if micro.work.signatures:
        objective += "\nSIGNATURES (exact): " + "; ".join(micro.work.signatures)
    if obs:
        objective += ("\nPROOF: your work is done when these already-written "
                      "tests pass: " + "; ".join(
                          f"{o.test_file}::{o.test_name}" for o in obs)
                      + ". Run them with run_tests using EXACTLY these cmd_id "
                        "values: " + ", ".join(f"proof:{o.id}" for o in obs)
                      + ". The tests are ALREADY WRITTEN and immutable: never "
                        "create or edit test files. You can write ONLY: "
                      + ", ".join(micro.work.files_owned))
    # PS5.5 tentativo 2: J importava 'storage' PRIMA che storage.py esistesse
    # (ModuleNotFoundError al proof). I moduli locali importabili sono un fatto
    # del control plane, non una deduzione del 2B.
    if importable:
        objective += ("\nIMPORTS: the ONLY local modules that exist are: "
                      + ", ".join(importable) + ". Never import any other "
                      "local module (it does not exist yet); stdlib is fine.")
    return SubtaskSpec(
        id=micro.id, phase_id=micro.id.split(".")[0], title=micro.title,
        objective=objective, inputs=micro.work.inputs,
        # pilota PS5: M2 mette negli outputs anche prose ("C1 covered") che
        # l'oracolo di esistenza-file non puo' verificare — gli expected_outputs
        # del contratto sono i files_owned: path REALI garantiti dal validatore
        tools=[], expected_outputs=micro.work.files_owned,
        completion_criteria=[o.behavior for o in obs],
        verification=[f"proof:{o.id}" for o in obs])


class PlanSysEngine(Orchestrator):
    """Il modello propone (S, M, J); QUESTO codice decide (PS-D1)."""

    # ── ingresso ─────────────────────────────────────────────────────────────

    def run_task(self, task_id: str) -> TaskState:
        state = self.store.load_task(task_id)
        log = TaskLog(self.cfg.paths.tasks_dir, task_id)
        tracker = BudgetTracker(self.store, state.budget, task_id)
        if state.status == "queued":
            self.store.set_task_status(task_id, "running", actor="plansys")
        self._reclaim_orphans(task_id, log)

        worker = Worker(self.llm, self.assembler, self.router)
        compiler = PhaseCompiler(self.cfg, self.store, self.llm, self.assembler,
                                 self.router, self.router.scope)

        plan = self._load_or_create_macro_plan(task_id, log)
        if isinstance(plan, TaskState):
            return plan

        autodecided: dict[str, int] = {}
        while True:
            state = self.store.load_task(task_id)
            if state.status in ("blocked", "cancelled"):
                log.line("plansys", f"stop: task {state.status}")
                return state

            phase = self._eligible_macro_phase(task_id, plan)
            if phase is None:
                return self._close_plan(task_id, plan, log)

            entry = self._phase_entry_gate(task_id, plan, phase)
            self._log_gate(task_id, entry)
            if entry.ok:
                log.line("gate", f"{phase.id} entry gate: criteri gia' provati "
                                 f"-> fase chiusa a costo zero")
                continue

            try:
                bp, vbp, _bundle = compiler.compile_phase(task_id, plan, phase,
                                                          log)
            except PhaseAlreadySatisfied:
                continue  # gate phase_entry gia' loggato dal compiler
            except NeedsDecision as e:
                payload = json.dumps({"question": e.choice.question,
                                      "options": e.choice.options,
                                      "recommended": e.choice.recommended,
                                      "reason": e.choice.reason})
                # PS-D8, policy per run non presidiate (eval): auto-decisione
                # sulla RACCOMANDATA, registrata come decisione — mai silenziosa
                if (os.environ.get("RG_PLANSYS_AUTODECIDE") == "recommended"
                        and autodecided.get(phase.id, 0) < 2):
                    autodecided[phase.id] = autodecided.get(phase.id, 0) + 1
                    aid = self.store.add_approval(task_id, kind="clarification",
                                                  payload=payload)
                    self.store.answer_approval(
                        aid, f"{e.choice.recommended} ({e.choice.reason})")
                    self.store.add_decision(
                        task_id, actor="policy:autodecide",
                        decision=e.choice.recommended,
                        reason=e.choice.question[:180])
                    log.line("compiler", f"{phase.id} choice point auto-deciso "
                                         f"(policy eval): {e.choice.recommended}")
                    continue
                self.store.add_approval(task_id, kind="clarification",
                                        payload=payload)
                self.store.set_task_status(
                    task_id, "blocked", actor="phase_compiler",
                    error=f"decision required on {e.phase_id}: "
                          f"{e.choice.question}"[:400])
                log.line("compiler", f"{phase.id} choice point -> blocked")
                return self.store.load_task(task_id)
            except (CompileFailed, LlmError, LlmTruncated,
                    ValidationError) as e:
                self.store.set_task_status(
                    task_id, "failed", actor="phase_compiler",
                    error=f"compile of {phase.id} failed: {e}"[:400])
                log.line("compiler", f"{phase.id} FAILED: {e}"[:200])
                return self.store.load_task(task_id)

            self._register_proof_commands(vbp)
            root = self.router.scope.root
            avail: set[str] = set()
            for p in root.rglob("*.py"):
                rel = p.relative_to(root)
                if not p.is_file() or "tasks" in rel.parts:
                    continue
                avail.add(p.stem)
                if len(rel.parts) > 1:  # package: 'commands/__init__.py'
                    avail.add(rel.parts[0])
            for micro in bp.micro:
                avail |= _module_names(micro.work.files_owned)
                self.store.upsert_subtask(
                    task_id, work_order(micro, vbp, sorted(avail)),
                    actor="plansys")

            for micro in bp.micro:
                out = self._run_micro(task_id, micro, vbp, worker, tracker, log)
                if out is not None:
                    return out
                tracker = BudgetTracker(self.store,
                                        self.store.load_task(task_id).budget,
                                        task_id)
                write_plan_doc(self.cfg.paths.tasks_dir, task_id, "ledger",
                               render_ledger(build_ledger(
                                   self.store, self.router.scope, task_id)))

            syn = self._phase_synthesis_gate(task_id, phase, vbp, plan)
            self._log_gate(task_id, syn)
            if not syn.ok:
                ko = [c.name for c in syn.checks if not c.ok]
                self.store.set_task_status(
                    task_id, "failed", actor="plansys",
                    error=f"phase {phase.id} synthesis gate failed: {ko} "
                          f"(no replanning in v1)"[:400])
                log.line("gate", f"{phase.id} synthesis KO: {ko}")
                return self.store.load_task(task_id)
            log.line("gate", f"{phase.id} synthesis verde: fase completata")

    # ── S ────────────────────────────────────────────────────────────────────

    def _load_or_create_macro_plan(self, task_id: str,
                                   log: TaskLog) -> MacroPlan | TaskState:
        try:
            row = self.store.load_ps_artifact(task_id, "macro_plan")
            return MacroPlan.model_validate_json(row["json"])
        except KeyError:
            pass
        state = self.store.load_task(task_id)
        volatile = (f"Repository files:\n{self._repo_listing()}\n"
                    f"Known test command ids: "
                    f"{sorted(self._test_cmd_ids()) or ['none yet']}"
                    f"{self._test_excerpts()}")
        senior = SeniorPlanner(self.llm, self.assembler, self.router)
        try:
            plan = senior.run(RoleContext(task=state, subtask=None,
                                          volatile=volatile))
        except (MacroRejected, LlmError, LlmTruncated) as e:
            self.store.set_task_status(task_id, "failed", actor="senior",
                                       error=f"senior planner failed: {e}"[:400])
            log.line("senior", f"FAILED: {e}"[:200])
            return self.store.load_task(task_id)
        self.store.save_ps_artifact(task_id, kind="macro_plan", ref="",
                                    payload_json=plan.model_dump_json(),
                                    actor="senior")
        write_plan_doc(self.cfg.paths.tasks_dir, task_id, "macro_plan",
                       render_macro_plan(plan))
        log.line("senior", f"macro plan: {len(plan.phases)} fasi, "
                           f"{len(plan.criteria)} criteri")
        return plan

    # ── fasi ─────────────────────────────────────────────────────────────────

    def _done_phases(self, task_id: str) -> set[str]:
        return {g["target"] for g in self.store.ps_gate_history(task_id)
                if g["ok"] and g["gate"] in ("phase_synthesis", "phase_entry")}

    def _eligible_macro_phase(self, task_id: str,
                              plan: MacroPlan) -> MacroPhase | None:
        done = self._done_phases(task_id)
        for p in plan.phases:
            if p.id in done:
                continue
            if all(d in done for d in p.depends_on):
                return p
        return None

    def _proof_pairs(self, task_id: str) -> list[tuple[PhaseBlueprint,
                                                       VerificationBlueprint]]:
        pairs = []
        bps = {r["ref"]: r for r in self.store.list_ps_artifacts(
            task_id, "phase_blueprint")}
        for ref, row in bps.items():
            try:
                vrow = self.store.load_ps_artifact(task_id,
                                                   "verification_blueprint", ref)
            except KeyError:
                continue
            pairs.append((PhaseBlueprint.model_validate_json(row["json"]),
                          VerificationBlueprint.model_validate_json(vrow["json"])))
        return pairs

    def _probe_criteria(self, task_id: str, cids: list[str],
                        only_phases: set[str] | None) -> list[CheckResult]:
        """Un criterio e' PROVATO se >=1 obbligo di una micro che lo dichiara
        e' verde ADESSO (ri-eseguito, mai creduto)."""
        checks: list[CheckResult] = []
        pairs = self._proof_pairs(task_id)
        for cid in cids:
            candidates = []
            for bp, vbp in pairs:
                if only_phases is not None and bp.phase_id not in only_phases:
                    continue
                proving = {m.id for m in bp.micro if cid in m.proves}
                candidates += [o for o in vbp.obligations
                               if o.micro_id in proving]
            if not candidates:
                checks.append(CheckResult(name=f"criterion:{cid}", ok=False,
                                          detail="no obligation proves it"))
                continue
            green = None
            for o in candidates:
                code, _ = _run_probe(self.router.scope,
                                     ["pytest", "-q",
                                      f"{o.test_file}::{o.test_name}"])
                if code == 0:
                    green = o.id
                    break
            checks.append(CheckResult(
                name=f"criterion:{cid}", ok=green is not None,
                detail=f"proved by {green}" if green
                else f"{len(candidates)} obligations, none green"))
        return checks

    def _phase_entry_gate(self, task_id: str, plan: MacroPlan,
                          phase: MacroPhase) -> GateReport:
        from redgiant.plansys import ablated
        if ablated("entry"):
            return GateReport(gate="phase_entry", target=phase.id, ok=False,
                              checks=[CheckResult(name="ABLATED", ok=False,
                                                  detail="entry gate off (A/B)")])
        done = self._done_phases(task_id)
        checks = (self._probe_criteria(task_id, phase.covers, done)
                  if done else [CheckResult(name="no_prior_phases", ok=False,
                                            detail="nothing completed yet")])
        return GateReport(gate="phase_entry", target=phase.id,
                          ok=all(c.ok for c in checks), checks=checks)

    def _phase_synthesis_gate(self, task_id: str, phase: MacroPhase,
                              vbp: VerificationBlueprint,
                              plan: MacroPlan | None = None) -> GateReport:
        """A/B PS6 (T007/T010/T040): la suite PIENA a chiusura di fase incontra
        i test delle fasi FUTURE, rossi per definizione — morte inevitabile a
        P1 sui task multi-fase con suite fornita. La sintesi e' SCOPED: proof
        di questa fase + proof delle fasi gia' chiuse; i synthesis_cmds interi
        girano solo quando la copertura del piano e' completa (ultima fase)."""
        checks: list[CheckResult] = []
        final = True
        if plan is not None:
            done = self._done_phases(task_id)
            covered = set(phase.covers)
            covered |= {cid for p in plan.phases if p.id in done
                        for cid in p.covers}
            final = covered >= {c.id for c in plan.criteria}
        if final:
            for cmd in vbp.synthesis_cmds:
                res = self.router.dispatch(task_id, f"{phase.id}.synthesis",
                                           "run_tests", {"cmd_id": cmd})
                checks.append(CheckResult(
                    name=f"synthesis:{cmd}", ok=res.ok,
                    detail=str(res.data.get("exit_code", res.error))))
        for o in vbp.obligations:
            code, _ = _run_probe(self.router.scope,
                                 ["pytest", "-q",
                                  f"{o.test_file}::{o.test_name}"])
            checks.append(CheckResult(name=f"obligation:{o.id}", ok=code == 0,
                                      detail=f"exit={code}"))
        if plan is not None and not final:
            done = self._done_phases(task_id)
            for bp_prev, vbp_prev in self._proof_pairs(task_id):
                if bp_prev.phase_id == phase.id or bp_prev.phase_id not in done:
                    continue
                for o in vbp_prev.obligations:
                    code, _ = _run_probe(self.router.scope,
                                         ["pytest", "-q",
                                          f"{o.test_file}::{o.test_name}"])
                    checks.append(CheckResult(
                        name=f"regression:{o.id}", ok=code == 0,
                        detail=f"exit={code}"))
        return GateReport(gate="phase_synthesis", target=phase.id,
                          ok=all(c.ok for c in checks), checks=checks)

    def _close_plan(self, task_id: str, plan: MacroPlan,
                    log: TaskLog) -> TaskState:
        cov = GateReport(gate="plan_coverage", target="plan",
                         ok=True,
                         checks=self._probe_criteria(
                             task_id, [c.id for c in plan.criteria], None))
        cov = GateReport(gate="plan_coverage", target="plan",
                         ok=all(c.ok for c in cov.checks), checks=cov.checks)
        self._log_gate(task_id, cov)
        if not cov.ok:
            ko = [c.name for c in cov.checks if not c.ok]
            self.store.set_task_status(
                task_id, "partial", actor="plansys",
                error=f"plan coverage gate failed: {ko}"[:400])
            log.line("gate", f"coverage KO: {ko}")
            return self.store.load_task(task_id)
        log.line("gate", "plan coverage verde: tutti i criteri provati")
        return self._finalize(self.store.load_task(task_id))

    # ── micro (J) ────────────────────────────────────────────────────────────

    def _register_proof_commands(self, vbp: VerificationBlueprint) -> None:
        """I comandi proof:* (test singolo) entrano nel catalogo run_tests:
        e' cosi' che verify_subtask esegue ESATTAMENTE le prove della micro."""
        spec = self.router.catalog.get("run_tests")
        if spec is None or not hasattr(spec.handler, "args"):
            return
        cmds: dict = spec.handler.args[1]
        for o in vbp.obligations:
            cmds[f"proof:{o.id}"] = ["pytest", "-q",
                                     f"{o.test_file}::{o.test_name}"]

    def _run_micro(self, task_id: str, micro: MicroPhase,
                   vbp: VerificationBlueprint, worker: Worker,
                   tracker: BudgetTracker, log: TaskLog) -> TaskState | None:
        """None = micro chiusa, si prosegue; TaskState = stato terminale/bloccato.

        Pilota PS5 #18: PS-D4 ("le prove sono immutabili per J") era scritto
        nel piano ma non nel filesystem — J ha sovrascritto i test qualificati
        con una versione rotta. Qui J riceve uno Scope ristretto ai SOLI
        files_owned della micro: il perimetro del contratto applicato
        meccanicamente, non per fiducia."""
        from redgiant.tools.router import ToolRouter, default_catalog
        shared_cmds = {}
        spec_rt = self.router.catalog.get("run_tests")
        if spec_rt is not None and hasattr(spec_rt.handler, "args"):
            shared_cmds = spec_rt.handler.args[1]  # STESSO dict (proof:* inclusi)
        micro_scope = Scope(self.router.scope.root, list(micro.work.files_owned))
        micro_router = ToolRouter(
            default_catalog(self.cfg, micro_scope, shared_cmds),
            micro_scope, self.store)
        worker = Worker(self.llm, self.assembler, micro_router)
        outer_router = self.router
        prev_sig: str | None = None
        # batch20, strategia generale n.3: J vede VERBATIM il sorgente dei test
        # che lo giudicheranno (contract anchoring all'ultimo anello — i test
        # codificano formati esatti che J non puo' indovinare)
        proof_block = ""
        for tf in sorted({o.test_file for o in vbp.obligations
                          if o.micro_id == micro.id}):
            f = self.router.scope.root / tf
            if f.is_file():
                src = "\n".join(f.read_text(encoding="utf-8",
                                            errors="replace").splitlines()[:120])
                proof_block += f"\n[PROOF TEST SOURCE {tf}]\n{src}"

        failure_block = ""
        while True:
            state = self.store.load_task(task_id)
            spec, status, attempts = self.store.get_subtask(task_id, micro.id)
            if status in ("completed", "completed_with_warnings"):
                return None
            if proof_block or failure_block:
                spec = spec.model_copy(
                    update={"objective": spec.objective + proof_block
                            + failure_block})

            key = tracker.exceeded()
            if key is not None:
                outcome = self._handle_budget_exhaustion(task_id, key, tracker,
                                                         log)
                if outcome is not None:
                    return outcome
                tracker = BudgetTracker(self.store,
                                        self.store.load_task(task_id).budget,
                                        task_id)

            self.router = micro_router
            try:
                verdict = self._execute_subtask(state, spec, worker, log)
            finally:
                self.router = outer_router
            if verdict is None:  # approvazione umana in corso
                self.store.set_subtask_status(task_id, micro.id, "blocked",
                                              actor="plansys")
                return self.store.load_task(task_id)

            gate = micro_gate(verdict.verdict == "pass", micro.id,
                              verdict.checks)
            self._log_gate(task_id, gate)
            if gate.ok:
                warned = any(not c.ok for c in verdict.checks)
                self.store.set_subtask_status(
                    task_id, micro.id,
                    "completed_with_warnings" if warned else "completed",
                    actor="plansys", result={"verdict": verdict.model_dump()})
                log.line("gate", f"{micro.id} micro gate PASS")
                return None

            failed = [c.name for c in verdict.checks if not c.ok]
            new_sig = failure_signature(failed, verdict.checks[0].detail
                                        if verdict.checks else "")
            rg = retry_gate(prev_sig, new_sig)
            self._log_gate(task_id, rg)
            _, _, attempts = self.store.get_subtask(task_id, micro.id)
            if not rg.ok or attempts >= state.budget.max_retries_per_subtask:
                reason = ("photocopy retry blocked" if not rg.ok
                          else "retries exhausted")
                self.store.set_subtask_status(
                    task_id, micro.id, "failed", actor="plansys",
                    result={"verdict": verdict.model_dump()})
                self.store.set_task_status(
                    task_id, "failed", actor="plansys",
                    error=f"micro {micro.id} failed ({reason}): {failed} "
                          f"(no replanning in v1)"[:400])
                log.line("gate", f"{micro.id} {reason}: {failed}")
                return self.store.load_task(task_id)
            prev_sig = new_sig
            # batch n.6 (Sol): al retry J vede la CODA dell'output dei proof
            # falliti — l'assertion diff dice il formato esatto atteso, che J
            # non puo' dedurre dal solo nome del check
            tails = [f"- {c.name}:\n...{c.detail[-500:]}"
                     for c in verdict.checks if not c.ok and c.detail]
            failure_block = ("\n[PREVIOUS ATTEMPT FAILED] the proof tests "
                             "produced this output; fix YOUR code to satisfy "
                             "exactly what the test asserts:\n"
                             + "\n".join(tails[:3])) if tails else ""
            self.store.set_subtask_status(task_id, micro.id, "retry",
                                          actor="plansys",
                                          result={"verdict": verdict.model_dump()})
            log.line("gate", f"{micro.id} FAIL -> retry ({attempts + 1}) "
                             f"[firma nuova]")

    # ── ausiliari ────────────────────────────────────────────────────────────

    def _log_gate(self, task_id: str, report: GateReport) -> None:
        self.store.log_ps_gate(
            task_id, gate=report.gate, target=report.target, ok=report.ok,
            checks_json=json.dumps([c.model_dump() for c in report.checks]))
