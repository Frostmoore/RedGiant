"""Phase Designer (piano F3.2, specsheet §6.4): espande UNA fase in sottofasi.

Punto di massima leva della qualità: qui si decide la FORMA del lavoro, e il
criterio D10 è hard — la decomposizione preferisce sottofasi meccanicamente
verificabili; una sottofase senza verifica eseguibile è un design respinto.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from redgiant.roles.base import Role, RoleContext
from redgiant.state.models import SubtaskSpec


class PhaseDesign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phase_id: str
    subtasks: list[SubtaskSpec] = Field(max_length=6)  # D21


def validate_design_logic(out: PhaseDesign, current_phase_id: str,
                          known_cmd_ids: set[str]) -> list[str]:
    problems: list[str] = []
    if out.phase_id != current_phase_id:
        problems.append(f"phase_id must be '{current_phase_id}', got '{out.phase_id}'")
    if not out.subtasks:
        problems.append("no subtasks")
    ids = [s.id for s in out.subtasks]
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate subtask ids: {ids}")
    pattern = re.compile(rf"^{re.escape(current_phase_id)}\.S\d+$")
    for s in out.subtasks:
        if not pattern.match(s.id):
            problems.append(f"subtask id '{s.id}' must match {current_phase_id}.S<n>")
        if s.phase_id != current_phase_id:
            problems.append(f"subtask {s.id} has phase_id '{s.phase_id}'")
        if not s.verification:
            # D10 hard: senza oracolo la sottofase non e' accettabile...
            # ...MA una fase puo' legittimamente avere sottofasi preparatorie
            # verificate dagli expected_outputs: si accetta verification vuota
            # SOLO se expected_outputs non e' vuoto (l'esistenza e' un oracolo).
            if not s.expected_outputs:
                problems.append(f"subtask {s.id} has no verification AND no "
                                f"expected_outputs: nothing mechanical can check it")
        for v in s.verification:
            if v not in known_cmd_ids:
                problems.append(f"subtask {s.id} verification '{v}' is not a known "
                                f"test command (known: {sorted(known_cmd_ids)})")
    # REVISIONE F3.2 (churn T009, concordata con l'utente): perimetro e verifica
    # devono coincidere — in una fase multi-sottofase la suite di test va SOLO
    # sull'ultima sottofase; le intermedie si verificano su cio' che possiedono
    # (un worker punito da test rossi fuori dal suo confine riscrive all'infinito
    # l'unico file che puo' toccare: 49 riscritture osservate).
    if len(out.subtasks) > 1:
        for s in out.subtasks[:-1]:
            if s.verification:
                problems.append(
                    f"subtask {s.id}: full test-suite verification is allowed ONLY on "
                    f"the LAST subtask of the phase; intermediate subtasks must be "
                    f"checked by their expected_outputs")
    return problems


class PhaseDesigner(Role):
    name = "phase_designer"
    output_model = PhaseDesign

    def run(self, ctx: RoleContext, *, current_phase_id: str,
            known_cmd_ids: set[str], max_tokens: int = 2048) -> PhaseDesign:
        parts = self.assembler.build(
            self.name, task=ctx.task, subtask=None, tools=[],
            volatile=ctx.volatile,
            output_schema=PhaseDesign.model_json_schema(), schema_name="PhaseDesign")
        out: PhaseDesign = self.llm.complete(
            parts, role=self.name, schema=PhaseDesign, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        problems = validate_design_logic(out, current_phase_id, known_cmd_ids)
        if not problems:
            return out
        retry = parts.with_appended_context(
            "\n[DESIGN REJECTED] fix ALL of these problems: " + "; ".join(problems))
        out = self.llm.complete(
            retry, role=self.name, schema=PhaseDesign, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        problems = validate_design_logic(out, current_phase_id, known_cmd_ids)
        if problems:
            raise DesignRejected(problems)
        return out


class DesignRejected(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))
