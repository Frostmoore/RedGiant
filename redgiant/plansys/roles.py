"""I ruoli creativi del plansys (PS2/PS3/PS4).

PS-D1: le chiamate LLM di questo package vivono SOLO qui e in compiler.py.
Pattern comune (lezione F3/F6 del README): validazione deterministica dopo il
parse, UNA richiamata correttiva che CITA le regole violate, poi eccezione
esplicita — mai loop di rigenerazione.
"""

from __future__ import annotations

from pydantic import BaseModel

from redgiant.plansys.artifacts import (MacroPlan, PhaseAnalysis, PhaseBlueprint,
                                        TestBundle, VerificationBlueprint)
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
        from redgiant.plansys import thinking_budget, thinking_roles
        think = thinking_budget() if self.name in thinking_roles() else None
        out: MacroPlan = self.llm.complete(
            parts, role=self.name, schema=MacroPlan, max_tokens=max_tokens,
            task_id=ctx.task.id, think=think).parsed  # type: ignore[assignment]
        report = macro_validation_gate(normalize_macro(out), ctx.task.request)
        # fino a DUE richiamate correttive (fast #4: la coverage e' l'errore
        # piu' meccanicamente correggibile; una richiamata sola perdeva task
        # interi su code di instabilita' — revisione annotata nel piano),
        # ciascuna citando le REGOLE violate, non solo i sintomi
        for _ in range(2):
            if report.ok:
                return out
            problems = [f"{c.name}: {c.detail}" for c in report.checks
                        if not c.ok]
            retry = parts.with_appended_context(
                "\n[PLAN REJECTED] fix ALL of these problems: "
                + "; ".join(problems)
                + "\n[RULES] every criterion id (C1..) must appear in the"
                  " covers list of at least one phase; depends_on may list ONLY"
                  " ids of phases in THIS plan (like \"P1\"); a phase with no"
                  " dependencies has depends_on: []; at least one phase must"
                  " have depends_on: []; every file named in the request must"
                  " appear in a criterion or phase intent — plan ALL of it.")
            out = self.llm.complete(
                retry, role=self.name, schema=MacroPlan, max_tokens=max_tokens,
                task_id=ctx.task.id, think=think).parsed  # type: ignore[assignment]
            report = macro_validation_gate(normalize_macro(out), ctx.task.request)
        if not report.ok:
            raise MacroRejected(
                [f"{c.name}: {c.detail}" for c in report.checks if not c.ok])
        return out


def parse_artifact(model: type[BaseModel], payload_json: str) -> BaseModel:
    """Helper condiviso: rilettura tipizzata di un artefatto persistito."""
    return model.model_validate_json(payload_json)


class _SingleShot(Role):
    """M1..M4 sono passi di compilazione SINGLE-SHOT: una chiamata, un parse.
    Le correzioni non vivono qui ma nel PhaseCompiler come patch (PS-D6).
    Eccezione (lezione F0/F2): il TRONCAMENTO e' un dato — un solo retry con
    l'istruzione esplicita di produrre MENO, poi l'errore sale."""

    def run(self, ctx: RoleContext, *, max_tokens: int = 1024,
            grammar_schema: dict | None = None) -> BaseModel:
        from redgiant.llm.client import LlmTruncated
        volatile = ctx.volatile
        for attempt in (1, 2):
            parts = self.assembler.build(
                self.name, task=ctx.task, subtask=None, tools=[],
                volatile=volatile,
                output_schema=self.output_model.model_json_schema(),
                schema_name=self.output_model.__name__)
            from redgiant.plansys import thinking_budget, thinking_roles
            think = (thinking_budget()
                     if self.name in thinking_roles() else None)
            try:
                return self.llm.complete(
                    parts, role=self.name, schema=self.output_model,
                    max_tokens=max_tokens, task_id=ctx.task.id,
                    grammar_schema=grammar_schema, think=think).parsed
            except LlmTruncated:
                if attempt == 2:
                    raise
                volatile += (f"\n[TRUNCATED] your previous output exceeded "
                             f"{max_tokens} tokens and was discarded. Produce "
                             f"a SMALLER object: fewer items (1-3), terse "
                             f"strings, no prose beyond the required fields.")
        raise AssertionError("unreachable")


class PhaseAnalyst(_SingleShot):
    """M1: analisi della macrofase, decisioni esplicite, choice point."""
    name = "phase_analyst"
    output_model = PhaseAnalysis


class WorkDecomposer(_SingleShot):
    """M2: decomposizione in microfasi con ownership esclusiva."""
    name = "work_decomposer"
    output_model = PhaseBlueprint


class VerificationDesigner(_SingleShot):
    """M3: gli obblighi di prova (cosa dimostrare, con quale oracolo)."""
    name = "verification_designer"
    output_model = VerificationBlueprint


class TestAuthor(_SingleShot):
    """M4: i file di test COMPLETI per gli obblighi (materializza il control
    plane, mai J; qualifica il gate, mai la fiducia)."""
    name = "test_author"
    output_model = TestBundle
