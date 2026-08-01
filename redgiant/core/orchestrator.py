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
from redgiant.roles.worker import Worker
from redgiant.state.models import Plan, SubtaskSpec, TaskState
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter


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

        while True:
            state = self.store.load_task(task_id)
            if state.status in ("blocked", "cancelled"):
                log.line("orchestrator", f"stopping loop: task {state.status}")
                return state

            # F2.5: prima si guarda se c'e' ancora lavoro — un task che ha finito
            # si chiude e basta (chiedere un'estensione budget a task completato
            # e' successo davvero: mai piu')
            spec = self._next_subtask(state)
            if spec is None:
                return self._finalize(state)

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
                self.store.set_subtask_status(
                    task_id, spec.id, "completed", actor="orchestrator",
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
            self.store.set_task_status(
                task_id, "failed", actor="orchestrator",
                error=f"subtask {spec.id} failed after {attempts} retries; "
                      f"failed checks: {failed_checks}")
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
