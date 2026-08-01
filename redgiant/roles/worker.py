"""Worker: ReAct a passo singolo vincolato (piano F1.5, D20).

A ogni step il modello emette UN oggetto WorkerStep (o una tool call o la
chiusura); il risultato viene appeso in coda a S6 e si genera lo step
successivo. La conversazione cresce SOLO in append: il prefisso resta intatto
e la KV cache riusa tutto (F0.5: 65 vs 7971 token).

Il finish del Worker NON chiude la sottofase: la chiude la verifica (D10).
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class WorkerStep(_Strict):
    """NOTA di design (F1.11): niente model_validator di coerenza cross-campo.

    La grammatica (D3) garantisce la FORMA del JSON Schema, ma non puo' esprimere
    "se action=tool allora tool_call presente": un validator Pydantic piu' severo
    dello schema trasformerebbe un'incoerenza semantica del modello in un falso
    LlmInvalidOutput (che per contratto e' un bug di piattaforma). La coerenza si
    verifica nel loop del Worker e l'incoerenza e' un DATO (nota in append), come
    i tool error.
    """
    thought: str = Field(max_length=300)  # pensiero corto, non saggio (specsheet §3)
    action: Literal["tool", "finish"]
    tool_call: ToolCallSpec | None = None
    finish: FinishReport | None = None

    def incoherence(self) -> str | None:
        if self.action == "tool" and self.tool_call is None:
            return "action=tool but tool_call is null"
        if self.action == "finish" and self.finish is None:
            return "action=finish but finish is null"
        return None


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
        last_fail_key: tuple | None = None
        fail_streak = 0
        for k in range(1, max_steps + 1):
            try:
                step: WorkerStep = self.llm.complete(
                    parts, role=self.name, schema=WorkerStep,
                    max_tokens=step_max_tokens, task_id=task.id,
                    subtask_id=ctx.subtask.id if ctx.subtask else None).parsed  # type: ignore
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
            bad = step.incoherence()
            if bad is not None:
                parts = parts.with_appended_context(
                    f"\n[STEP {k}] {step.model_dump_json()}"
                    f"\n[STEP {k} INVALID] {bad} - emit a coherent step: action must "
                    f"match its payload.")
                continue

            if step.action == "finish":
                if resume_file is not None:
                    resume_file.unlink(missing_ok=True)  # tentativo concluso
                return step.finish  # type: ignore[return-value]

            call = step.tool_call
            assert call is not None  # garantito da incoherence()
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
            if sig == last_call_sig:
                repeat_note = ("\n[NOTE] identical call repeated - change approach "
                               "or finish (blocked) instead of retrying it again.")
            last_call_sig = sig

            # F2.5 (loop da 12 step): la ripetizione VA fermata anche quando i
            # tentativi variano nei dettagli — conta (tool, errore), non i byte.
            fail_key = (call.tool, result.error) if not result.ok else None
            if fail_key is not None and fail_key == last_fail_key:
                fail_streak += 1
            else:
                fail_streak = 1 if fail_key is not None else 0
            last_fail_key = fail_key
            if fail_streak >= 6:
                return FinishReport(
                    status="blocked",
                    summary=f"tool '{call.tool}' failed {fail_streak} times in a row "
                            f"with '{result.error}': aborting this attempt early",
                    evidence=[], verification_requested=[])
            if fail_streak == 3:
                repeat_note += (f"\n[ADVICE] '{call.tool}' has now failed {fail_streak} "
                                f"times with '{result.error}'. STOP retrying it the same "
                                f"way: switch tool (e.g. write_file to rewrite the whole "
                                f"file - you already read its content) or finish blocked.")

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
