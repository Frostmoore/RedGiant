"""Collaudo end-to-end della GUI (committato in chiusura F2: la campagna di
collaudo deve essere riproducibile col repo, non con script volatili).

Esegue un task sintetico dell'Evaluator ATTRAVERSO la GUI (form -> coda ->
eventuali approvazioni auto-concesse -> esito), misurando cio' che conta.

Prerequisito: GUI avviata (scripts/start-gui.ps1).
Uso:  python scripts/collaudo-gui.py --task T007 [--approve] [--base http://127.0.0.1:8090]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from redgiant.eval.harness import discover_tasks  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="id del task sintetico (es. T007)")
    ap.add_argument("--approve", action="store_true",
                    help="attiva approve_writes e auto-approva quando richiesto")
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--timeout", type=int, default=900)
    ns = ap.parse_args()

    task = next((t for t in discover_tasks(ROOT / "redgiant" / "eval" / "tasks")
                 if t.id == ns.task), None)
    if task is None:
        print(f"task sconosciuto: {ns.task}")
        return 2

    workdir = Path(tempfile.mkdtemp(prefix=f"collaudo_{task.id}_"))
    shutil.copytree(task.repo_dir, workdir, dirs_exist_ok=True)
    plan_json = (task.plan_file.read_text(encoding="utf-8") if task.plan_file else "")

    client = httpx.Client(base_url=ns.base, timeout=30)
    r = client.post("/tasks", data={
        "prompt": task.prompt, "target_dir": str(workdir),
        "writable": ", ".join(task.writable_globs), "plan_json": plan_json,
        **({"approve_writes": "true"} if ns.approve else {})},
        follow_redirects=False)
    if r.status_code != 303:
        print(f"creazione fallita: HTTP {r.status_code}")
        return 2
    tid = r.headers["location"].rsplit("/", 1)[-1]
    print(f"task {tid} avviato su {workdir}")

    db = sqlite3.connect(ROOT / "data" / "redgiant.db")
    db.row_factory = sqlite3.Row
    t0 = time.time()
    approvals = 0
    status = "TIMEOUT"
    while time.time() - t0 < ns.timeout:
        time.sleep(4)
        status = db.execute("SELECT status FROM tasks WHERE id=?",
                            (tid,)).fetchone()["status"]
        if status == "blocked":
            for a in db.execute("SELECT id, payload FROM approvals WHERE task_id=?"
                                " AND status='pending'", (tid,)).fetchall():
                client.post(f"/approvals/{a['id']}", data={"answer": "yes"})
                approvals += 1
                print(f"  [{time.time()-t0:4.0f}s] approvato:"
                      f" {json.loads(a['payload']).get('tool')}")
        elif status in ("completed", "partial", "failed", "cancelled"):
            break

    argv = task.success_cmd.split()
    if argv[0] in ("pytest", "python"):
        argv = [sys.executable, "-m", "pytest", "-q"] if argv[0] == "pytest" \
            else [sys.executable, *argv[1:]]
    verified = subprocess.run(argv, cwd=workdir, capture_output=True,
                              timeout=300).returncode == 0
    used = db.execute(
        "SELECT COALESCE(SUM(MAX(prompt_tokens-cached_tokens,0)+gen_tokens),0) t,"
        " COUNT(*) n FROM llm_calls WHERE task_id=?", (tid,)).fetchone()
    print(f"\nESITO: {status} | verificato esternamente: {verified} | "
          f"{used['n']} chiamate | {used['t']} token-lavoro | "
          f"{approvals} approvazioni | {time.time()-t0:.0f}s")
    return 0 if (status == "completed" and verified) else 1


if __name__ == "__main__":
    raise SystemExit(main())
