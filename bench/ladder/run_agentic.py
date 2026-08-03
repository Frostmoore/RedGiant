"""Bracci AGENTICI della ladder, con ABLAZIONI (regola della triade).

Si eseguono SOLO sui gradini dove il nudo e' caduto: dove il nudo passa, il
task non misura il workflow (e va reso piu' largo). Per ogni gradino:
  full      = workflow completo
  -search   = senza search_code (deve listare e leggere)
  -verify   = senza verifica deterministica (si crede al Worker)
  -retry    = un colpo solo coi tool
Il delta full-vs-ablazione ATTRIBUISCE il merito al componente; il delta
full-vs-nudo dice quanto sale il pavimento.

Uso: python bench/ladder/run_agentic.py <profilo> <T05x,T05y> [bracci]
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from redgiant.eval.harness import run_eval

ARMS = {"full": "", "-search": "search", "-verify": "verify",
        "-retry": "retry"}


def main(profile: str, task_ids: list[str], arms: list[str]) -> int:
    dirty = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        print("INVALIDO: working tree sporco")
        return 3
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    print(f"LADDER AGENTICA @ {sha} — {task_ids} × {arms}\n", flush=True)
    out = ROOT / "bench" / "results"
    for arm in arms:
        env_val = ARMS[arm]
        if env_val:
            os.environ["RG_WORKER_ABLATE"] = env_val
        else:
            os.environ.pop("RG_WORKER_ABLATE", None)
        t0 = time.time()
        try:
            report = run_eval(profile, task_ids, out)
            body = Path(report).read_text(encoding="utf-8")
            verified = [l for l in body.splitlines()
                        if l.startswith("**Verified")]
            print(f"[{arm}] {' '.join(verified)} in {time.time()-t0:.0f}s",
                  flush=True)
            for line in body.splitlines():
                if line.startswith("| T05"):
                    print(f"    {line}", flush=True)
        except Exception as e:
            print(f"[{arm}] ERRORE dopo {time.time()-t0:.0f}s: {e}",
                  flush=True)
    os.environ.pop("RG_WORKER_ABLATE", None)
    print("\nLADDER AGENTICA COMPLETA")
    return 0


if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "severino-sim"
    ids = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["T055"])
    a = (sys.argv[3].split(",") if len(sys.argv) > 3
         else ["full", "-search", "-verify", "-retry"])
    sys.exit(main(prof, ids, a))
