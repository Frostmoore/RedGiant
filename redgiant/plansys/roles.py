"""I ruoli creativi del plansys (PS2/PS3/PS4).

PS-D1: le chiamate LLM di questo package vivono SOLO qui e in compiler.py.
Pattern comune (lezione F3/F6 del README): validazione deterministica dopo il
parse, UNA richiamata correttiva che CITA le regole violate, poi eccezione
esplicita — mai loop di rigenerazione.
"""

from __future__ import annotations

from pydantic import BaseModel

from redgiant.plansys.artifacts import MacroPlan, PhaseAnalysis, PhaseBlueprint
from redgiant.plansys.gates import macro_validation_gate, normalize_macro
from redgiant.roles.base import Role, RoleContext


class MacroRejected(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


class SeniorPlanner(Role):
    """S: scrive il MacroPlan una volta e esce di scena (PS-D1)."""
    name = "senior_planner"
    output_model = MacroPlan

    def run(self, ctx: RoleContext, *, max_tokens: int = 1024) -> MacroPlan:
        parts = self.assembler.build(
            self.name, task=ctx.task, subtask=None, tools=[],
            volatile=ctx.volatile,
            output_schema=MacroPlan.model_json_schema(), schema_name="MacroPlan")
        out: MacroPlan = self.llm.complete(
            parts, role=self.name, schema=MacroPlan, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        report = macro_validation_gate(normalize_macro(out))
        if report.ok:
            return out
        problems = [f"{c.name}: {c.detail}" for c in report.checks if not c.ok]
        # una sola richiamata, citando le REGOLE violate (non solo i sintomi)
        retry = parts.with_appended_context(
            "\n[PLAN REJECTED] fix ALL of these problems: " + "; ".join(problems)
            + "\n[RULES] every criterion id (C1..) must appear in the covers list"
              " of at least one phase; depends_on may list ONLY ids of phases in"
              " THIS plan (like \"P1\"); a phase with no dependencies has"
              " depends_on: []; at least one phase must have depends_on: [].")
        out = self.llm.complete(
            retry, role=self.name, schema=MacroPlan, max_tokens=max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[assignment]
        report = macro_validation_gate(normalize_macro(out))
        if not report.ok:
            raise MacroRejected(
                [f"{c.name}: {c.detail}" for c in report.checks if not c.ok])
        return out


def parse_artifact(model: type[BaseModel], payload_json: str) -> BaseModel:
    """Helper condiviso: rilettura tipizzata di un artefatto persistito."""
    return model.model_validate_json(payload_json)


class _SingleShot(Role):
    """M1..M4 sono passi di compilazione SINGLE-SHOT: una chiamata, un parse.
    Le correzioni non vivono qui ma nel PhaseCompiler come patch (PS-D6)."""

    def run(self, ctx: RoleContext, *, max_tokens: int = 1024) -> BaseModel:
        parts = self.assembler.build(
            self.name, task=ctx.task, subtask=None, tools=[],
            volatile=ctx.volatile,
            output_schema=self.output_model.model_json_schema(),
            schema_name=self.output_model.__name__)
        return self.llm.complete(
            parts, role=self.name, schema=self.output_model,
            max_tokens=max_tokens, task_id=ctx.task.id).parsed


class PhaseAnalyst(_SingleShot):
    """M1: analisi della macrofase, decisioni esplicite, choice point."""
    name = "phase_analyst"
    output_model = PhaseAnalysis


class WorkDecomposer(_SingleShot):
    """M2: decomposizione in microfasi con ownership esclusiva."""
    name = "work_decomposer"
    output_model = PhaseBlueprint
