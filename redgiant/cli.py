"""CLI di sviluppo (piano F1.9): rg run | status | eval | bench.

Non è l'interfaccia utente (quella è la GUI di F2): è il pilota minimo per
sviluppo e test. In F1 il piano è statico: --plan è obbligatorio per run.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from redgiant import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rg", description="Red Giant dev CLI")
    parser.add_argument("--version", action="version", version=f"redgiant {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="esegue un task (piano statico in F1)")
    p_run.add_argument("--target", required=True, help="directory bersaglio")
    p_run.add_argument("--prompt", required=True)
    p_run.add_argument("--plan", default=None, help="plan.json statico")
    p_run.add_argument("--plansys", action="store_true",
                       help="PS5: pianificazione S/M/J + gate (senza plan.json)")
    p_run.add_argument("--profile", default="dev-fast")
    p_run.add_argument("--domain", default="coding")
    p_run.add_argument("--writable", nargs="*", default=[],
                       help="glob scrivibili relativi al target")
    p_run.add_argument("--test-cmd", action="append", default=[],
                       metavar="ID=CMD", help='es. "pytest=pytest -q" (ripetibile)')

    p_status = sub.add_parser("status", help="albero di esecuzione di un task")
    p_status.add_argument("task_id")
    p_status.add_argument("--profile", default="dev-fast")

    p_eval = sub.add_parser("eval", help="esegue i task sintetici e produce il report")
    p_eval.add_argument("--profile", default="severino-sim")
    p_eval.add_argument("--only", default=None, help="lista di id separati da virgola")
    p_eval.add_argument("--out", type=Path, default=Path("bench/results"))
    p_eval.add_argument("--planner", action="store_true",
                        help="F3: il piano lo genera il Planner (A/B vs baseline statica)")
    p_eval.add_argument("--plansys", action="store_true",
                        help="PS6: pianificazione S/M/J + gate (A/B vs baseline)")

    p_bench = sub.add_parser("bench", help="wrapper di bench/run_bench.py")
    p_bench.add_argument("--profile", required=True)

    p_serve = sub.add_parser("serve", help="avvia la GUI web (F2)")
    p_serve.add_argument("--profile", default="severino-sim")

    ns = parser.parse_args(argv)
    return {"run": _run, "status": _status, "eval": _eval, "bench": _bench,
            "serve": _serve}[ns.cmd](ns)


def _run(ns: argparse.Namespace) -> int:
    from redgiant.config import Config
    from redgiant.core.orchestrator import Orchestrator, load_static_plan
    from redgiant.eval.harness import _PROMPTS_DIR
    from redgiant.llm.client import LlamaClient
    from redgiant.prompts.assemble import PromptAssembler
    from redgiant.state.models import Budget
    from redgiant.state.store import StateStore
    from redgiant.tools.base import Scope
    from redgiant.tools.router import ToolRouter, default_catalog

    cfg = Config.load(ns.profile)
    store = StateStore(cfg.paths.db)
    llm = LlamaClient(cfg.llm, store)
    if not llm.health():
        print(f"llama-server non raggiungibile su {cfg.llm.base_url}: avvialo prima")
        return 2

    test_commands = {}
    for spec in ns.test_cmd:
        cmd_id, _, cmd = spec.partition("=")
        test_commands[cmd_id] = shlex.split(cmd)

    scope = Scope(Path(ns.target), ns.writable)
    router = ToolRouter(default_catalog(cfg, scope, test_commands), scope, store)
    if ns.plansys:
        from redgiant.plansys.engine import PlanSysEngine
        orch = PlanSysEngine(cfg, store, llm, router, PromptAssembler(_PROMPTS_DIR))
    else:
        if ns.plan is None:
            print("serve --plan (statico) oppure --plansys")
            return 2
        orch = Orchestrator(cfg, store, llm, router, PromptAssembler(_PROMPTS_DIR))

    tid = store.create_task(ns.prompt, ns.target, ns.profile,
                            Budget(**vars(cfg.budget)))
    if not ns.plansys:
        load_static_plan(store, tid, Path(ns.plan))
    print(f"task {tid} avviato (profilo {ns.profile})")
    state = orch.run_task(tid)
    print(f"esito: {state.status}")
    _print_tree(store, tid)
    return 0 if state.status == "completed" else 1


def _status(ns: argparse.Namespace) -> int:
    from redgiant.config import Config
    from redgiant.state.store import StateStore

    cfg = Config.load(ns.profile)
    store = StateStore(cfg.paths.db)
    try:
        _print_tree(store, ns.task_id)
    except KeyError:
        print(f"task sconosciuto: {ns.task_id}")
        return 1
    return 0


def _print_tree(store, task_id: str) -> None:
    """Vista operativa stile specsheet §20."""
    st = store.load_task(task_id)
    used = store.budget_used(task_id)
    pct = 100 * used.tokens / max(st.budget.max_total_tokens, 1)
    print(f"TASK {task_id}")
    print(f"├── request: {st.request[:80]}")
    print(f"├── status: {st.status}" + (f" ({st.plan and 'plan v%d' % st.plan.version})"))
    marks = {"completed": "✓", "completed_with_warnings": "✓~", "failed": "✗",
             "running": "▶", "retry": "↻", "repair": "🔧", "blocked": "⏸",
             "pending": "·", "skipped": "»"}
    rows = store.list_subtasks(task_id)
    for i, r in enumerate(rows):
        joint = "└──" if i == len(rows) - 1 else "├──"
        m = marks.get(r["status"], "?")
        att = f" (attempts {r['attempts']})" if r["attempts"] else ""
        print(f"{joint} {m} {r['subtask_id']} {r['title'][:50]} [{r['status']}]{att}")
    print(f"budget: {used.tokens} tok ({pct:.0f}%), {used.tool_calls} tool calls")


def _eval(ns: argparse.Namespace) -> int:
    from redgiant.eval.harness import run_eval
    only = ns.only.split(",") if ns.only else None
    report = run_eval(ns.profile, only, ns.out, use_planner=ns.planner,
                      use_plansys=ns.plansys)
    print(f"report: {report}")
    print(Path(report).read_text(encoding="utf-8"))
    return 0


def _serve(ns: argparse.Namespace) -> int:
    import uvicorn
    from redgiant.config import Config
    from redgiant.web.app import create_app

    cfg = Config.load(ns.profile)
    print(f"Red Giant GUI su http://{cfg.web.host}:{cfg.web.port} (profilo {ns.profile})")
    uvicorn.run(create_app(cfg), host=cfg.web.host, port=cfg.web.port, log_level="warning")
    return 0


def _bench(ns: argparse.Namespace) -> int:
    import subprocess
    return subprocess.call([sys.executable, "bench/run_bench.py",
                            "--profile", ns.profile])


if __name__ == "__main__":
    raise SystemExit(main())
