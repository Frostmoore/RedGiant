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

# (nome braccio) -> variabili d'ambiente del braccio (le altre vengono azzerate)
# B2 = workflow senza thinking (full + ablazioni) · B4 = workflow CON thinking
# Convenzione: "-x" ABLA un componente attivo, "+x" ACCENDE un componente che
# il progetto tiene spento (verdetto negativo ma aperto, come D11 e TH3).
_ENV_VARS = ("RG_WORKER_ABLATE", "RG_THINKING_ROLES", "RG_FINISH_GATE",
             "RG_CALCULATOR")
ARMS = {
    "full": {},
    "-search": {"RG_WORKER_ABLATE": "search"},
    "-verify": {"RG_WORKER_ABLATE": "verify"},
    "-retry": {"RG_WORKER_ABLATE": "retry"},
    "-coherence": {"RG_WORKER_ABLATE": "coherence"},  # la guardia F4 sull'aritmetica
    "-compact": {"RG_WORKER_ABLATE": "compact"},     # F5.0-bis: catena volatile
    "+calc": {"RG_CALCULATOR": "1"},                 # LAD.13: spenta di default
    "+finishgate": {"RG_FINISH_GATE": "1"},          # LAD.9: spento di default
    "think": {"RG_THINKING_ROLES": "worker"},        # B4: percorso diretto = Giano
    "think-search": {"RG_WORKER_ABLATE": "search", "RG_THINKING_ROLES": "worker"},
    "think-verify": {"RG_WORKER_ABLATE": "verify", "RG_THINKING_ROLES": "worker"},
    "think-retry": {"RG_WORKER_ABLATE": "retry", "RG_THINKING_ROLES": "worker"},
    "think-coherence": {"RG_WORKER_ABLATE": "coherence",
                        "RG_THINKING_ROLES": "worker"},
    "think-compact": {"RG_WORKER_ABLATE": "compact",
                      "RG_THINKING_ROLES": "worker"},
    "think+calc": {"RG_CALCULATOR": "1", "RG_THINKING_ROLES": "worker"},
    "think+finishgate": {"RG_FINISH_GATE": "1", "RG_THINKING_ROLES": "worker"},
}
# simmetria obbligatoria (utente 2026-08-03): stesse ablazioni nei due blocchi
B2 = ["full", "-search", "-verify", "-retry", "-coherence", "-compact",
      "+calc", "+finishgate"]
B4 = ["think", "think-search", "think-verify", "think-retry",
      "think-coherence", "think-compact", "think+calc", "think+finishgate"]
# smoke GPU: i bracci piu' informativi, con N run per avere statistica
SMOKE = ["full", "-coherence", "-search", "-verify"]


def main(profile: str, task_ids: list[str], arms: list[str],
         runs: int = 1) -> int:
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
        env = ARMS[arm]
        for var in _ENV_VARS:          # sempre azzerate: nessuna perdita tra bracci
            os.environ.pop(var, None)
        for var, val in env.items():
            os.environ[var] = val
        greens = {t: 0 for t in task_ids}
        t0 = time.time()
        for n in range(runs):
            try:
                report = run_eval(profile, task_ids, out)
                body = Path(report).read_text(encoding="utf-8")
                for line in body.splitlines():
                    if line.startswith("| T05"):
                        cells = [c.strip() for c in line.split("|")]
                        if len(cells) > 3 and cells[3] == "True":
                            greens[cells[1]] += 1
                print(f"[{arm}] run {n+1}/{runs}: "
                      + " ".join(f"{k}={v}" for k, v in greens.items()),
                      flush=True)
            except Exception as e:
                print(f"[{arm}] run {n+1} ERRORE: {e}", flush=True)
        print(f"[{arm}] TOTALE "
              + " ".join(f"{k}={v}/{runs}" for k, v in greens.items())
              + f" in {time.time()-t0:.0f}s", flush=True)
    for var in _ENV_VARS:
        os.environ.pop(var, None)
    print("\nLADDER AGENTICA COMPLETA")
    return 0


if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "severino-sim"
    ids = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["T055"])
    spec = sys.argv[3] if len(sys.argv) > 3 else "B2"
    a = {"B2": B2, "B4": B4, "all": B2 + B4,
         "SMOKE": SMOKE}.get(spec, spec.split(","))
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    sys.exit(main(prof, ids, a, n))
