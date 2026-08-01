"""GUI web (piano F2, D12): FastAPI + Jinja2 + HTMX, processo unico, zero build.

Tutte le rotte sono HTML: nessuna API JSON pubblica. La GUI legge lo stato dal
DB (F1.1) ed e' quindi disaccoppiata dall'evoluzione della pipeline.
Avvio:  rg serve  [--profile severino-sim]
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from redgiant.config import Config
from redgiant.state.models import Budget
from redgiant.state.store import StateStore
from redgiant.web.jobs import JobQueue, write_task_config

_HERE = Path(__file__).resolve().parent


def create_app(cfg: Config) -> FastAPI:
    app = FastAPI(title="Red Giant", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    templates = Jinja2Templates(directory=_HERE / "templates")
    store = StateStore(cfg.paths.db)
    jobs = JobQueue(cfg, store)
    app.state.cfg, app.state.store, app.state.jobs = cfg, store, jobs

    def page(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(
            request, name, {"cfg": cfg, "queue": jobs.queue_snapshot(),
                            "current": jobs.current(), **ctx},
            status_code=status_code)

    # ── tasks ────────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        tasks = store.list_tasks()
        pending = len(store.pending_approvals())
        return page(request, "index.html", tasks=tasks, pending=pending)

    @app.get("/tasks/new", response_class=HTMLResponse)
    def task_new(request: Request):
        return page(request, "task_new.html")

    @app.post("/tasks")
    def task_create(request: Request,
                    prompt: str = Form(""), target_dir: str = Form(""),
                    domain: str = Form("coding"), writable: str = Form(""),
                    test_commands: str = Form(""), plan_json: str = Form(""),
                    approve_writes: bool = Form(False),
                    max_tokens: int = Form(0)):
        target = Path(target_dir)
        if not prompt.strip() or not target.is_dir():
            return page(request, "task_new.html", status_code=400,
                        error="prompt vuoto o target_dir inesistente",
                        form=dict(prompt=prompt, target_dir=target_dir))
        tcmds: dict[str, list[str]] = {}
        for line in test_commands.splitlines():
            cmd_id, _, cmd = line.strip().partition("=")
            if cmd_id and cmd:
                import shlex
                tcmds[cmd_id.strip()] = shlex.split(cmd)
        plan = None
        if plan_json.strip():
            try:
                plan = json.loads(plan_json)
            except json.JSONDecodeError as e:
                return page(request, "task_new.html", status_code=400,
                            error=f"plan JSON invalido: {e}",
                            form=dict(prompt=prompt, target_dir=target_dir))
            # pre-flight F2.5: verifiche del piano senza comando registrato = task
            # destinato a fallire con "unknown check". Meglio un 400 subito.
            declared = {v for st in plan.get("subtasks", []) for v in st.get("verification", [])}
            missing = sorted(declared - set(tcmds))
            if missing:
                return page(request, "task_new.html", status_code=400,
                            error=f"il piano dichiara verifiche senza comando registrato: "
                                  f"{missing} — aggiungile in 'Comandi di test' "
                                  f"(es. {missing[0]}={missing[0]} -q)",
                            form=dict(prompt=prompt, target_dir=target_dir))
        budget = Budget(
            max_total_tokens=max_tokens or cfg.budget.max_total_tokens,
            max_tool_calls=cfg.budget.max_tool_calls,
            max_retries_per_subtask=cfg.budget.max_retries_per_subtask,
            max_wall_s=cfg.budget.max_wall_s)
        tid = store.create_task(prompt, str(target), cfg.profile_name, budget)
        write_task_config(cfg.paths.tasks_dir, tid,
                          writable_globs=[g.strip() for g in writable.split(",") if g.strip()],
                          test_commands=tcmds, plan=plan)
        if approve_writes:
            p = cfg.paths.tasks_dir / tid / "task_config.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            data["approve_writes"] = True
            p.write_text(json.dumps(data), encoding="utf-8")
        jobs.submit(tid)
        return RedirectResponse(f"/tasks/{tid}", status_code=303)

    @app.get("/tasks/{task_id}", response_class=HTMLResponse)
    def task_detail(request: Request, task_id: str):
        try:
            st = store.load_task(task_id)
        except KeyError:
            return HTMLResponse("task sconosciuto", status_code=404)
        return page(request, "task.html", t=st, subtasks=store.list_subtasks(task_id),
                    used=store.budget_used(task_id),
                    approvals=store.pending_approvals(task_id))

    @app.get("/tasks/{task_id}/tree", response_class=HTMLResponse)
    def task_tree(request: Request, task_id: str):
        try:
            st = store.load_task(task_id)
        except KeyError:
            return HTMLResponse("", status_code=404)
        return page(request, "tree.html", t=st, subtasks=store.list_subtasks(task_id),
                    used=store.budget_used(task_id))

    @app.get("/tasks/{task_id}/log", response_class=HTMLResponse)
    def task_log(request: Request, task_id: str, tail: int = 200):
        p = cfg.paths.tasks_dir / task_id / "task.log"
        if not p.is_file():
            return HTMLResponse("nessun log", status_code=404)
        lines = p.read_text(encoding="utf-8").splitlines()[-tail:]
        return page(request, "log.html", task_id=task_id, lines=lines)

    @app.post("/tasks/{task_id}/cancel")
    def task_cancel(task_id: str):
        ok = jobs.cancel(task_id)
        return RedirectResponse(f"/tasks/{task_id}" if ok else "/", status_code=303)

    # ── approvals ────────────────────────────────────────────────────────────

    @app.get("/approvals", response_class=HTMLResponse)
    def approvals(request: Request):
        items = []
        for a in store.pending_approvals():
            a = dict(a)
            a["payload_pretty"] = json.dumps(json.loads(a["payload"]), indent=1)[:800]
            items.append(a)
        return page(request, "approvals.html", items=items)

    @app.post("/approvals/{approval_id}")
    def approval_answer(approval_id: int, answer: str = Form(...)):
        try:
            task_id = store.answer_approval(approval_id, answer.strip())
        except KeyError:
            return HTMLResponse("richiesta sconosciuta", status_code=404)
        except ValueError:
            return HTMLResponse("gia' risposta", status_code=409)
        # ripartenza: sottofasi blocked -> pending, task -> queued, resubmit
        for r in store.list_subtasks(task_id):
            if r["status"] == "blocked":
                store.set_subtask_status(task_id, r["subtask_id"], "pending", actor="user")
        st = store.load_task(task_id)
        if st.status == "blocked":
            store.set_task_status(task_id, "queued", actor="user",
                                  error=None)
            app.state.jobs.submit(task_id)
        return RedirectResponse("/approvals", status_code=303)

    # ── metrics ──────────────────────────────────────────────────────────────

    @app.get("/metrics", response_class=HTMLResponse)
    def metrics(request: Request):
        with store._conn() as c:
            evals = [dict(r) for r in c.execute(
                "SELECT started_at, profile, git_ref, report_path FROM eval_runs"
                " ORDER BY id DESC LIMIT 5")]
        return page(request, "metrics.html", evals=evals, tasks=store.list_tasks(15))

    return app
