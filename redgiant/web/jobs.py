"""JobQueue (piano F2.1, D7): UN worker thread, UNA inferenza alla volta.

La serialita' non e' un limite da nascondere ma un contratto da esporre: la GUI
mostra la coda. Un'eccezione in un job -> task failed, la coda sopravvive.
`cancel` e' cooperativo: l'Orchestrator lo onora al confine tra sottofasi
(uccidere un Worker a meta' patch lascerebbe il target sporco).

Config per-task: la GUI scrive data/tasks/<id>/task_config.json
(writable_globs, test_commands, plan opzionale) e il queue ricostruisce
Scope/Router/Orchestrator da li' — cosi' anche la ripresa post-riavvio
ha tutto cio' che serve su disco.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import traceback
from pathlib import Path

from redgiant.config import Config
from redgiant.core.orchestrator import Orchestrator, load_static_plan
from redgiant.llm.client import LlamaClient
from redgiant.prompts.assemble import PromptAssembler
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter, default_catalog

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_COMPOSE = Path(__file__).resolve().parents[2] / "docker" / "severino-sim" / "compose.yml"


def write_task_config(tasks_dir: Path, task_id: str, *, writable_globs: list[str],
                      test_commands: dict[str, list[str]],
                      plan: dict | None = None) -> None:
    d = tasks_dir / task_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "task_config.json").write_text(json.dumps({
        "writable_globs": writable_globs, "test_commands": test_commands,
        "plan": plan}), encoding="utf-8")


def read_task_config(tasks_dir: Path, task_id: str) -> dict:
    p = tasks_dir / task_id / "task_config.json"
    if not p.is_file():
        return {"writable_globs": [], "test_commands": {}, "plan": None}
    return json.loads(p.read_text(encoding="utf-8"))


class JobQueue:
    def __init__(self, cfg: Config, store: StateStore) -> None:
        self.cfg = cfg
        self.store = store
        self._q: "queue.Queue[str]" = queue.Queue()
        self._current: str | None = None
        self._lock = threading.Lock()
        self._started_container = False
        self._thread = threading.Thread(target=self._worker, daemon=True,
                                        name="redgiant-jobqueue")
        self._thread.start()
        # ripresa post-riavvio (feedback F2.5): i task queued/running nel DB
        # esistono solo li' — la coda in-memory muore col processo. Si riaccodano
        # (l'Orchestrator reclama le sottofasi running orfane).
        for t in self.store.list_tasks(200):
            if t["status"] in ("queued", "running"):
                self.submit(t["id"])

    # ── API ──────────────────────────────────────────────────────────────────

    def submit(self, task_id: str) -> None:
        with self._lock:
            if task_id == self._current or task_id in list(self._q.queue):
                return  # idempotente
        self._q.put(task_id)

    def cancel(self, task_id: str) -> bool:
        """Cooperativo: marca cancelled; l'Orchestrator lo onora tra sottofasi."""
        try:
            st = self.store.load_task(task_id)
        except KeyError:
            return False
        if st.status not in ("queued", "running", "blocked"):
            return False
        self.store.set_task_status(task_id, "cancelled", actor="user",
                                   error="cancelled from GUI")
        return True

    def current(self) -> str | None:
        return self._current

    def queue_snapshot(self) -> list[str]:
        return list(self._q.queue)

    # ── worker thread ────────────────────────────────────────────────────────

    def _worker(self) -> None:
        while True:
            task_id = self._q.get()
            with self._lock:
                self._current = task_id
            try:
                self._run_one(task_id)
            except Exception as e:  # la coda sopravvive sempre
                try:
                    self.store.set_task_status(
                        task_id, "failed", actor="jobqueue",
                        error=f"internal: {type(e).__name__}: {e}"[:400])
                except Exception:
                    pass
                traceback.print_exc()
            finally:
                with self._lock:
                    self._current = None
                self._q.task_done()

    def _run_one(self, task_id: str) -> None:
        state = self.store.load_task(task_id)
        if state.status == "cancelled":
            return
        llm = LlamaClient(self.cfg.llm, self.store)
        if not self._ensure_server(llm):
            self.store.set_task_status(
                task_id, "failed", actor="jobqueue",
                error=f"llama-server non raggiungibile su {self.cfg.llm.base_url} "
                      f"(profilo {self.cfg.profile_name})")
            return

        tc = read_task_config(self.cfg.paths.tasks_dir, task_id)
        scope = Scope(Path(state.target_dir), tc["writable_globs"])
        # F2 (richiesta utente): i comandi di test li trova il SISTEMA — scoperta
        # deterministica dal repo, la config esplicita dell'utente vince sul merge.
        from redgiant.tools.proc import discover_test_commands
        test_commands = {**discover_test_commands(scope.root,
                                                  self.cfg.security.shell_whitelist),
                         **tc["test_commands"]}

        def _persist(cmds: dict) -> None:
            p = self.cfg.paths.tasks_dir / task_id / "task_config.json"
            data = read_task_config(self.cfg.paths.tasks_dir, task_id)
            data["test_commands"] = cmds
            p.write_text(json.dumps(data), encoding="utf-8")

        catalog = default_catalog(self.cfg, scope, test_commands,
                                  persist_test_commands=_persist)
        if tc.get("approve_writes"):
            from dataclasses import replace
            for name in ("edit_file", "write_file", "write_patch"):
                if name in catalog:
                    catalog[name] = replace(catalog[name], requires_approval=True)
        router = ToolRouter(catalog, scope, self.store)
        orch = Orchestrator(self.cfg, self.store, llm, router,
                            PromptAssembler(_PROMPTS_DIR))
        if state.plan is None and tc.get("plan"):
            plan_path = self.cfg.paths.tasks_dir / task_id / "plan.json"
            plan_path.write_text(json.dumps(tc["plan"]), encoding="utf-8")
            load_static_plan(self.store, task_id, plan_path)
        try:
            orch.run_task(task_id)
        finally:
            self._release_server()

    # ── ciclo di vita del server (D7: modello residente per la durata del job) ─

    def _ensure_server(self, llm: LlamaClient) -> bool:
        if llm.health():
            return True
        if self.cfg.profile_name == "severino-sim" and _COMPOSE.is_file():
            subprocess.run(["docker", "compose", "-f", str(_COMPOSE), "up", "-d"],
                           capture_output=True, timeout=120)
            self._started_container = True
            import time
            for _ in range(40):
                time.sleep(3)
                if llm.health():
                    return True
        return llm.health()

    def _release_server(self) -> None:
        if self._started_container and self._q.empty():
            subprocess.run(["docker", "compose", "-f", str(_COMPOSE), "stop"],
                           capture_output=True, timeout=60)
            self._started_container = False
