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

# (nome braccio) -> (RG_WORKER_ABLATE, RG_THINKING_ROLES)
# B2 = workflow senza thinking (full + ablazioni) · B4 = workflow CON thinking
ARMS = {
    "full": ("", ""),
    "-search": ("search", ""),
    "-verify": ("verify", ""),
    "-retry": ("retry", ""),
    "-calc": ("calc", ""),                      # la calcolatrice deterministica
    "-coherence": ("coherence", ""),            # la guardia F4 sull'aritmetica
    "-finishgate": ("finishgate", ""),          # il gate sul finish fantasma
    "think": ("", "worker"),                    # B4: percorso diretto = Giano
    "think-search": ("search", "worker"),       # B4 SPECCHIA B2 ablazione per
    "think-verify": ("verify", "worker"),       # ablazione: il ragionamento
    "think-retry": ("retry", "worker"),         # compensa il pezzo mancante?
    "think-calc": ("calc", "worker"),
    "think-coherence": ("coherence", "worker"),
    "think-finishgate": ("finishgate", "worker"),
}
# simmetria obbligatoria (utente 2026-08-03): stesse ablazioni nei due blocchi
B2 = ["full", "-search", "-verify", "-retry", "-calc", "-coherence", "-finishgate"]
B4 = ["think", "think-search", "think-verify", "think-retry", "think-calc",
      "think-coherence", "think-finishgate"]
# smoke GPU: i bracci piu' informativi, con N run per avere statistica
SMOKE = ["full", "-finishgate", "-coherence", "-search"]


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
        ablate, thinking = ARMS[arm]
        for var, val in (("RG_WORKER_ABLATE", ablate),
                         ("RG_THINKING_ROLES", thinking)):
            if val:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)
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
    os.environ.pop("RG_WORKER_ABLATE", None)
    os.environ.pop("RG_THINKING_ROLES", None)
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
