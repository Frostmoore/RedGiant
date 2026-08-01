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

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    thought: str = Field(max_length=300)  # pensiero corto, non saggio (specsheet §3)
    action: Literal["tool", "finish"]
    tool_call: ToolCallSpec | None = None
    finish: FinishReport | None = None

    @model_validator(mode="after")
    def _coherent(self) -> "WorkerStep":
        if self.action == "tool" and (self.tool_call is None or self.finish is not None):
            raise ValueError("action=tool requires tool_call and no finish")
        if self.action == "finish" and (self.finish is None or self.tool_call is not None):
            raise ValueError("action=finish requires finish and no tool_call")
        return self


class Worker(Role):
    name = "worker"
    output_model = WorkerStep

    def run(self, ctx: RoleContext, *, max_steps: int,
            step_max_tokens: int = 512) -> FinishReport:
        task = ctx.task
        tools = self.router.allowed_for(self.name, task.domain)
        parts = self.assembler.build(
            self.name, task=task, subtask=ctx.subtask, tools=tools,
            volatile=ctx.volatile,
            output_schema=WorkerStep.model_json_schema(), schema_name="WorkerStep")

        last_call_sig: str | None = None
        for k in range(1, max_steps + 1):
            step: WorkerStep = self.llm.complete(
                parts, role=self.name, schema=WorkerStep,
                max_tokens=step_max_tokens, task_id=task.id,
                subtask_id=ctx.subtask.id if ctx.subtask else None).parsed  # type: ignore

            if step.action == "finish":
                return step.finish  # type: ignore[return-value]

            call = step.tool_call
            assert call is not None  # garantito dal validator
            result = self.router.dispatch(
                task.id, ctx.subtask.id if ctx.subtask else "", call.tool, call.args)

            if result.error == "awaiting_approval":
                return FinishReport(status="blocked",
                                    summary=f"awaiting user approval for tool '{call.tool}'",
                                    evidence=[], verification_requested=[])

            sig = json.dumps({"t": call.tool, "a": call.args}, sort_keys=True)
            repeat_note = ""
            if sig == last_call_sig:
                repeat_note = ("\n[NOTE] identical call repeated - change approach "
                               "or finish (blocked) instead of retrying it again.")
            last_call_sig = sig

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
