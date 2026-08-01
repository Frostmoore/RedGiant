"""Planner (piano F3.1, specsheet §6.3): la mappa del lavoro, sintetica per contratto.

"Pianificazione globale, esecuzione locale" (§1): il piano è una mappa, non un
romanzo — il limite di fasi/token è un vincolo di QUALITÀ (un piano corto si
aggiorna, uno lungo si abbandona) oltre che di costo (D8).

La forma la garantisce la grammatica (D3); la LOGICA la validano check
deterministici (id univoci, dipendenze esistenti e acicliche): violazione =
una sola richiamata con l'errore nel contesto, poi si fallisce esplicitamente
(niente loop di replanning sull'output malformato).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from redgiant.roles.base import Role, RoleContext
from redgiant.state.models import PhaseSpec


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(max_length=300)
    success_criteria: list[str] = Field(max_length=6)
    phases: list[PhaseSpec] = Field(max_length=7)  # D21: tetto duro


def validate_plan_logic(out: PlannerOutput,
                        required_phase_ids: list[str] | None = None) -> list[str]:
    """Check deterministici sulla LOGICA del piano. Ritorna i problemi (vuoto = ok)."""
    problems: list[str] = []
    ids = [p.id for p in out.phases]
    if not ids:
        problems.append("plan has no phases")
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate phase ids: {ids}")
    known = set(ids)
    for p in out.phases:
        for dep in p.depends_on:
            if dep not in known:
                problems.append(f"phase {p.id} depends on unknown phase '{dep}'")
            if dep == p.id:
                problems.append(f"phase {p.id} depends on itself")
    # aciclicità (DFS)
    graph = {p.id: [d for d in p.depends_on if d in known] for p in out.phases}
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    def dfs(node: str) -> bool:
        color[node] = GREY
        for nxt in graph[node]:
            if color[nxt] == GREY or (color[nxt] == WHITE and dfs(nxt)):
                return True
        color[node] = BLACK
        return False

    if any(dfs(n) for n in graph if color[n] == WHITE):
        problems.append("dependency cycle detected")
    if ids and not any(not p.depends_on for p in out.phases):
        problems.append("no root phase (every phase has dependencies)")
    for rid in required_phase_ids or []:
        if rid not in known:
            problems.append(f"COMPLETED phase '{rid}' was dropped: it must be kept")
    return problems


class Planner(Role):
    name = "planner"
    output_model = PlannerOutput

    def run(self, ctx: RoleContext, *, max_tokens: int = 1536,
            required_phase_ids: list[str] | None = None) -> PlannerOutput:
        parts = self.assembler.build(
            self.name, task=ctx.task, subtask=None, tools=[],
            volatile=ctx.volatile,
            output_schema=PlannerOutput.model_json_schema(), schema_name="PlannerOutput")
        out: PlannerOutput = self.llm.complete(
            parts, role=self.name, schema=PlannerOutput, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        problems = validate_plan_logic(out, required_phase_ids)
        if not problems:
            return out
        # una sola richiamata, con gli errori come dati (D3: la forma è garantita,
        # qui si corregge la logica)
        retry = parts.with_appended_context(
            "\n[PLAN REJECTED] your plan has logical problems, fix ALL of them: "
            + "; ".join(problems))
        out = self.llm.complete(
            retry, role=self.name, schema=PlannerOutput, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        problems = validate_plan_logic(out, required_phase_ids)
        if problems:
            raise PlanRejected(problems)
        return out


class PlanRejected(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))
