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
                                        MacroPlan, PhaseAnalysis, PhaseBlueprint,
                                        TestBundle, VerificationBlueprint)
from redgiant.plansys.gates import (oracle_qualification_gate, validate_analysis,
                                    validate_blueprint, validate_bundle,
                                    validate_verification)
from redgiant.plansys.ledger import build_ledger, project_for_phase, render_ledger
from redgiant.plansys.render import render_blueprint, write_plan_doc
from redgiant.plansys.roles import (PhaseAnalyst, TestAuthor,
                                    VerificationDesigner, WorkDecomposer)
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

        def _norm(b: PhaseBlueprint) -> PhaseBlueprint:
            # Smoke PS4.3: M2 inventa criteri mai esistiti (C3/C4 su un piano
            # C1-C2). Un id che non e' nel piano e' rumore inequivoco:
            # riparazione deterministica, non un giro di patch.
            for m in b.micro:
                m.proves = [c for c in m.proves if c in phase.covers]
            return b

        out: PhaseBlueprint = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens)  # type: ignore
        out = self._repair_loop(
            "M2", role, ctx, out, PhaseBlueprint,
            lambda b: validate_blueprint(_norm(b), analysis, phase.covers), log)
        self.store.save_ps_artifact(task_id, kind="phase_blueprint", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M2: {len(out.micro)} microfasi")
        return out

    # ── passi M3/M4 + qualificazione (PS4) ───────────────────────────────────

    def _known_cmd_ids(self) -> set[str]:
        spec = self.router.catalog.get("run_tests") if self.router else None
        if spec is None or not hasattr(spec.handler, "args"):
            return set()
        return set(spec.handler.args[1])

    def design_verification(self, task_id: str, phase: MacroPhase,
                            bp: PhaseBlueprint, projection: str,
                            log) -> VerificationBlueprint:
        known = self._known_cmd_ids()
        state = self.store.load_task(task_id)
        volatile = (f"{projection}\n[BLUEPRINT] {bp.model_dump_json()}"
                    f"\n[KNOWN TEST COMMANDS] {sorted(known)}")
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = VerificationDesigner(self.llm, self.assembler, self.router)
        out: VerificationBlueprint = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens)  # type: ignore
        out = self._repair_loop("M3", role, ctx, out, VerificationBlueprint,
                                lambda v: validate_verification(v, bp, known),
                                log)
        self.store.save_ps_artifact(task_id, kind="verification_blueprint",
                                    ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M3: {len(out.obligations)} obblighi")
        return out

    def author_tests(self, task_id: str, phase: MacroPhase, bp: PhaseBlueprint,
                     vbp: VerificationBlueprint, projection: str,
                     log) -> TestBundle:
        state = self.store.load_task(task_id)
        volatile = (f"{projection}\n[BLUEPRINT] {bp.model_dump_json()}"
                    f"\n[OBLIGATIONS] {vbp.model_dump_json()}")
        # smoke PS4.3: se un test_file degli obblighi ESISTE, M4 deve vederne
        # il contenuto per includerlo (la guardia di materializzazione rifiuta
        # i test persi) — senza il sorgente non potrebbe che inventare
        for tf in sorted({o.test_file for o in vbp.obligations}):
            existing = self.scope.root / tf
            if existing.is_file():
                volatile += (f"\n[EXISTING TEST FILE {tf}]\n"
                             + existing.read_text(encoding="utf-8",
                                                  errors="replace"))
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = TestAuthor(self.llm, self.assembler, self.router)
        out: TestBundle = role.run(
            ctx, max_tokens=self.cfg.plansys.test_author_max_tokens)  # type: ignore
        out = self._repair_loop("M4", role, ctx, out, TestBundle,
                                lambda b: validate_bundle(b, vbp), log,
                                max_tokens=self.cfg.plansys.test_author_max_tokens)
        self.store.save_ps_artifact(task_id, kind="test_bundle", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M4: {len(out.artifacts)} file di test")
        return out

    def materialize_tests(self, bundle: TestBundle, log) -> None:
        """Il CONTROL PLANE scrive i test (mai J): Scope dedicato ai soli path
        del bundle + syntax gate dei writer esistenti. Guardia (smoke PS4.3):
        sovrascrivere un test file esistente NON deve far sparire test — i
        nomi esistenti devono sopravvivere nel contenuto nuovo."""
        from redgiant.plansys.gates import _parse_tests
        from redgiant.tools import fs
        test_scope = Scope(self.scope.root, [a.path for a in bundle.artifacts])
        for a in bundle.artifacts:
            dest = self.scope.root / a.path
            if dest.is_file():
                old, _ = _parse_tests(dest.read_text(encoding="utf-8",
                                                     errors="replace"))
                new, _ = _parse_tests(a.content)
                dropped = sorted(set(old) - set(new))
                if dropped:
                    raise CompileFailed(
                        "materialize",
                        [f"{a.path}: existing tests would be DROPPED: {dropped} "
                         f"— the artifact must contain them plus the new ones"])
            res = fs.write_file(test_scope, a.path, a.content)
            if not res.ok:
                raise CompileFailed("materialize", [f"{a.path}: {res.error}"])
            log.line("compiler", f"test materializzato: {a.path}")

    def compile_phase(self, task_id: str, plan: MacroPlan, phase: MacroPhase,
                      log) -> tuple[PhaseBlueprint, VerificationBlueprint,
                                    TestBundle]:
        """La pipeline M1->M4 + Oracle Qualification (flusso §PS-A5)."""
        projection = self.projection(task_id, plan, phase)
        analysis = self.analyze(task_id, plan, phase, projection, log)
        bp = self.decompose(task_id, phase, analysis, projection, log)
        vbp = self.design_verification(task_id, phase, bp, projection, log)
        bundle = self.author_tests(task_id, phase, bp, vbp, projection, log)

        state = self.store.load_task(task_id)
        rounds = 0
        while True:
            try:
                self.materialize_tests(bundle, log)
            except CompileFailed as e:
                rounds += 1
                if rounds > 2:
                    raise
                log.line("gate", f"{phase.id} materializzazione KO: patch M4")
                ctx = RoleContext(task=state, subtask=None,
                                  volatile=f"[OBLIGATIONS] {vbp.model_dump_json()}")
                patch = self._request_patch(ctx, "test_author", e.problems,
                                            bundle.model_dump_json())
                bundle = TestBundle.model_validate_json(self._apply_patch(
                    TestBundle, bundle.model_dump_json(), patch))
                probs = validate_bundle(bundle, vbp)
                if probs:
                    raise CompileFailed("M4-patch", probs)
                self.store.save_ps_artifact(
                    task_id, kind="test_bundle", ref=phase.id,
                    payload_json=bundle.model_dump_json(), actor="phase_compiler")
                continue
            report = oracle_qualification_gate(
                vbp, bundle, bp, self.scope, self.router, task_id,
                mutation_probe=self.cfg.plansys.mutation_probe)
            self.store.log_ps_gate(
                task_id, gate="oracle_qualification", target=phase.id,
                ok=report.ok,
                checks_json=json.dumps([c.model_dump() for c in report.checks]))
            if report.ok:
                break
            failed = [c for c in report.checks if not c.ok]
            log.line("gate", f"{phase.id} oracle_qualification KO: "
                             f"{[c.name for c in failed][:6]}")
            rounds += 1
            if rounds > 2:
                raise CompileFailed("oracle_qualification",
                                    [f"{c.name}: {c.detail}" for c in failed])
            # routing della correzione: contenuto test -> M4; disegno prove -> M3
            m4_keys = (":exists", ":asserts", ":targets_contract", ":scope",
                       "bundle_covers")
            m4_issues = [f"{c.name}: {c.detail}" for c in failed
                         if any(k in c.name for k in m4_keys)]
            m3_issues = [f"{c.name}: {c.detail}" for c in failed
                         if not any(k in c.name for k in m4_keys)]
            # una patch INVALIDA (payload deforme, target ignoto, validatore
            # rosso) e' un round fallito, non un crash: si logga e si ritenta
            # (il tetto rounds fa da uscita deterministica, PS-D1)
            if m4_issues:
                try:
                    ctx = RoleContext(
                        task=state, subtask=None,
                        volatile=f"[OBLIGATIONS] {vbp.model_dump_json()}")
                    patch = self._request_patch(ctx, "test_author", m4_issues,
                                                bundle.model_dump_json())
                    cand = TestBundle.model_validate_json(self._apply_patch(
                        TestBundle, bundle.model_dump_json(), patch))
                    probs = validate_bundle(cand, vbp)
                    if probs:
                        raise ValueError("; ".join(probs)[:300])
                    bundle = cand
                    self.store.save_ps_artifact(
                        task_id, kind="test_bundle", ref=phase.id,
                        payload_json=bundle.model_dump_json(),
                        actor="phase_compiler")
                except (ValidationError, ValueError, json.JSONDecodeError) as e:
                    log.line("gate", f"patch M4 invalida: {str(e)[:120]}")
            if m3_issues:
                try:
                    ctx = RoleContext(
                        task=state, subtask=None,
                        volatile=f"[BLUEPRINT] {bp.model_dump_json()}")
                    patch = self._request_patch(ctx, "verification_designer",
                                                m3_issues, vbp.model_dump_json())
                    cand = VerificationBlueprint.model_validate_json(
                        self._apply_patch(VerificationBlueprint,
                                          vbp.model_dump_json(), patch))
                    probs = validate_verification(cand, bp, self._known_cmd_ids())
                    if probs:
                        raise ValueError("; ".join(probs)[:300])
                    vbp = cand
                    self.store.save_ps_artifact(
                        task_id, kind="verification_blueprint", ref=phase.id,
                        payload_json=vbp.model_dump_json(),
                        actor="phase_compiler")
                except (ValidationError, ValueError, json.JSONDecodeError) as e:
                    log.line("gate", f"patch M3 invalida: {str(e)[:120]}")

        write_plan_doc(self.cfg.paths.tasks_dir, task_id,
                       f"{phase.id}.blueprint",
                       render_blueprint(bp, vbp, analysis))
        log.line("compiler", f"{phase.id} qualificata: blueprint completo")
        return bp, vbp, bundle

    # ── meccanica delle correzioni (PS-D6) ───────────────────────────────────

    def _repair_loop(self, step: str, role, ctx: RoleContext, artifact: BaseModel,
                     model: type[BaseModel], validate, log,
                     max_tokens: int | None = None) -> BaseModel:
        if max_tokens is None:
            max_tokens = self.cfg.plansys.m_pass_max_tokens
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
            artifact = role.run(retry_ctx, max_tokens=max_tokens)
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
