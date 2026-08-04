"""Worker: ReAct a passo singolo vincolato (piano F1.5, D20).

A ogni step il modello emette UN oggetto WorkerStep (o una tool call o la
chiusura); il risultato viene appeso in coda a S6 e si genera lo step
successivo. La conversazione cresce SOLO in append: il prefisso resta intatto
e la KV cache riusa tutto (F0.5: 65 vs 7971 token).

Il finish del Worker NON chiude la sottofase: la chiude la verifica (D10).
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from redgiant.roles.base import Role, RoleContext
from redgiant.tools.base import ToolResult

_RESULT_MAX_CHARS = 6000  # ~400 righe compatte; il troncamento e' dichiarato nel blocco

# LAD.9 — il "finish fantasma": 31 tentativi su 78 (40%) dichiaravano done senza
# aver chiamato NESSUNO strumento di scrittura, e ripetevano l'errore anche col
# 'FAIL: answer.txt missing' del giudice riportato nel tentativo dopo (data.md
# §7.6.5). La regola 8 della card lo vieta dal F1: terza conferma che l'istruzione
# non produce obbedienza — quindi struttura.
_MUTATING_TOOLS: frozenset[str] = frozenset({"write_file", "edit_file", "write_patch"})
_MAX_FINISH_REFUSALS: int = 2  # tetto: non si sostituisce un loop degenere con un altro


def finish_gate_enabled() -> bool:
    """SPENTO DI DEFAULT (verdetto LAD.9, 2026-08-03) — `RG_FINISH_GATE=1` per
    accenderlo.

    Il gate intercetta una patologia REALE e misurata (40% dei tentativi
    dichiarava done senza scrivere) ma non ha prodotto alcun effetto:
    L5 18/20 vs 16/20 (p=0.66), L7 11/20 vs 11/20 (p=1.00), e costa il +15% di
    tempo. Il motivo, che e' il vero risultato: **il loop di retry pagava gia'
    per il finish fantasma** — la verifica esterna lo becca e il tentativo dopo
    di solito riesce. Il gate e' ridondante rispetto a un componente che
    esisteva gia'.

    Resta nel codice, spento, perche' il verdetto e' APERTO: sui task coding
    larghi un tentativo sprecato costa 100K+ token invece di 25 secondi (T032:
    140K token in loop), e li' convertirlo in un passo potrebbe pagare. Va
    rimisurato su T040-T042 prima di dichiararlo inutile.

    Stesso trattamento di D11 (planner) e TH3 (thinking): costruito, misurato,
    spento, con la condizione di retest scritta.
    """
    import os
    return os.environ.get("RG_FINISH_GATE", "").strip() not in ("", "0", "false")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCallSpec(_Strict):
    tool: str
    args: dict


class FinishReport(_Strict):
    status: Literal["done", "blocked"]
    summary: str = Field(max_length=600)
    evidence: list[str]
    verification_requested: list[str]


class WorkerToolStep(_Strict):
    thought: str = Field(max_length=300)  # pensiero corto, non saggio (specsheet §3)
    action: Literal["tool"]
    tool_call: ToolCallSpec


class WorkerFinishStep(_Strict):
    thought: str = Field(max_length=300)
    action: Literal["finish"]
    finish: FinishReport


class WorkerStep(RootModel[Annotated[WorkerToolStep | WorkerFinishStep,
                                     Field(discriminator="action")]]):
    """NOTA di design (F2.5, terzo giro): la coerenza action↔payload e' STRUTTURALE.

    Storia: prima era un model_validator (falsi LlmInvalidOutput), poi un dato
    gestito in-loop. Il collaudo ha mostrato il caso peggiore: un doppio apice non
    escapato nel thought chiude la stringa JSON, il modello deraglia e l'unica
    uscita sintattica era l'incoerente finish:null -> loop caotici da 60+ chiamate.
    Con la union discriminata il ramo incompleto NON e' generabile: dopo un derail
    la grammatica costringe comunque a un passo intero e coerente.
    """


class Worker(Role):
    name = "worker"
    output_model = WorkerStep

    def _finish_gate(self, ctx: RoleContext, task_id: str,
                     mutated: bool) -> str | None:
        """LAD.9: messaggio di rifiuto azionabile, o None se il finish puo' passare.

        Due condizioni DISTINTE, deliberatamente strette:

        1. `expected_outputs` promessi ma inesistenti -> rifiuto. Costo zero.
        2. Firma del finish fantasma: nessuna mutazione in questo tentativo E
           oracolo di `verification` rosso -> rifiuto.

        Perche' la CONGIUNZIONE e non il solo oracolo rosso: la regola 11 della
        card autorizza a chiudere `done` quando i test falliscono FUORI dal
        proprio perimetro (li possiede una sottofase successiva). Rifiutare ogni
        finish con oracolo rosso ucciderebbe quella via d'uscita e produrrebbe
        thrashing sui task multi-sottofase. Cosi' si colpisce solo il caso
        logicamente impossibile: hai dichiarato fatto, non hai cambiato niente,
        e l'oracolo e' rosso.

        Costo nel percorso buono: ZERO. Se il tentativo ha mutato qualcosa
        l'oracolo non viene eseguito qui — gira solo sul sospetto di fantasma.
        """
        spec = ctx.subtask
        if spec is None:
            return None

        missing = []
        for out in spec.expected_outputs:
            try:
                if not self.router.scope.check_read(out).exists():
                    missing.append(out)
            except Exception:
                missing.append(out)
        if missing:
            return (f"you declared this subtask done, but the promised output(s) "
                    f"{missing} do NOT exist on disk. Nothing you described was "
                    f"written. Create them now with write_file, then finish.")

        if mutated:
            return None

        from redgiant.core.verify import _is_cmd_id
        for check in spec.verification:
            if not _is_cmd_id(self.router, check):
                continue
            res = self.router.dispatch(task_id, spec.id, "run_tests",
                                       {"cmd_id": check})
            if not res.ok:
                tail = str(res.data.get("output_tail", res.error or ""))[-300:]
                return (f"you declared this subtask done, but in THIS attempt you "
                        f"never wrote, edited or patched any file, and the "
                        f"verification '{check}' fails:\n{tail}\n"
                        f"Describing an action does not perform it. Do the actual "
                        f"tool call now, then finish.")
        return None

    def run(self, ctx: RoleContext, *, max_steps: int,
            step_max_tokens: int = 512,
            step_log=None, resume_file=None) -> FinishReport:
        """step_log: callable(str) opzionale — osservabilita' §20, ogni step loggato.
        resume_file: Path opzionale (F2.5, richiesta utente) — ripresa IN-PLACE dopo
        un'approvazione: al blocco il contesto volatile viene salvato li'; alla
        ripresa si riparte dallo step esatto (prefill quasi tutto in KV cache),
        invece di rifare letture ed edit da zero."""
        task = ctx.task
        volatile = ctx.volatile
        if resume_file is not None and resume_file.is_file():
            volatile = resume_file.read_text(encoding="utf-8")
            volatile += ("\n[RESUMED] The pending request has been decided by the "
                         "user. Re-issue that tool call now: if granted it will "
                         "execute; if denied you will get approval_denied as data.")
            if step_log is not None:
                step_log("ripresa in-place dal contesto salvato")
        tools = self.router.allowed_for(self.name, task.domain)
        parts = self.assembler.build(
            self.name, task=task, subtask=ctx.subtask, tools=tools,
            volatile=volatile,
            output_schema=WorkerStep.model_json_schema(), schema_name="WorkerStep")

        from redgiant.llm.client import LlmTruncated

        last_call_sig: str | None = None
        fail_counts: dict[tuple, int] = {}
        # LAD.9: stato del gate sul finish. `mutated` e' vero appena UNA scrittura
        # va a buon fine in questo tentativo — e' cio' che distingue il lavoro
        # fatto dal lavoro solo raccontato.
        gate_on = finish_gate_enabled()
        mutated = False
        finish_refusals = 0
        # TH0.3 (braccio T-J): pensiero per-step di J — il canale e' usa-e-getta
        # dentro complete() (TH-D2): la catena append-only 'parts' non lo vede mai
        from redgiant.plansys import thinking_budget, thinking_roles
        think = thinking_budget() if self.name in thinking_roles() else None
        for k in range(1, max_steps + 1):
            try:
                wrapper: WorkerStep = self.llm.complete(
                    parts, role=self.name, schema=WorkerStep,
                    max_tokens=step_max_tokens, task_id=task.id,
                    subtask_id=ctx.subtask.id if ctx.subtask else None,
                    think=think).parsed  # type: ignore
                step = wrapper.root
            except LlmTruncated:
                # F2.5: il troncamento di UNO step non brucia il tentativo intero —
                # e' un dato in-loop (la KV resta calda), come i tool error.
                parts = parts.with_appended_context(
                    f"\n[STEP {k} TRUNCATED] your output exceeded the step budget "
                    f"({step_max_tokens} tokens). Emit a SHORTER step: brief thought, "
                    f"smaller edit (split large changes into multiple edit_file calls).")
                if step_log is not None:
                    step_log(f"step {k}: TRUNCATED at {step_max_tokens} tok")
                continue

            if step_log is not None:
                step_log(f"step {k}: {step.model_dump_json()[:280]}")

            if isinstance(step, WorkerFinishStep):
                if (step.finish.status == "done" and gate_on
                        and finish_refusals < _MAX_FINISH_REFUSALS):
                    problem = self._finish_gate(ctx, task.id, mutated)
                    if problem is not None:
                        finish_refusals += 1
                        if step_log is not None:
                            step_log(f"step {k}: FINISH REFUSED ({finish_refusals}"
                                     f"/{_MAX_FINISH_REFUSALS})")
                        parts = parts.with_appended_context(
                            f"\n[FINISH REFUSED] {problem}")
                        continue
                if resume_file is not None:
                    resume_file.unlink(missing_ok=True)  # tentativo concluso
                return step.finish

            call = step.tool_call  # WorkerToolStep: garantito dalla struttura
            result = self.router.dispatch(
                task.id, ctx.subtask.id if ctx.subtask else "", call.tool, call.args)

            if result.error == "awaiting_approval":
                if resume_file is not None:
                    resume_file.parent.mkdir(parents=True, exist_ok=True)
                    resume_file.write_text(
                        parts.volatile_context
                        + f"\n[STEP {k}] {step.model_dump_json()}"
                        + f"\n[STEP {k} RESULT] awaiting user approval for '{call.tool}'",
                        encoding="utf-8")
                return FinishReport(status="blocked",
                                    summary=f"awaiting user approval for tool '{call.tool}'",
                                    evidence=[], verification_requested=[])

            if result.ok and call.tool in _MUTATING_TOOLS:
                mutated = True  # LAD.9: il mondo e' cambiato davvero, non a parole

            sig = json.dumps({"t": call.tool, "a": call.args}, sort_keys=True)
            repeat_note = ""
            counted: list[tuple] = []
            if sig == last_call_sig:
                repeat_note = ("\n[NOTE] identical call repeated - change approach "
                               "or finish (blocked) instead of retrying it again.")
                # A/B 2026-08-02: la ripetizione identica consecutiva e' degenere
                # anche quando la chiamata "riesce" (visto: 15 edit no-op di fila
                # fino a esaurire gli step): entra nel guard cumulativo come un
                # fallimento, non resta un semplice avviso. Rerun stesso giorno:
                # run_tests ESENTATO (come per tests_failed) — rieseguire l'oracolo
                # e' lecito, il guard abortiva le sottofasi di sola analisi.
                if call.tool != "run_tests":
                    counted.append((call.tool, "identical_repeat"))
            last_call_sig = sig

            # F2.5 (loop da 12 step) + retest D2: la ripetizione va contata in modo
            # CUMULATIVO per (tool, errore) nel tentativo — quella consecutiva era
            # aggirabile alternando letture ok tra un fallimento e l'altro.
            if not result.ok and not (call.tool == "run_tests"
                                      and result.error == "tests_failed"):
                # i test ROSSI durante l'iterazione sono l'oracolo che parla, non
                # un tool rotto: non contano per l'aborto (il tetto e' max_steps)
                counted.append((call.tool, result.error))
            for fk in counted:
                fail_counts[fk] = fail_counts.get(fk, 0) + 1
                n = fail_counts[fk]
                if n >= 8:
                    return FinishReport(
                        status="blocked",
                        summary=f"tool '{fk[0]}' failed {n} times with "
                                f"'{fk[1]}' in this attempt: aborting early",
                        evidence=[], verification_requested=[])
                if n in (3, 5):
                    repeat_note += (f"\n[ADVICE] '{fk[0]}' has failed {n} times "
                                    f"with '{fk[1]}' in this attempt. STOP "
                                    f"retrying it the same way: switch tool (e.g. "
                                    f"write_file to rewrite the whole file) or finish "
                                    f"blocked.")

            parts = parts.with_appended_context(
                f"\n[STEP {k}] {step.model_dump_json()}"
                f"\n[STEP {k} RESULT] {self._serialize(result)}{repeat_note}")

        return FinishReport(status="blocked", summary="step budget exhausted",
                            evidence=[], verification_requested=[])

    @staticmethod
    def _serialize(result: ToolResult) -> str:
        payload = {"ok": result.ok, "data": result.data,
                   "evidence": result.evidence, "error": result.error}
        text = json.dumps(payload, ensure_ascii=False)
        if len(text) > _RESULT_MAX_CHARS:
            text = text[:_RESULT_MAX_CHARS] + f'... [TRUNCATED at {_RESULT_MAX_CHARS} chars]'
        return text
