"""Orchestrator v0 (piano F1.7): il motore deterministico minimo.

Esegue in sequenza le sottofasi di un piano STATICO (plans.version=0), applica
la verifica deterministica, aggiorna lo stato, si ferma bene. Le decisioni sono
volutamente banali (pass -> next; fail -> retry entro budget -> failed): la
sofisticazione e' il Supervisor (F4) e dovra' giustificarsi contro questa
semplicita' (D11). Il modello propone, l'Orchestrator decide (§7).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from redgiant.config import Config
from redgiant.core.budget import BudgetTracker
from redgiant.core.verify import Verdict, verify_subtask
from redgiant.llm.client import LlamaClient, LlmError
from redgiant.prompts.assemble import PromptAssembler
from redgiant.roles.base import RoleContext
from redgiant.roles.phase_designer import DesignRejected, PhaseDesigner
from redgiant.roles.planner import Planner, PlannerOutput, PlanRejected
from redgiant.roles.worker import Worker
from redgiant.state.models import Plan, PhaseSpec, SubtaskSpec, TaskState
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter

_MAX_REPLANS = 2  # F3.4: oltre, il piano e' il problema e si fallisce esplicitamente


class TaskLog:
    """Log leggibile per umani (F1.8, specsheet §20): data/tasks/<id>/task.log."""

    def __init__(self, tasks_dir: Path, task_id: str) -> None:
        d = tasks_dir / task_id
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / "task.log"

    def line(self, actor: str, msg: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} | {actor:<12} | {msg[:300]}\n")


class Orchestrator:
    def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                 router: ToolRouter, assembler: PromptAssembler) -> None:
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.router = router
        self.assembler = assembler

    # ── ciclo principale ─────────────────────────────────────────────────────

    def run_task(self, task_id: str) -> TaskState:
        state = self.store.load_task(task_id)
        log = TaskLog(self.cfg.paths.tasks_dir, task_id)
        tracker = BudgetTracker(self.store, state.budget, task_id)

        if state.status == "queued":
            self.store.set_task_status(task_id, "running", actor="orchestrator")
        self._reclaim_orphans(task_id, log)

        worker = Worker(self.llm, self.assembler, self.router)

        # F3.3: se il piano non esiste, lo genera il Planner (v1: piano dinamico).
        # Gate D11 (A/B 2026-08-02: baseline 9/10 vs planner 2/10): Planner OFF
        # di default -> piano ingenuo deterministico, zero chiamate LLM.
        if state.plan is None:
            if not self.cfg.planner_enabled:
                self._naive_plan(task_id, log)
            else:
                try:
                    self._generate_plan(task_id, log)
                except (PlanRejected, LlmError) as e:
                    self.store.set_task_status(task_id, "failed", actor="planner",
                                               error=f"planner failed: {e}"[:400])
                    log.line("planner", f"FAILED: {e}")
                    return self.store.load_task(task_id)

        replans = 0
        design_rounds: dict[str, int] = {}  # tetto strutturale anti-loop del designer
        while True:
            state = self.store.load_task(task_id)
            if state.status in ("blocked", "cancelled"):
                log.line("orchestrator", f"stopping loop: task {state.status}")
                return state

            # F2.5: prima si guarda se c'e' ancora lavoro — un task che ha finito
            # si chiude e basta (chiedere un'estensione budget a task completato
            # e' successo davvero: mai piu')
            phase = self._eligible_phase(state)
            if phase is None:
                return self._finalize(state)

            # F3.3: espansione LAZY — solo la fase corrente viene dettagliata (§25.5)
            if not self._phase_subtasks(state.id, phase.id):
                design_rounds[phase.id] = design_rounds.get(phase.id, 0) + 1
                if design_rounds[phase.id] > 3:
                    self.store.set_task_status(
                        task_id, "failed", actor="orchestrator",
                        error=f"design loop on phase {phase.id}: "
                              f"{design_rounds[phase.id]} rounds")
                    log.line("orchestrator", f"design loop su {phase.id} -> failed")
                    return self.store.load_task(task_id)
                try:
                    self._design_phase(task_id, phase, log)
                except (DesignRejected, LlmError) as e:
                    replans += 1
                    if replans > _MAX_REPLANS or not self._replan(
                            task_id, f"phase {phase.id} design failed: {e}", log):
                        self.store.set_task_status(
                            task_id, "failed", actor="phase_designer",
                            error=f"design of {phase.id} failed: {e}"[:400])
                        return self.store.load_task(task_id)
                continue

            spec = self._next_subtask_in_phase(state.id, phase.id)
            if spec is None:
                if self._phase_done(state.id, phase.id):
                    continue  # fase chiusa: il giro dopo prende la successiva
                # fase con sottofasi failed e nessuna lavorabile (es. ripresa)
                replans += 1
                if replans <= _MAX_REPLANS and self._replan(
                        task_id, f"phase {phase.id} has failed subtasks and no "
                                 f"workable ones", log):
                    continue
                self.store.set_task_status(
                    task_id, "failed", actor="orchestrator",
                    error=f"phase {phase.id} unrecoverable; replans exhausted")
                return self.store.load_task(task_id)

            key = tracker.exceeded()
            if key is not None:
                outcome = self._handle_budget_exhaustion(task_id, key, tracker, log)
                if outcome is not None:
                    return outcome
                # estensione concessa: budget ricaricato, si prosegue
                tracker = BudgetTracker(self.store,
                                        self.store.load_task(task_id).budget, task_id)

            verdict = self._execute_subtask(state, spec, worker, log)
            if verdict is None:  # blocked (approvazione): il loop riprendera' dopo
                self.store.set_subtask_status(task_id, spec.id, "blocked",
                                              actor="orchestrator")
                return self.store.load_task(task_id)

            if verdict.verdict == "pass":
                warned = any(not c.ok for c in verdict.checks)
                self.store.set_subtask_status(
                    task_id, spec.id,
                    "completed_with_warnings" if warned else "completed",
                    actor="orchestrator",
                    result={"verdict": verdict.model_dump()})
                (self.cfg.paths.tasks_dir / task_id / f"resume_{spec.id}.ctx"
                 ).unlink(missing_ok=True)
                log.line("verify", f"{spec.id} PASS")
                continue

            _, _, attempts = self.store.get_subtask(task_id, spec.id)
            if attempts < state.budget.max_retries_per_subtask:
                self.store.set_subtask_status(
                    task_id, spec.id, "retry", actor="orchestrator",
                    result={"verdict": verdict.model_dump()})
                log.line("verify", f"{spec.id} FAIL -> retry ({attempts + 1})")
                continue

            self.store.set_subtask_status(task_id, spec.id, "failed",
                                          actor="orchestrator",
                                          result={"verdict": verdict.model_dump()})
            failed_checks = [c.name for c in verdict.checks if not c.ok]
            # F3.4: una sottofase esaurita non uccide il task — prima si prova a
            # RIPIANIFICARE (il piano potrebbe essere il problema, specsheet §12)
            replans += 1
            if replans <= _MAX_REPLANS and self._replan(
                    task_id, f"subtask {spec.id} failed after {attempts} retries; "
                             f"failed checks: {failed_checks}", log):
                continue
            self.store.set_task_status(
                task_id, "failed", actor="orchestrator",
                error=f"subtask {spec.id} failed after {attempts} retries; "
                      f"failed checks: {failed_checks}; replans exhausted")
            log.line("orchestrator", f"task FAILED at {spec.id}: {failed_checks}")
            return self.store.load_task(task_id)

    # ── passi ────────────────────────────────────────────────────────────────

    def _next_subtask(self, state: TaskState) -> SubtaskSpec | None:
        for row in self.store.list_subtasks(state.id):
            if row["status"] in ("running", "retry", "repair", "pending"):
                spec, _, _ = self.store.get_subtask(state.id, row["subtask_id"])
                return spec
        return None

    def _execute_subtask(self, state: TaskState, spec: SubtaskSpec,
                         worker: Worker, log: TaskLog) -> Verdict | None:
        """Worker -> verifica. None = bloccato in attesa dell'umano."""
        task_id = state.id
        _, prev_status, attempts = self.store.get_subtask(task_id, spec.id)
        self.store.set_subtask_status(task_id, spec.id, "running", actor="orchestrator")
        log.line("worker", f"start {spec.id} '{spec.title}' (attempt {attempts + 1})")

        volatile = f"Subtask spec: {spec.model_dump_json()}"
        answer = self.store.latest_clarification_answer(task_id)
        if answer:
            volatile += f"\n[USER ANSWER] {answer}"
        if attempts > 0:
            prev = next((r["result"] for r in self.store.list_subtasks(task_id)
                         if r["subtask_id"] == spec.id and r["result"]), None)
            if prev:
                failed = [c for c in json.loads(prev)["verdict"]["checks"] if not c["ok"]]
                volatile += ("\n[PREVIOUS ATTEMPT FAILED] fix these specific failures, "
                             "do not repeat the same approach: "
                             + json.dumps(failed[:5]))

        ctx = RoleContext(task=state, subtask=spec, volatile=volatile)
        resume_file = self.cfg.paths.tasks_dir / task_id / f"resume_{spec.id}.ctx"
        try:
            report = worker.run(ctx, max_steps=self.cfg.worker_max_steps,
                                step_max_tokens=self.cfg.worker_step_max_tokens,
                                step_log=lambda m: log.line("step", m),
                                resume_file=resume_file)
        except LlmError as e:
            log.line("worker", f"{spec.id} LLM error: {e}")
            from redgiant.roles.worker import FinishReport
            report = FinishReport(status="blocked", summary=f"llm error: {e}"[:590],
                                  evidence=[], verification_requested=[])

        if report.status == "blocked" and "approval" in report.summary:
            log.line("worker", f"{spec.id} blocked: {report.summary}")
            return None

        log.line("worker", f"{spec.id} finished: {report.status} - {report.summary[:120]}")
        verdict = verify_subtask(spec, report, self.router.scope, self.router, task_id)
        return verdict

    def _finalize(self, state: TaskState) -> TaskState:
        rows = self.store.list_subtasks(state.id)
        done = [r for r in rows if r["status"] in ("completed", "completed_with_warnings")]
        if rows and len(done) == len(rows):
            self.store.set_task_status(state.id, "completed", actor="orchestrator")
        elif done:
            self.store.set_task_status(state.id, "partial", actor="orchestrator",
                                       error="not all subtasks completed")
        else:
            self.store.set_task_status(state.id, "failed", actor="orchestrator",
                                       error="no subtask completed")
        return self.store.load_task(state.id)

    # ── pianificazione (F3) ──────────────────────────────────────────────────

    def _naive_plan(self, task_id: str, log: TaskLog) -> None:
        """Gate D11: col Planner spento il piano e' quello della baseline vincente
        dell'A/B — una fase, una sottofase do-everything, verifica = primo cmd di
        test noto. Deterministico, zero token."""
        state = self.store.load_task(task_id)
        first_cmd = next(iter(sorted(self._test_cmd_ids())), None)
        self.store.save_plan(task_id, Plan(
            version=0, goal=state.request[:290],
            success_criteria=["verification passes"],
            phases=[PhaseSpec(id="P1", title="Do the task", depends_on=[],
                              completion_criteria=["verification passes"])]),
            actor="orchestrator", reason="naive (planner disabled, D11)")
        self.store.upsert_subtask(task_id, SubtaskSpec(
            id="P1.S1", phase_id="P1", title="Do the task",
            objective=state.request, inputs=[], tools=[],
            expected_outputs=[], completion_criteria=["verification passes"],
            verification=[first_cmd] if first_cmd else []), actor="orchestrator")
        log.line("orchestrator", "piano ingenuo (planner OFF, verdetto D11): "
                                 "1 fase, 1 sottofase")

    def _generate_plan(self, task_id: str, log: TaskLog) -> None:
        state = self.store.load_task(task_id)
        volatile = ("Produce the global plan for the task.\n"
                    f"Repository files:\n{self._repo_listing()}\n"
                    f"Available test command ids: {sorted(self._test_cmd_ids())}"
                    f"{self._test_excerpts()}")
        planner = Planner(self.llm, self.assembler, self.router)
        out = planner.run(RoleContext(task=state, subtask=None, volatile=volatile))
        self.store.save_plan(task_id, Plan(version=1, goal=out.goal,
                                           success_criteria=out.success_criteria,
                                           phases=out.phases),
                             actor="planner", reason="initial")
        log.line("planner", f"plan v1: {len(out.phases)} fasi — {out.goal[:80]}")

    def _design_phase(self, task_id: str, phase: PhaseSpec, log: TaskLog) -> None:
        state = self.store.load_task(task_id)
        done = [r["subtask_id"] for r in self.store.list_subtasks(task_id)
                if r["status"].startswith("completed")]
        volatile = (f"Current phase to expand: {phase.model_dump_json()}\n"
                    f"Already completed subtasks: {done}\n"
                    f"Repository files:\n{self._repo_listing()}\n"
                    f"Available test command ids: {sorted(self._test_cmd_ids())} "
                    f"(use them in verification)"
                    f"{self._test_excerpts()}")
        designer = PhaseDesigner(self.llm, self.assembler, self.router)
        out = designer.run(RoleContext(task=state, subtask=None, volatile=volatile),
                           current_phase_id=phase.id,
                           known_cmd_ids=self._test_cmd_ids())
        for st in out.subtasks:
            self.store.upsert_subtask(task_id, st, actor="phase_designer")
        log.line("designer", f"{phase.id}: {len(out.subtasks)} sottofasi")

    def _replan(self, task_id: str, reason: str, log: TaskLog) -> bool:
        """F3.4: nuova versione del piano; le fasi completate sono IMMUTABILI."""
        if not self.cfg.planner_enabled:
            # gate D11: senza Planner niente replanning — si fallisce esplicito
            log.line("orchestrator", "replanning saltato: planner OFF (D11)")
            return False
        state = self.store.load_task(task_id)
        if state.plan is None:
            return False
        completed = [p for p in state.plan.phases if self._phase_done(task_id, p.id)]
        keep_ids = [p.id for p in completed]
        volatile = ("[REPLANNING] The current plan is no longer valid.\n"
                    f"Reason: {reason}\n"
                    "COMPLETED phases (keep as-is, same id and title): "
                    + json.dumps([p.model_dump() for p in completed]) + "\n"
                    f"Old plan: {state.plan.model_dump_json()}\n"
                    f"Repository files:\n{self._repo_listing()}\n"
                    f"Available test command ids: {sorted(self._test_cmd_ids())}"
                    f"{self._test_excerpts()}\n"
                    "Produce a corrected plan; do not repeat the failed approach.")
        planner = Planner(self.llm, self.assembler, self.router)
        try:
            out = planner.run(RoleContext(task=state, subtask=None, volatile=volatile),
                              required_phase_ids=keep_ids)
        except (PlanRejected, LlmError) as e:
            log.line("planner", f"replanning FAILED: {e}"[:200])
            return False
        newv = state.plan.version + 1
        self.store.save_plan(task_id, Plan(version=newv, goal=out.goal,
                                           success_criteria=out.success_criteria,
                                           phases=out.phases),
                             actor="planner", reason=reason[:200])
        # sottofasi non-completate delle fasi NON conservate -> skipped: il piano
        # nuovo le ridisegnera'; le completate restano intoccabili
        for r in self.store.list_subtasks(task_id):
            if not r["status"].startswith("completed") and r["phase_id"] not in keep_ids:
                self.store.set_subtask_status(task_id, r["subtask_id"], "skipped",
                                              actor="planner")
        log.line("planner", f"replanning -> plan v{newv} ({reason[:80]})")
        return True

    def _eligible_phase(self, state: TaskState) -> PhaseSpec | None:
        """Prima fase non completata con tutte le dipendenze completate (§10)."""
        if state.plan is None:
            return None
        for p in state.plan.phases:
            if self._phase_done(state.id, p.id):
                continue
            if all(self._phase_done(state.id, d) for d in p.depends_on):
                return p
        return None

    def _phase_done(self, task_id: str, phase_id: str) -> bool:
        rows = self._phase_subtasks(task_id, phase_id)
        return bool(rows) and all(r["status"].startswith("completed") for r in rows)

    def _phase_subtasks(self, task_id: str, phase_id: str) -> list[dict]:
        return [r for r in self.store.list_subtasks(task_id)
                if r["phase_id"] == phase_id and r["status"] != "skipped"]

    def _next_subtask_in_phase(self, task_id: str, phase_id: str) -> SubtaskSpec | None:
        for r in self._phase_subtasks(task_id, phase_id):
            if r["status"] in ("running", "retry", "repair", "pending"):
                spec, _, _ = self.store.get_subtask(task_id, r["subtask_id"])
                return spec
        return None

    def _repo_listing(self, max_files: int = 40) -> str:
        root = self.router.scope.root
        out: list[str] = []
        for p in sorted(root.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(root).as_posix()
            if any(seg in rel for seg in (".git/", "__pycache__/", ".venv/")):
                continue
            # batch20 n.5 (plansys): artefatti di runtime del task dentro la
            # workdir — inquinano i prompt e variano a ogni run
            # (F3b.1: idem la cache http — e' runtime, non repo)
            if (rel.startswith("tasks/") or rel.endswith(".db")
                    or rel.startswith(".rg_http_cache/")):
                continue
            out.append(rel)
            if len(out) >= max_files:
                out.append("... (truncated)")
                break
        return "\n".join(out) or "(empty)"

    def _test_excerpts(self, max_files: int = 2, max_lines: int = 60) -> str:
        """F3 (smoke T009): i test sono il CONTRATTO — il Designer deve vederli,
        o inventa nomi di API che i test smentiranno (slugify vs slug: 108
        chiamate bruciate). Selezione grezza; la selezione vera e' F5."""
        root = self.router.scope.root
        picked = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and "test" in p.name.lower() and p.suffix in (".py", ".php"):
                picked.append(p)
                if len(picked) >= max_files:
                    break
        if not picked:
            return ""
        out = ["\nKey test file excerpts (this is the CONTRACT: copy identifiers "
               "EXACTLY from here, never invent names):"]
        for p in picked:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            body = "\n".join(lines[:max_lines])
            out.append(f"--- {p.relative_to(root).as_posix()} ---\n{body}")
        return "\n".join(out)

    def _test_cmd_ids(self) -> set[str]:
        spec = self.router.catalog.get("run_tests")
        if spec is None or not hasattr(spec.handler, "args"):
            return set()
        return set(spec.handler.args[1])

    # ── ausiliari ────────────────────────────────────────────────────────────

    def _reclaim_orphans(self, task_id: str, log: TaskLog) -> None:
        """Ripresa (F1.7): una sottofase 'running' di un processo morto torna pending."""
        for row in self.store.list_subtasks(task_id):
            if row["status"] == "running":
                self.store.set_subtask_status(task_id, row["subtask_id"], "pending",
                                              actor="orchestrator")
                log.line("orchestrator",
                         f"reclaimed orphan running subtask {row['subtask_id']} -> pending")

    def _handle_budget_exhaustion(self, task_id: str, key: str,
                                  tracker: BudgetTracker, log: TaskLog) -> TaskState | None:
        """F2.5 (richiesta utente): budget esaurito = checkpoint di consenso, non
        ghigliottina. Ritorna None se l'estensione e' stata concessa (si prosegue);
        altrimenti lo stato terminale/bloccato."""
        taken = self.store.take_budget_extension(task_id)
        if taken is not None:
            answer, ext_key, add = taken
            if answer == "yes" and add > 0:
                self.store.extend_budget(task_id, ext_key, add)
                log.line("budget", f"estensione concessa: {ext_key} +{add}")
                return None
            log.line("budget", "estensione rifiutata dall'utente")
            return self._stop_on_budget(task_id, key, log)
        add = max(tracker.budget.max_total_tokens // 2, 8000) if key == "tokens" else \
            max(getattr(tracker.budget, f"max_{key}", 0) // 2, 10)
        import json as _json
        self.store.add_approval(task_id, kind="irreversible_op",
                                payload=_json.dumps({"tool": "extend_budget",
                                                     "args": {"key": key, "add": add}}))
        self.store.set_task_status(task_id, "blocked", actor="budget",
                                   error=f"budget '{key}' esaurito: in attesa della tua "
                                         f"decisione (estendere di {add}?)")
        log.line("budget", f"budget '{key}' esaurito -> chiedo estensione (+{add})")
        return self.store.load_task(task_id)

    def _stop_on_budget(self, task_id: str, key: str, log: TaskLog) -> TaskState:
        rows = self.store.list_subtasks(task_id)
        done = [r for r in rows if r["status"].startswith("completed")]
        status = "partial" if done else "failed"
        self.store.set_task_status(
            task_id, status, actor="budget",
            error=f"budget '{key}' exceeded; completed {len(done)}/{len(rows)} subtasks")
        log.line("budget", f"budget '{key}' exceeded -> {status}")
        return self.store.load_task(task_id)


def load_static_plan(store: StateStore, task_id: str, plan_file: Path) -> None:
    """F1: carica il piano statico (plans.version=0) e le sue sottofasi."""
    data = json.loads(plan_file.read_text(encoding="utf-8"))
    plan = Plan.model_validate({**data.get("plan", data), "version": 0})
    store.save_plan(task_id, plan, actor="system", reason="static plan (F1)")
    for st in data.get("subtasks", []):
        store.upsert_subtask(task_id, SubtaskSpec.model_validate(st), actor="system")
