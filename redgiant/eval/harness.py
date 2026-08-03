"""Evaluator v0 (piano F1.10): il giudice del progetto.

Ogni task sintetico = cartella con task.toml + repo/ (+ plan.json in F1).
Esecuzione: copia del repo in una dir temporanea (il sorgente non si sporca MAI),
run della pipeline, poi VERIFICA ESTERNA: success_cmd eseguito dall'harness
sulla copia. `completed` = il sistema dice di aver finito; `verified` = il
giudice esterno conferma. La forbice tra i due e' la metrica anti-bugia e deve
restare zero.

useful_tokens v0: token delle chiamate LLM nelle sottofasi terminate
'completed'; il resto e' overhead. (Approssimazione dichiarata: il linkage
fine chiamata->tool-accettata e' debito tecnico, v. atlante.)
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from redgiant.config import Config
from redgiant.core.orchestrator import Orchestrator, load_static_plan
from redgiant.llm.client import LlamaClient
from redgiant.prompts.assemble import PromptAssembler
from redgiant.state.models import Budget
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter, default_catalog

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class EvalTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    domain: str
    prompt: str
    repo_dir: Path
    plan_file: Path | None
    success_cmd: str
    timeout_s: int
    tags: list[str]
    writable_globs: list[str] = []
    test_commands: dict[str, list[str]] = {}
    requires: list[str] = []          # eseguibili esterni necessari (es. "php")
    expected_outcome: str = "verified"  # F4: anche "failed" | "blocked"
    # F3b.2: whitelist http PER-TASK (override della config, che di default e'
    # vuota) e servizio locale "esterno" avviato dall'harness (determinismo:
    # l'endpoint reale arriva in F7). Path relativo alla dir del task, NON al
    # repo: il modello non deve vederne il sorgente.
    http_allowed_domains: list[str] = []
    service_script: Path | None = None
    # LADDER: braccio di controllo "modello nudo" (bench/naked_probe.py) —
    # glob dei materiali da inlineare e istruzione one-shot. Se assenti, il
    # task non ha braccio nudo (es. serve tool-use per costruzione).
    naked_materials: list[str] = []
    naked_instruction: str = ""
    # LADDER L7: 8 fatti in 400 documenti non si raccolgono in 20 passi — il
    # budget di passi e' una proprieta' della TAGLIA del task, non una
    # costante globale (0 = usa il default di config)
    worker_max_steps: int = 0


class EvalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    completed: bool
    verified: bool
    skipped: str | None = None
    total_tokens: int
    useful_tokens: int
    wall_s: float
    llm_calls: int
    tool_calls: int
    retries: int


def discover_tasks(tasks_dir: Path) -> list[EvalTask]:
    tasks = []
    for toml_path in sorted(tasks_dir.glob("*/task.toml")):
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        base = toml_path.parent
        plan = base / data["plan_file"] if data.get("plan_file") else None
        tasks.append(EvalTask(
            id=data["id"], domain=data.get("domain", "coding"), prompt=data["prompt"],
            repo_dir=base / "repo", plan_file=plan,
            success_cmd=data["success_cmd"], timeout_s=data.get("timeout_s", 1800),
            tags=data.get("tags", []),
            writable_globs=data.get("writable_globs", []),
            test_commands={k: list(v) for k, v in data.get("test_commands", {}).items()},
            requires=data.get("requires", []),
            expected_outcome=data.get("expected_outcome", "verified"),
            http_allowed_domains=data.get("http_allowed_domains", []),
            service_script=(base / data["service_script"]
                            if data.get("service_script") else None),
            naked_materials=data.get("naked_materials", []),
            naked_instruction=data.get("naked_instruction", ""),
            worker_max_steps=data.get("worker_max_steps", 0)))
    return tasks


def _naive_plan(task: EvalTask) -> dict:
    """Baseline F3.5: il piano 'ingenuo' — una fase, una sottofase do-everything.
    Rappresenta cio' che farebbe un agente naive; e' il gruppo di controllo del
    Planner (D11)."""
    first_cmd = next(iter(task.test_commands), None)
    return {
        "plan": {"goal": task.prompt[:290], "success_criteria": ["verification passes"],
                 "phases": [{"id": "P1", "title": "Do the task", "depends_on": [],
                             "completion_criteria": ["verification passes"]}]},
        "subtasks": [{
            "id": "P1.S1", "phase_id": "P1", "title": "Do the task",
            "objective": task.prompt, "inputs": [], "tools": [],
            "expected_outputs": [], "completion_criteria": ["verification passes"],
            "verification": [first_cmd] if first_cmd else []}]}


def run_eval(profile: str, only: list[str] | None, out_dir: Path,
             use_planner: bool = False, use_plansys: bool = False) -> Path:
    cfg = Config.load(profile)
    if use_planner:
        # gate D11: --planner e' la riaccensione ESPLICITA (config default: off)
        from dataclasses import replace
        cfg = replace(cfg, planner_enabled=True)
    if use_plansys:
        # PS-D9: idem per il plansys
        from dataclasses import replace
        cfg = replace(cfg, plansys_enabled=True)
    store = StateStore(cfg.paths.db)
    llm = LlamaClient(cfg.llm, store)
    if not llm.health():
        raise RuntimeError(f"llama-server not reachable at {cfg.llm.base_url} "
                           f"(profile {profile}): start it first")
    assembler = PromptAssembler(_PROMPTS_DIR)

    tasks = discover_tasks(cfg.eval_tasks_dir)
    if only:
        tasks = [t for t in tasks if t.id in only]
    results: list[EvalResult] = []

    for task in tasks:
        missing = [r for r in task.requires if shutil.which(r) is None]
        if missing:
            results.append(EvalResult(task_id=task.id, completed=False, verified=False,
                                      skipped=f"missing executables: {missing}",
                                      total_tokens=0, useful_tokens=0, wall_s=0.0,
                                      llm_calls=0, tool_calls=0, retries=0))
            continue
        results.append(_run_one(cfg, store, llm, assembler, task, use_planner,
                                use_plansys))

    git_ref = _git_ref()
    report = write_report(results, profile, git_ref, out_dir, use_planner,
                          use_plansys)
    store_row = StateStore(cfg.paths.db)
    with store_row._conn() as c:  # riga eval_runs (harness = unico scrittore)
        c.execute("INSERT INTO eval_runs (started_at, profile, git_ref, report_path)"
                  " VALUES (?,?,?,?)",
                  (datetime.now(timezone.utc).isoformat(timespec='seconds'),
                   profile, git_ref, str(report)))
    return report


def _run_one(cfg: Config, store: StateStore, llm: LlamaClient,
             assembler: PromptAssembler, task: EvalTask,
             use_planner: bool = False, use_plansys: bool = False) -> EvalResult:
    workdir = Path(tempfile.mkdtemp(prefix=f"rgeval_{task.id}_"))
    shutil.copytree(task.repo_dir, workdir, dirs_exist_ok=True)

    # F3b.2: whitelist http per-task (la config di default resta VUOTA) e
    # servizio locale avviato dall'harness come "esterno" deterministico
    if task.http_allowed_domains:
        from dataclasses import replace
        cfg = replace(cfg, security=replace(
            cfg.security,
            http_allowed_domains=tuple(task.http_allowed_domains)))
    if task.worker_max_steps:
        from dataclasses import replace as _replace
        cfg = _replace(cfg, worker_max_steps=task.worker_max_steps)
    service = None
    if task.service_script is not None:
        service = subprocess.Popen(
            [sys.executable, str(task.service_script)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)  # il servizio e' un http.server: pronto in <1s

    scope = Scope(workdir, task.writable_globs)
    router = ToolRouter(default_catalog(cfg, scope, task.test_commands), scope, store)
    if use_plansys:
        import os
        from redgiant.plansys.engine import PlanSysEngine
        # PS-D8, run non presidiate: i choice point si auto-decidono sulla
        # raccomandata (registrata come decisione, mai silenziosa)
        os.environ["RG_PLANSYS_AUTODECIDE"] = "recommended"
        orch = PlanSysEngine(cfg, store, llm, router, assembler)
    else:
        orch = Orchestrator(cfg, store, llm, router, assembler)

    # ablazione "retry": un colpo solo coi tool (braccio A/B, mai produzione)
    from redgiant.core.ablate import worker_ablated
    budget = Budget(max_total_tokens=cfg.budget.max_total_tokens,
                    max_tool_calls=cfg.budget.max_tool_calls,
                    max_retries_per_subtask=(
                        0 if worker_ablated("retry")
                        else cfg.budget.max_retries_per_subtask),
                    max_wall_s=min(cfg.budget.max_wall_s, task.timeout_s))
    tid = store.create_task(task.prompt, str(workdir), cfg.profile_name, budget)
    # F3.5 A/B: con use_planner il piano lo genera il Planner (si IGNORA il
    # plan.json); con use_plansys lo genera S (PS5); senza, piano statico o
    # 'ingenuo' come baseline
    if not use_planner and not use_plansys:
        if task.plan_file is not None:
            load_static_plan(store, tid, task.plan_file)
        else:
            import json as _json
            p = workdir / "_naive_plan.json"
            p.write_text(_json.dumps(_naive_plan(task)), encoding="utf-8")
            load_static_plan(store, tid, p)
            p.unlink()

    t0 = time.monotonic()
    try:
        state = orch.run_task(tid)
    finally:
        if service is not None:
            service.terminate()  # il giudice NON usa il servizio: verifica
            # gli artefatti scritti, coi valori attesi cablati nello script
    wall = time.monotonic() - t0

    verified = False
    if state.status == "completed":
        argv = shlex.split(task.success_cmd)
        # stessa risoluzione dei tool (F1.11): pytest/python = l'interprete dell'harness
        if argv[0] == "pytest":
            argv = [sys.executable, "-m", "pytest", *argv[1:]]
        elif argv[0] == "python":
            argv = [sys.executable, *argv[1:]]
        try:
            proc = subprocess.run(argv, cwd=workdir, capture_output=True, timeout=300)
            verified = proc.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            verified = False

    total, useful, calls, tools, retries = _metrics(store, tid)
    return EvalResult(task_id=task.id, completed=state.status == "completed",
                      verified=verified, total_tokens=total, useful_tokens=useful,
                      wall_s=round(wall, 1), llm_calls=calls, tool_calls=tools,
                      retries=retries)


def _metrics(store: StateStore, task_id: str) -> tuple[int, int, int, int, int]:
    with store._conn() as c:
        total = c.execute("SELECT COALESCE(SUM(prompt_tokens+gen_tokens),0) t,"
                          " COUNT(*) n FROM llm_calls WHERE task_id=?",
                          (task_id,)).fetchone()
        done_ids = [r["subtask_id"] for r in c.execute(
            "SELECT subtask_id FROM subtasks WHERE task_id=? AND status LIKE 'completed%'",
            (task_id,))]
        if done_ids:
            q = ",".join("?" * len(done_ids))
            useful = c.execute(
                f"SELECT COALESCE(SUM(prompt_tokens+gen_tokens),0) t FROM llm_calls"
                f" WHERE task_id=? AND subtask_id IN ({q})",
                (task_id, *done_ids)).fetchone()["t"]
        else:
            useful = 0
        tools = c.execute("SELECT COUNT(*) n FROM tool_calls WHERE task_id=?",
                          (task_id,)).fetchone()["n"]
        retries = c.execute("SELECT COALESCE(SUM(attempts),0) a FROM subtasks"
                            " WHERE task_id=?", (task_id,)).fetchone()["a"]
    return total["t"], useful, total["n"], tools, retries


def write_report(results: list[EvalResult], profile: str, git_ref: str,
                 out_dir: Path, use_planner: bool = False,
                 use_plansys: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    official = profile != "dev-fast"
    mode = "plansys" if use_plansys else ("planner" if use_planner else "static")
    ran = [r for r in results if r.skipped is None]
    lines = [
        f"# Evaluator — run {stamp} UTC",
        "",
        f"Profilo: `{profile}` · modalità piano: **{mode}**"
        + ("" if official else " — ⚠️ NON UFFICIALE (D6)"),
        f" · commit: `{git_ref}` · task: {len(results)}",
        "",
        "| task | completed | verified | tokens | useful | useful% | wall_s | llm calls | tool calls | retries |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.skipped:
            lines.append(f"| {r.task_id} | SKIPPED: {r.skipped} | | | | | | | | |")
            continue
        pct = f"{(r.useful_tokens / r.total_tokens * 100):.0f}%" if r.total_tokens else "-"
        lines.append(f"| {r.task_id} | {r.completed} | {r.verified} | {r.total_tokens} |"
                     f" {r.useful_tokens} | {pct} | {r.wall_s} | {r.llm_calls} |"
                     f" {r.tool_calls} | {r.retries} |")
    if ran:
        v = sum(1 for r in ran if r.verified)
        lied = sum(1 for r in ran if r.completed and not r.verified)
        lines += ["",
                  f"**Verified: {v}/{len(ran)}** · forbice completed≠verified: {lied} "
                  f"(deve essere 0) · token totali: {sum(r.total_tokens for r in ran)}"]
    path = out_dir / f"eval_{profile}_{mode}_{stamp}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _git_ref() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
