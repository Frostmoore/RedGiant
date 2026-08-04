"""Modelli Pydantic dello stato (piano F1.1, §A5).

Tutti con extra="forbid": un campo inatteso è un bug, non una tolleranza.
Lo stato strutturato è la memoria primaria del sistema (specsheet §8, D-25.3);
la cronologia testuale è solo una fonte secondaria.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

TaskStatus = Literal["queued", "running", "blocked", "completed", "partial", "failed", "cancelled"]
SubtaskStatus = Literal["pending", "running", "completed", "completed_with_warnings",
                        "retry", "repair", "blocked", "failed", "skipped"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Budget(_Strict):
    max_total_tokens: int
    max_tool_calls: int
    max_retries_per_subtask: int
    max_wall_s: int


class BudgetUsed(_Strict):
    tokens: int = 0
    tool_calls: int = 0
    wall_s: float = 0.0


class SubtaskSpec(_Strict):
    id: str
    phase_id: str
    title: str
    objective: str
    inputs: list[str]
    tools: list[str]
    expected_outputs: list[str]
    completion_criteria: list[str]
    verification: list[str]  # nomi di check per verify.py (cmd_id di test inclusi)


class PhaseSpec(_Strict):
    id: str
    title: str
    depends_on: list[str]
    completion_criteria: list[str]


class Plan(_Strict):
    version: int
    goal: str
    success_criteria: list[str]
    phases: list[PhaseSpec]


class TaskState(_Strict):
    id: str
    request: str
    target_dir: str
    domain: str
    status: TaskStatus
    plan: Plan | None
    current_phase: str | None
    current_subtask: str | None
    budget: Budget
    used: BudgetUsed


class LlmCallRow(_Strict):
    """Riga di llm_calls: scritta dal LlamaClient, letta dalle metriche."""
    role: str
    subtask_id: str | None
    schema_name: str | None
    t_start: str
    prompt_tokens: int
    cached_tokens: int
    gen_tokens: int
    prefill_ms: float
    gen_ms: float
    outcome: Literal["ok", "timeout", "error", "invalid"]
    # TH0: token/ms del canale di pensiero (0 per le chiamate senza thinking)
    thinking_tokens: int = 0
    thinking_ms: float = 0.0
    # F5.0: composizione del prompt sezione per sezione (S1-S7), token.
    # Sapere CHE la finestra si riempie non basta: serve sapere DI COSA, e su
    # ogni chiamata — non solo quando esplode. Costo misurato: 0,5-6,3 ms per
    # sezione contro step da 1-3 s (~0,5%).
    sections: dict[str, int] | None = None


class ToolCallRow(_Strict):
    """Riga di tool_calls: scritta dal ToolRouter."""
    subtask_id: str | None
    tool: str
    args: dict
    ok: bool
    evidence: list[str]
    duration_ms: float
