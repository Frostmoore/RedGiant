"""PhaseCompiler (PS3.3/PS4): la pipeline di compilazione M1->M4.

PS-D3: quattro invocazioni dello stesso modello con schemi piccoli, validate
deterministicamente tra un passo e l'altro. PS-D6: le correzioni sono PATCH
tipizzate dell'artefatto (max 2 per passo, poi 1 rigenerazione, poi
CompileFailed esplicito) — mai rigenerazioni a raffica.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from redgiant.config import Config
from redgiant.llm.client import LlamaClient
from redgiant.plansys.artifacts import (BlueprintPatch, ChoicePoint, MacroPhase,
                                        MacroPlan, PhaseAnalysis, PhaseBlueprint)
from redgiant.plansys.gates import validate_analysis, validate_blueprint
from redgiant.plansys.ledger import build_ledger, project_for_phase, render_ledger
from redgiant.plansys.render import write_plan_doc
from redgiant.plansys.roles import PhaseAnalyst, WorkDecomposer
from redgiant.prompts.assemble import PromptAssembler
from redgiant.roles.base import RoleContext
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter

_MAX_PATCHES = 2  # per passo; poi 1 rigenerazione intera, poi CompileFailed


class CompileFailed(Exception):
    def __init__(self, step: str, problems: list[str]) -> None:
        self.step = step
        self.problems = problems
        super().__init__(f"{step}: " + "; ".join(problems))


class NeedsDecision(Exception):
    """PS-D8: M1 ha emesso decision_required — il chiamante instrada la
    clarification sul canale approvals esistente e sospende la compilazione."""

    def __init__(self, phase_id: str, choice: ChoicePoint) -> None:
        self.phase_id = phase_id
        self.choice = choice
        super().__init__(f"{phase_id}: {choice.question}")


# Le liste patchabili di ogni artefatto: (chiave lista, chiave identita')
_PATCHABLE: dict[str, tuple[str, str]] = {
    "PhaseAnalysis": ("decisions", "id"),
    "PhaseBlueprint": ("micro", "id"),
    "VerificationBlueprint": ("obligations", "id"),
    "TestBundle": ("artifacts", "path"),
}


class PhaseCompiler:
    def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                 assembler: PromptAssembler, router: ToolRouter,
                 scope: Scope) -> None:
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.assembler = assembler
        self.router = router
        self.scope = scope

    # ── passi M1/M2 (PS3; M3/M4 in PS4) ─────────────────────────────────────

    def projection(self, task_id: str, plan: MacroPlan, phase: MacroPhase) -> str:
        ledger = build_ledger(self.store, self.scope, task_id)
        write_plan_doc(self.cfg.paths.tasks_dir, task_id, "ledger",
                       render_ledger(ledger))
        proj = project_for_phase(ledger, plan, phase.id,
                                 self.cfg.plansys.projection_max_tokens,
                                 self.llm.count_tokens)
        answer = self.store.latest_clarification_answer(task_id)
        if answer:
            proj += f"\n[USER ANSWER] {answer}"
        return proj

    def analyze(self, task_id: str, plan: MacroPlan, phase: MacroPhase,
                projection: str, log) -> PhaseAnalysis:
        state = self.store.load_task(task_id)
        volatile = (f"{projection}\n[MACRO PHASE] {phase.id} — {phase.title}: "
                    f"{phase.intent} (covers: {', '.join(phase.covers)})")
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = PhaseAnalyst(self.llm, self.assembler, self.router)
        out: PhaseAnalysis = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens)  # type: ignore
        out = self._repair_loop("M1", role, ctx, out, PhaseAnalysis,
                                lambda a: validate_analysis(a, volatile, phase.id),
                                log)
        if out.decision_required is not None:
            self.store.save_ps_artifact(
                task_id, kind="phase_analysis", ref=phase.id,
                payload_json=out.model_dump_json(), actor="phase_compiler")
            raise NeedsDecision(phase.id, out.decision_required)
        self.store.save_ps_artifact(task_id, kind="phase_analysis", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M1: {len(out.decisions)} decisioni, "
                             f"{len(out.artifacts)} artefatti")
        return out

    def decompose(self, task_id: str, phase: MacroPhase, analysis: PhaseAnalysis,
                  projection: str, log) -> PhaseBlueprint:
        state = self.store.load_task(task_id)
        volatile = (f"{projection}\n[ANALYSIS] {analysis.model_dump_json()}")
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = WorkDecomposer(self.llm, self.assembler, self.router)
        out: PhaseBlueprint = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens)  # type: ignore
        out = self._repair_loop(
            "M2", role, ctx, out, PhaseBlueprint,
            lambda b: validate_blueprint(b, analysis, phase.covers), log)
        self.store.save_ps_artifact(task_id, kind="phase_blueprint", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M2: {len(out.micro)} microfasi")
        return out

    # ── meccanica delle correzioni (PS-D6) ───────────────────────────────────

    def _repair_loop(self, step: str, role, ctx: RoleContext, artifact: BaseModel,
                     model: type[BaseModel], validate, log) -> BaseModel:
        problems = validate(artifact)
        patches = 0
        while problems and patches < _MAX_PATCHES:
            patches += 1
            log.line("compiler", f"{step} respinto ({len(problems)}): patch {patches}")
            patch = self._request_patch(ctx, role.name, problems,
                                        artifact.model_dump_json())
            try:
                artifact = model.model_validate_json(
                    self._apply_patch(model, artifact.model_dump_json(), patch))
            except (ValidationError, ValueError) as e:
                problems = [f"patch not applicable: {e}"[:200]]
                continue
            problems = validate(artifact)
        if problems:
            # ultima spiaggia: UNA rigenerazione intera con le violazioni citate
            log.line("compiler", f"{step}: patch esaurite, rigenerazione unica")
            retry_ctx = RoleContext(
                task=ctx.task, subtask=None,
                volatile=ctx.volatile + "\n[REJECTED] your previous output had "
                "these problems, produce a corrected COMPLETE object: "
                + "; ".join(problems))
            artifact = role.run(retry_ctx,
                                max_tokens=self.cfg.plansys.m_pass_max_tokens)
            problems = validate(artifact)
            if problems:
                raise CompileFailed(step, problems)
        return artifact

    def _request_patch(self, ctx: RoleContext, role_name: str,
                       violations: list[str], current_json: str) -> BlueprintPatch:
        parts = self.assembler.build(
            role_name, task=ctx.task, subtask=None, tools=[],
            volatile=(f"[ARTIFACT] {current_json}\n[VIOLATIONS] "
                      + "; ".join(violations)
                      + "\nEmit a BlueprintPatch that fixes ONLY the violated "
                        "parts. op=replace/add/remove; target = the id (or path)"
                        " of the element; payload_json = the complete corrected "
                        "element as a JSON string (empty for remove)."),
            output_schema=BlueprintPatch.model_json_schema(),
            schema_name="BlueprintPatch")
        return self.llm.complete(
            parts, role=role_name, schema=BlueprintPatch,
            max_tokens=self.cfg.plansys.m_pass_max_tokens,
            task_id=ctx.task.id).parsed  # type: ignore[return-value]

    @staticmethod
    def _apply_patch(model: type[BaseModel], artifact_json: str,
                     patch: BlueprintPatch) -> str:
        """Applicazione DETERMINISTICA: opera sulla lista patchabile del tipo
        (micro/obligations/decisions/artifacts), identita' per id/path."""
        list_key, id_key = _PATCHABLE[model.__name__]
        data = json.loads(artifact_json)
        items: list[dict] = data.get(list_key, [])
        for op in patch.ops:
            if op.op == "remove":
                items = [i for i in items if i.get(id_key) != op.target]
                continue
            payload = json.loads(op.payload_json)
            if op.op == "add":
                items.append(payload)
            else:  # replace
                idx = next((k for k, i in enumerate(items)
                            if i.get(id_key) == op.target), None)
                if idx is None:
                    raise ValueError(f"replace target '{op.target}' not found")
                items[idx] = payload
        data[list_key] = items
        return json.dumps(data)
