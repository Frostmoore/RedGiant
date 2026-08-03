"""Braccio NUDO della ladder: un solo prompt coi materiali inline, una
completion, zero tool/loop/retry, stesso giudice del task agentico.

Quando i materiali NON stanno nel contesto, si TRONCANO dichiarandolo — e'
esattamente cio' che puo' fare un sistema one-shot: e' il limite fisico, non
un handicap arbitrario (il braccio agentico invece cerca e legge selettivo).

Bracci della matrice coperti: **B1** (nudo) e **B3** (nudo + thinking, con
`--think`): il canale di pensiero nativo si apre PRIMA della risposta, stesso
protocollo two-call del workflow (TH-D1), fusibile dal config.

Uso: python bench/ladder/run_naked.py [profilo] [n_run] [prefisso] [--think]
Default: severino-sim 3 T05 (senza thinking)
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import shutil

from redgiant.config import Config
from redgiant.eval.harness import discover_tasks
from redgiant.llm.client import ContextOverflow, LlamaClient, LlmError
from redgiant.prompts.assemble import PromptParts

MAX_OUT = 256


def main(profile: str, n_runs: int, prefix: str, think: bool = False) -> int:
    cfg = Config.load(profile)
    llm = LlamaClient(cfg.llm)
    if not llm.health():
        print(f"llama-server non raggiungibile ({cfg.llm.base_url})")
        return 2
    from redgiant.plansys import thinking_budget
    think_budget = thinking_budget() if think else None
    tasks = [t for t in discover_tasks(cfg.eval_tasks_dir)
             if t.id.startswith(prefix) and t.naked_materials]
    print(f"NAKED LADDER ({'B3 con thinking' if think else 'B1 nudo'}) — "
          f"profilo {profile}, {len(tasks)} gradini, {n_runs} run\n")
    for task in sorted(tasks, key=lambda t: t.id):
        greens, notes = 0, ""
        for n in range(n_runs):
            mats = []
            for pattern in task.naked_materials:
                for p in sorted(task.repo_dir.glob(pattern)):
                    mats.append(f"--- {p.name} ---\n"
                                f"{p.read_text(encoding='utf-8')}")
            body = "\n\n".join(mats)
            # troncamento dichiarato: il limite fisico del one-shot
            budget = cfg.llm.ctx_size - MAX_OUT - 400 - (think_budget or 0)
            n_tok = llm.count_tokens(body)
            truncated = n_tok > budget
            if truncated:
                keep = int(len(body) * budget / n_tok)
                body = (body[:keep]
                        + "\n\n[MATERIALS TRUNCATED: they do not fit the "
                          "context window]")
                notes = f" (materiali troncati: {n_tok}->{budget} tok)"
            parts = PromptParts(
                preamble="You are a precise assistant. Output ONLY the "
                         "requested content, no commentary.",
                role_card=task.naked_instruction,
                tool_card="", task_header=f"TASK {task.id}",
                durable_state="", volatile_context=body,
                output_instruction="Output the exact file content now.")
            t0 = time.time()
            try:
                r = llm.complete(parts, role="naked_probe",
                                 max_tokens=MAX_OUT, think=think_budget)
                text = r.text
            except (ContextOverflow, LlmError) as e:
                print(f"  {task.id} run {n+1}: ko ({type(e).__name__})")
                continue
            tmp = Path(tempfile.mkdtemp(prefix=f"naked_{task.id}_"))
            shutil.copytree(task.repo_dir, tmp, dirs_exist_ok=True)
            (tmp / "answer.txt").write_text(text.strip() + "\n",
                                            encoding="utf-8")
            j = subprocess.run([sys.executable, "judge.py"], cwd=tmp,
                               capture_output=True, text=True, timeout=60)
            ok = j.returncode == 0
            greens += ok
            print(f"  {task.id} run {n+1}: "
                  f"{'VERDE' if ok else 'ko — ' + j.stdout.strip()[:60]}"
                  f" [{time.time()-t0:.0f}s]", flush=True)
        print(f"== {task.id}: {greens}/{n_runs}{notes}\n", flush=True)
    return 0


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--think"]
    sys.exit(main(argv[0] if argv else "severino-sim",
                  int(argv[1]) if len(argv) > 1 else 3,
                  argv[2] if len(argv) > 2 else "T05",
                  think="--think" in sys.argv))
