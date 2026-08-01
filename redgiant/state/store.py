"""StateStore: unico punto di accesso al database (piano F1.1, DDL §A5).

Nessun SQL fuori da questo modulo. Ogni mutazione è in transazione e porta
l'attore. Gli artefatti grandi NON vanno nel DB ma su disco in data/tasks/<id>/
(specsheet §8). Connessione per-operazione: SQLite in WAL regge bene e si evita
ogni problema di threading con la GUI (F2).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from redgiant.state.models import (
    Budget, BudgetUsed, LlmCallRow, Plan, SubtaskSpec, SubtaskStatus,
    TaskState, TaskStatus, ToolCallRow,
)

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tasks (
  id          TEXT PRIMARY KEY,
  created_at  TEXT NOT NULL,
  request     TEXT NOT NULL,
  target_dir  TEXT NOT NULL,
  domain      TEXT NOT NULL DEFAULT 'coding',
  status      TEXT NOT NULL CHECK (status IN
              ('queued','running','blocked','completed','partial','failed','cancelled')),
  profile     TEXT NOT NULL,
  pipeline    TEXT,
  error       TEXT
);
CREATE TABLE IF NOT EXISTS plans (
  task_id  TEXT NOT NULL REFERENCES tasks(id),
  version  INTEGER NOT NULL,
  actor    TEXT NOT NULL,
  reason   TEXT NOT NULL,
  json     TEXT NOT NULL,
  PRIMARY KEY (task_id, version)
);
CREATE TABLE IF NOT EXISTS subtasks (
  task_id     TEXT NOT NULL REFERENCES tasks(id),
  subtask_id  TEXT NOT NULL,
  phase_id    TEXT NOT NULL,
  title       TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN
              ('pending','running','completed','completed_with_warnings',
               'retry','repair','blocked','failed','skipped')),
  spec        TEXT NOT NULL,
  result      TEXT,
  attempts    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (task_id, subtask_id)
);
CREATE TABLE IF NOT EXISTS llm_calls (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id       TEXT NOT NULL,
  subtask_id    TEXT,
  role          TEXT NOT NULL,
  schema_name   TEXT,
  t_start       TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL,
  cached_tokens INTEGER NOT NULL,
  gen_tokens    INTEGER NOT NULL,
  prefill_ms    REAL NOT NULL,
  gen_ms        REAL NOT NULL,
  outcome       TEXT NOT NULL CHECK (outcome IN ('ok','timeout','error','invalid'))
);
CREATE TABLE IF NOT EXISTS tool_calls (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id     TEXT NOT NULL,
  subtask_id  TEXT,
  tool        TEXT NOT NULL,
  args        TEXT NOT NULL,
  ok          INTEGER NOT NULL,
  evidence    TEXT NOT NULL,
  duration_ms REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  actor      TEXT NOT NULL,
  decision   TEXT NOT NULL,
  reason     TEXT NOT NULL,
  target     TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budgets (
  task_id   TEXT NOT NULL,
  key       TEXT NOT NULL CHECK (key IN ('tokens','tool_calls','retries','wall_s')),
  limit_val INTEGER NOT NULL,
  used      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (task_id, key)
);
CREATE TABLE IF NOT EXISTS eval_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  profile     TEXT NOT NULL,
  git_ref     TEXT NOT NULL,
  report_path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id  TEXT NOT NULL,
  kind     TEXT NOT NULL CHECK (kind IN ('irreversible_op','clarification')),
  payload  TEXT NOT NULL,
  status   TEXT NOT NULL CHECK (status IN ('pending','answered','expired')),
  answer   TEXT
);
CREATE TABLE IF NOT EXISTS checkpoints (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('post_plan','post_subtask','pre_risky','pre_replan')),
  git_ref    TEXT,
  slot_file  TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  signals    TEXT NOT NULL,
  classifier TEXT,
  pipeline   TEXT NOT NULL,
  outcome    TEXT
);
CREATE INDEX IF NOT EXISTS idx_subtasks_status ON subtasks(task_id, status);
CREATE INDEX IF NOT EXISTS idx_llm_calls_task  ON llm_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_st   ON tool_calls(task_id, subtask_id);
CREATE INDEX IF NOT EXISTS idx_approvals_pend  ON approvals(status);
"""

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid() -> str:
    """ULID: 48 bit di timestamp ms + 80 bit random, base32 Crockford (ordinabile)."""
    ts = int(time.time() * 1000)
    rnd = int.from_bytes(os.urandom(10), "big")
    n = (ts << 80) | rnd
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[n & 0x1F])
        n >>= 5
    return "".join(reversed(chars))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:  # transazione: commit su successo, rollback su eccezione
                yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    # ── tasks ────────────────────────────────────────────────────────────────

    def create_task(self, request: str, target_dir: str, profile: str, budget: Budget) -> str:
        task_id = _ulid()
        with self._conn() as c:
            c.execute(
                "INSERT INTO tasks (id, created_at, request, target_dir, status, profile)"
                " VALUES (?,?,?,?, 'queued', ?)",
                (task_id, _now(), request, target_dir, profile))
            for key, limit in (("tokens", budget.max_total_tokens),
                               ("tool_calls", budget.max_tool_calls),
                               ("retries", budget.max_retries_per_subtask),
                               ("wall_s", budget.max_wall_s)):
                c.execute("INSERT INTO budgets (task_id, key, limit_val) VALUES (?,?,?)",
                          (task_id, key, limit))
        return task_id

    def load_task(self, task_id: str) -> TaskState:
        with self._conn() as c:
            row = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            plan_row = c.execute(
                "SELECT json FROM plans WHERE task_id=? ORDER BY version DESC LIMIT 1",
                (task_id,)).fetchone()
            plan = Plan.model_validate_json(plan_row["json"]) if plan_row else None
            # sottofase corrente derivata (unica fonte di verita': la tabella subtasks)
            cur = c.execute(
                "SELECT subtask_id, phase_id FROM subtasks WHERE task_id=? AND status IN"
                " ('running','retry','repair') ORDER BY rowid LIMIT 1", (task_id,)).fetchone()
            if cur is None:
                cur = c.execute(
                    "SELECT subtask_id, phase_id FROM subtasks WHERE task_id=? AND"
                    " status='pending' ORDER BY rowid LIMIT 1", (task_id,)).fetchone()
            budget = self._budget(c, task_id)
        return TaskState(
            id=row["id"], request=row["request"], target_dir=row["target_dir"],
            domain=row["domain"], status=row["status"], plan=plan,
            current_phase=cur["phase_id"] if cur else None,
            current_subtask=cur["subtask_id"] if cur else None,
            budget=budget, used=self.budget_used(task_id))

    def list_tasks(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, created_at, request, domain, status, profile, pipeline, error"
                " FROM tasks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def set_task_status(self, task_id: str, status: TaskStatus, *, actor: str,
                        error: str | None = None) -> None:
        with self._conn() as c:
            n = c.execute("UPDATE tasks SET status=?, error=? WHERE id=?",
                          (status, error, task_id)).rowcount
            if n == 0:
                raise KeyError(task_id)
            self._decision(c, task_id, actor, f"task_status={status}",
                           error or "status change", None)

    # ── plan e subtasks ──────────────────────────────────────────────────────

    def save_plan(self, task_id: str, plan: Plan, *, actor: str, reason: str) -> None:
        with self._conn() as c:
            row = c.execute("SELECT MAX(version) AS v FROM plans WHERE task_id=?",
                            (task_id,)).fetchone()
            version = plan.version if row["v"] is None else max(plan.version, row["v"] + 1)
            payload = plan.model_copy(update={"version": version})
            c.execute("INSERT INTO plans (task_id, version, actor, reason, json)"
                      " VALUES (?,?,?,?,?)",
                      (task_id, version, actor, reason, payload.model_dump_json()))

    def upsert_subtask(self, task_id: str, spec: SubtaskSpec, *, actor: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO subtasks (task_id, subtask_id, phase_id, title, status, spec)"
                " VALUES (?,?,?,?, 'pending', ?)"
                " ON CONFLICT(task_id, subtask_id) DO UPDATE SET"
                " phase_id=excluded.phase_id, title=excluded.title, spec=excluded.spec",
                (task_id, spec.id, spec.phase_id, spec.title, spec.model_dump_json()))
            self._decision(c, task_id, actor, f"upsert_subtask={spec.id}", spec.title, spec.id)

    def get_subtask(self, task_id: str, subtask_id: str) -> tuple[SubtaskSpec, SubtaskStatus, int]:
        with self._conn() as c:
            r = c.execute("SELECT spec, status, attempts FROM subtasks WHERE task_id=? AND"
                          " subtask_id=?", (task_id, subtask_id)).fetchone()
        if r is None:
            raise KeyError((task_id, subtask_id))
        return SubtaskSpec.model_validate_json(r["spec"]), r["status"], r["attempts"]

    def list_subtasks(self, task_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT subtask_id, phase_id, title, status, attempts, result FROM subtasks"
                " WHERE task_id=? ORDER BY rowid", (task_id,)).fetchall()
        return [dict(r) for r in rows]

    def set_subtask_status(self, task_id: str, subtask_id: str, status: SubtaskStatus,
                           *, actor: str, result: dict | None = None) -> None:
        bump = 1 if status in ("retry", "repair") else 0
        with self._conn() as c:
            n = c.execute(
                "UPDATE subtasks SET status=?, attempts=attempts+?,"
                " result=COALESCE(?, result) WHERE task_id=? AND subtask_id=?",
                (status, bump, json.dumps(result) if result is not None else None,
                 task_id, subtask_id)).rowcount
            if n == 0:
                raise KeyError((task_id, subtask_id))
            self._decision(c, task_id, actor, f"subtask_status={status}", "", subtask_id)

    # ── approvals (schema F2; scrittura gia' necessaria al ToolRouter F1.4) ──

    def add_approval(self, task_id: str, *, kind: str, payload: str) -> int:
        with self._conn() as c:
            cur = c.execute("INSERT INTO approvals (task_id, kind, payload, status)"
                            " VALUES (?,?,?, 'pending')", (task_id, kind, payload))
            return int(cur.lastrowid)

    def pending_approvals(self, task_id: str | None = None) -> list[dict]:
        q = "SELECT id, task_id, kind, payload, status FROM approvals WHERE status='pending'"
        args: tuple = ()
        if task_id is not None:
            q += " AND task_id=?"
            args = (task_id,)
        with self._conn() as c:
            return [dict(r) for r in c.execute(q, args).fetchall()]

    def answer_approval(self, approval_id: int, answer: str) -> str:
        """Risponde a una richiesta pending; ritorna il task_id. KeyError se assente,
        ValueError se gia' risposta (409 in GUI)."""
        with self._conn() as c:
            row = c.execute("SELECT task_id, status FROM approvals WHERE id=?",
                            (approval_id,)).fetchone()
            if row is None:
                raise KeyError(approval_id)
            if row["status"] != "pending":
                raise ValueError("already answered")
            c.execute("UPDATE approvals SET status='answered', answer=? WHERE id=?",
                      (answer, approval_id))
            self._decision(c, row["task_id"], "user", "approval_answer", answer,
                           str(approval_id))
            return row["task_id"]

    def list_grants(self, task_id: str | None = None) -> list[dict]:
        """Le concessioni attive (answered): visibili e ribaltabili dall'utente (F2.5)."""
        q = ("SELECT id, task_id, kind, payload, answer FROM approvals"
             " WHERE status='answered' AND kind='irreversible_op'")
        args: tuple = ()
        if task_id is not None:
            q += " AND task_id=?"
            args = (task_id,)
        with self._conn() as c:
            return [dict(r) for r in c.execute(q + " ORDER BY id DESC", args).fetchall()]

    def override_approval(self, approval_id: int, answer: str | None) -> str:
        """Ribalta o revoca una grant (richiesta utente: 'devo poter overriddare il no').
        answer 'yes'/'no' = nuova risposta; None = revoca (expired: si richiedera')."""
        with self._conn() as c:
            row = c.execute("SELECT task_id, status FROM approvals WHERE id=?",
                            (approval_id,)).fetchone()
            if row is None:
                raise KeyError(approval_id)
            if row["status"] != "answered":
                raise ValueError("not an active grant")
            if answer is None:
                c.execute("UPDATE approvals SET status='expired' WHERE id=?", (approval_id,))
                self._decision(c, row["task_id"], "user", "grant_revoked", "", str(approval_id))
            else:
                c.execute("UPDATE approvals SET answer=? WHERE id=?", (answer, approval_id))
                self._decision(c, row["task_id"], "user", "grant_override", answer,
                               str(approval_id))
            return row["task_id"]

    def consume_matching_approval(self, task_id: str, tool: str, args_json: str) -> str | None:
        """F2.3: alla ri-esecuzione di un tool sospeso, consuma l'approvazione risposta
        che matcha; ritorna la risposta ('yes'/'no') o None.

        Match su (tool, path) e consenso PERMANENTE per il task (feedback F2.5,
        secondo giro): approvare "scrivi su stack.py" vale per TUTTO il task — il
        modello deve poter iterare sul file concesso (correggere un edit sbagliato
        richiede un'altra scrittura: ri-chiedere ogni volta = riavvii che bruciano
        budget mentre si aspetta l'umano, osservato dal vivo). Un 'no' e' permanente
        allo stesso modo. La riga resta 'answered': e' una GRANT, non un gettone.
        Fallback su args interi se il tool non ha 'path'."""
        args = json.loads(args_json)
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, payload, answer FROM approvals WHERE task_id=? AND"
                " kind='irreversible_op' AND status='answered'", (task_id,)).fetchall()
            write_family = {"edit_file", "write_file", "write_patch"}
            for r in rows:
                p = json.loads(r["payload"])
                p_tool = p.get("tool")
                # F2.5: stessa famiglia di rischio = stessa grant — approvare la
                # scrittura su un file vale per TUTTI i tool di scrittura su quel file
                same_tool = (p_tool == tool or
                             (p_tool in write_family and tool in write_family))
                if not same_tool:
                    continue
                p_args = p.get("args") or {}
                same_path = ("path" in p_args and "path" in args
                             and p_args["path"] == args["path"])
                same_all = json.dumps(p_args, sort_keys=True) == json.dumps(args, sort_keys=True)
                if same_path or same_all:
                    return r["answer"]
        return None

    def latest_clarification_answer(self, task_id: str) -> str | None:
        with self._conn() as c:
            r = c.execute(
                "SELECT answer FROM approvals WHERE task_id=? AND kind='clarification'"
                " AND status='answered' ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
        return r["answer"] if r else None

    # ── log e budget ─────────────────────────────────────────────────────────

    def add_decision(self, task_id: str, *, actor: str, decision: str, reason: str,
                     target: str | None = None) -> None:
        with self._conn() as c:
            self._decision(c, task_id, actor, decision, reason, target)

    def log_llm_call(self, task_id: str, row: LlmCallRow) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO llm_calls (task_id, subtask_id, role, schema_name, t_start,"
                " prompt_tokens, cached_tokens, gen_tokens, prefill_ms, gen_ms, outcome)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, row.subtask_id, row.role, row.schema_name, row.t_start,
                 row.prompt_tokens, row.cached_tokens, row.gen_tokens,
                 row.prefill_ms, row.gen_ms, row.outcome))

    def log_tool_call(self, task_id: str, row: ToolCallRow) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO tool_calls (task_id, subtask_id, tool, args, ok, evidence,"
                " duration_ms) VALUES (?,?,?,?,?,?,?)",
                (task_id, row.subtask_id, row.tool, json.dumps(row.args), int(row.ok),
                 json.dumps(row.evidence), row.duration_ms))

    def extend_budget(self, task_id: str, key: str, add: int) -> None:
        """F2.5 (richiesta utente): il budget si estende su consenso, non e' una ghigliottina."""
        with self._conn() as c:
            c.execute("UPDATE budgets SET limit_val = limit_val + ? WHERE task_id=? AND key=?",
                      (add, task_id, key))
            self._decision(c, task_id, "user", f"budget_extended:{key}", f"+{add}", None)

    def take_budget_extension(self, task_id: str) -> tuple[str, str, int] | None:
        """Consuma (one-shot: NON e' una grant permanente, ogni esaurimento ri-chiede)
        la risposta a una richiesta di estensione budget: (answer, key, add) o None."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, payload, answer FROM approvals WHERE task_id=? AND"
                " kind='irreversible_op' AND status='answered'", (task_id,)).fetchall()
            for r in rows:
                p = json.loads(r["payload"])
                if p.get("tool") == "extend_budget":
                    c.execute("UPDATE approvals SET status='expired' WHERE id=?", (r["id"],))
                    args = p.get("args") or {}
                    return r["answer"], args.get("key", "tokens"), int(args.get("add", 0))
        return None

    def budget_used(self, task_id: str) -> BudgetUsed:
        """Aggregato dal DB: una sola fonte di verita', mai contatori in RAM.
        wall_s la calcola il BudgetTracker (dal created_at del task)."""
        with self._conn() as c:
            # F2.5: il budget misura il LAVORO, non la dimensione dei prompt — i token
            # serviti dalla KV cache non costano: (prompt - cached) + gen. Contare il
            # prompt intero a ogni step gonfiava il consumo quadraticamente.
            llm = c.execute(
                "SELECT COALESCE(SUM(prompt_tokens - cached_tokens + gen_tokens), 0) AS t"
                " FROM llm_calls WHERE task_id=?", (task_id,)).fetchone()
            tools = c.execute("SELECT COUNT(*) AS n FROM tool_calls WHERE task_id=?",
                              (task_id,)).fetchone()
        return BudgetUsed(tokens=llm["t"], tool_calls=tools["n"], wall_s=0.0)

    # ── interni ──────────────────────────────────────────────────────────────

    def _budget(self, c: sqlite3.Connection, task_id: str) -> Budget:
        rows = {r["key"]: r["limit_val"] for r in
                c.execute("SELECT key, limit_val FROM budgets WHERE task_id=?", (task_id,))}
        return Budget(max_total_tokens=rows["tokens"], max_tool_calls=rows["tool_calls"],
                      max_retries_per_subtask=rows["retries"], max_wall_s=rows["wall_s"])

    @staticmethod
    def _decision(c: sqlite3.Connection, task_id: str, actor: str, decision: str,
                  reason: str, target: str | None) -> None:
        c.execute("INSERT INTO decisions (task_id, actor, decision, reason, target,"
                  " created_at) VALUES (?,?,?,?,?,?)",
                  (task_id, actor, decision, reason, target, _now()))
