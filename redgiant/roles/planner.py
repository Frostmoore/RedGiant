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


# A/B 2026-08-02: il modello scrive "none"/"null" per dire "nessuna dipendenza"
# (due task morti in 15s); il rerun ha aggiunto l'auto-dipendenza ("P1 depends
# on P1", altri due task morti in 2 chiamate). Entrambi inequivoci: riparazione
# deterministica, come la normalizzazione N-TAB negli editor.
_DEP_SENTINELS = {"none", "null", "n/a", "-", ""}


def normalize_plan(out: PlannerOutput) -> PlannerOutput:
    """Ripara i sentinelli inequivoci; le vere allucinazioni restano al validatore."""
    for p in out.phases:
        p.depends_on = [d for d in p.depends_on
                        if d.strip().lower() not in _DEP_SENTINELS
                        and d != p.id]
    return out


def validate_plan_logic(out: PlannerOutput,
                        required_phase_ids: list[str] | None = None) -> list[str]:
    """Check deterministici sulla LOGICA del piano. Ritorna i problemi (vuoto = ok).
    PS2.2: i check sul grafo (duplicati, dipendenze, cicli, root) sono condivisi
    con plansys.gates.dag_problems — un solo validatore di dipendenze nel repo."""
    from redgiant.plansys.gates import dag_problems  # lazy: evita il ciclo di import
    problems: list[str] = []
    ids = [p.id for p in out.phases]
    if not ids:
        problems.append("plan has no phases")
    problems += dag_problems([(p.id, p.depends_on) for p in out.phases])
    for rid in required_phase_ids or []:
        if rid not in set(ids):
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
        problems = validate_plan_logic(normalize_plan(out), required_phase_ids)
        if not problems:
            return out
        # una sola richiamata, con gli errori come dati (D3: la forma è garantita,
        # qui si corregge la logica). A/B 2026-08-02: elencare i problemi non
        # basta — il modello piccolo va istruito sulla regola violata, non solo
        # sul sintomo.
        retry = parts.with_appended_context(
            "\n[PLAN REJECTED] your plan has logical problems, fix ALL of them: "
            + "; ".join(problems)
            + "\n[RULES] depends_on may list ONLY ids of phases in THIS plan "
              "(like \"P1\") - never file names or words like \"none\". A phase "
              "with no dependencies has depends_on: []. At least one phase must "
              "have depends_on: [].")
        out = self.llm.complete(
            retry, role=self.name, schema=PlannerOutput, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        problems = validate_plan_logic(normalize_plan(out), required_phase_ids)
        if problems:
            raise PlanRejected(problems)
        return out


class PlanRejected(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))
