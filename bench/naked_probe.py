"""Braccio di controllo "modello NUDO" per la serie F3-bis (richiesta utente
2026-08-03: quanto e' merito del modello e quanto del workflow?).

Protocollo: per ogni task T030-T032 il modello riceve i MATERIALI INLINE in un
solo prompt (per T031 il JSON del servizio, gia' fetchato: il tool-use e'
workflow per definizione e resta fuori) e produce UNA completion libera —
niente tool, niente loop, niente retry, niente verifica. L'output diventa
l'artefatto (con una sola concessione meccanica: strip dei code-fence) e lo
giudica LO STESSO judge.py del task. N run per la banda di varianza.

Uso: python bench/naked_probe.py [profilo] [n_run]   (default: severino-sim 3)
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from redgiant.config import Config
from redgiant.llm.client import LlamaClient
from redgiant.prompts.assemble import PromptParts

TASKS = ROOT / "redgiant" / "eval" / "tasks"

T031_PAYLOAD = ('{"service": "atlas-monitor", "version": "2.4.1", '
                '"uptime_days": 17, "healthy": true}')


def _materials(task_id: str) -> tuple[str, str, str]:
    """(istruzione, materiali, nome artefatto)."""
    if task_id == "T030_doc_analysis":
        docs = "\n\n".join(
            f"--- {p.name} ---\n{p.read_text(encoding='utf-8')}"
            for p in sorted((TASKS / task_id / "repo" / "docs").glob("*.md")))
        return ("Answer from the FACTS in the documents. Output EXACTLY two "
                "lines, nothing else: 'staging_port=<port of the staging "
                "server>' and 'project_start=<year the project started>'.",
                docs, "answer.txt")
    if task_id == "T031_api_call":
        return ("The monitoring service returned the JSON below. Output "
                "EXACTLY two lines, nothing else: 'version=<version field>' "
                "and 'uptime_days=<uptime_days field>'.",
                T031_PAYLOAD, "report.txt")
    if task_id == "T032_doc_transform":
        md = (TASKS / task_id / "repo" / "records.md").read_text(
            encoding="utf-8")
        return ("Extract the people into CSV. Output EXACTLY the CSV and "
                "nothing else: header line 'name,email,role' then one row "
                "per person, in document order, no quotes, no extra spaces.",
                md, "out.csv")
    raise KeyError(task_id)


def _strip_fences(text: str) -> str:
    m = re.search(r"```[a-z]*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def run_probe(profile: str, n_runs: int) -> int:
    cfg = Config.load(profile)
    llm = LlamaClient(cfg.llm)
    if not llm.health():
        print(f"llama-server non raggiungibile ({cfg.llm.base_url})")
        return 2
    rows = []
    for task_id in ("T030_doc_analysis", "T031_api_call",
                    "T032_doc_transform"):
        instr, mats, artifact = _materials(task_id)
        greens = 0
        for n in range(n_runs):
            parts = PromptParts(
                preamble="You are a precise assistant. Output ONLY the "
                         "requested content, no commentary.",
                role_card=instr, tool_card="",
                task_header=f"TASK {task_id} (probe run {n + 1})",
                durable_state="", volatile_context=mats,
                output_instruction="Output the exact content now.")
            r = llm.complete(parts, role="naked_probe", max_tokens=256)
            tmp = Path(tempfile.mkdtemp(prefix=f"naked_{task_id}_"))
            shutil.copytree(TASKS / task_id / "repo", tmp,
                            dirs_exist_ok=True)
            (tmp / artifact).write_text(_strip_fences(r.text),
                                        encoding="utf-8")
            judge = subprocess.run([sys.executable, "judge.py"], cwd=tmp,
                                   capture_output=True, text=True, timeout=60)
            greens += judge.returncode == 0
            print(f"  {task_id} run {n + 1}: "
                  f"{'VERDE' if judge.returncode == 0 else 'ko — ' + judge.stdout.strip()[:80]}",
                  flush=True)
        rows.append((task_id, greens, n_runs))
    print("\n=== NAKED PROBE ===")
    for tid, g, n in rows:
        print(f"{tid}: {g}/{n}")
    return 0


if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "severino-sim"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    sys.exit(run_probe(profile, runs))
