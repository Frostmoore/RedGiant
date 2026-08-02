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
        for k in range(1, max_steps + 1):
            try:
                wrapper: WorkerStep = self.llm.complete(
                    parts, role=self.name, schema=WorkerStep,
                    max_tokens=step_max_tokens, task_id=task.id,
                    subtask_id=ctx.subtask.id if ctx.subtask else None).parsed  # type: ignore
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

            sig = json.dumps({"t": call.tool, "a": call.args}, sort_keys=True)
            repeat_note = ""
            counted: list[tuple] = []
            if sig == last_call_sig:
                repeat_note = ("\n[NOTE] identical call repeated - change approach "
                               "or finish (blocked) instead of retrying it again.")
                # A/B 2026-08-02: la ripetizione identica consecutiva e' degenere
                # anche quando la chiamata "riesce" (visto: 15 edit no-op di fila
                # fino a esaurire gli step): entra nel guard cumulativo come un
                # fallimento, non resta un semplice avviso.
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
