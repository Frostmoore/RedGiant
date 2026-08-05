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

import datetime as _dt
import os
import subprocess
import sys
import time
from pathlib import Path


def log(msg: str) -> None:
    """Regola di progetto (utente 2026-08-05): OGNI test emette log
    timestampati, cosi' i run restano diagnosticabili anche a distanza di
    settimane — i difetti di misura si trovano leggendo artefatti, non
    punteggi, e un artefatto senza tempo non si incrocia con niente."""
    print(f"[{_dt.datetime.now().isoformat(timespec='seconds')}] {msg}",
          flush=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from redgiant.eval.harness import run_eval

# (nome braccio) -> variabili d'ambiente del braccio (le altre vengono azzerate)
# B2 = workflow senza thinking (full + ablazioni) · B4 = workflow CON thinking
# Convenzione: "-x" ABLA un componente attivo, "+x" ACCENDE un componente che
# il progetto tiene spento (verdetto negativo ma aperto, come D11 e TH3).
_ENV_VARS = ("RG_WORKER_ABLATE", "RG_THINKING_ROLES", "RG_FINISH_GATE",
             "RG_CALCULATOR", "RG_WORKER_CARD")
ARMS = {
    "full": {},
    "-search": {"RG_WORKER_ABLATE": "search"},
    "-verify": {"RG_WORKER_ABLATE": "verify"},
    "-retry": {"RG_WORKER_ABLATE": "retry"},
    "-coherence": {"RG_WORKER_ABLATE": "coherence"},  # la guardia F4 sull'aritmetica
    "-compact": {"RG_WORKER_ABLATE": "compact"},     # F5.0-bis: catena volatile
    "card-min": {"RG_WORKER_CARD": "minimal"},       # F5.0-ter: card ridotta
    # F5.6b — il braccio che mette alla prova la SINTESI: se "cercare invece di
    # leggere" e' una sola variabile con piu' leve, il pensiero deve recuperare
    # il crollo della card ridotta (L7: 1/20 -> ?)
    "card-min+think": {"RG_WORKER_CARD": "minimal",
                       "RG_THINKING_ROLES": "worker"},
    # F5.0-quater — bisezione della card: minimal + un gruppo di regole per
    # braccio. A = disciplina d'azione/strumenti (regole 1,5,8,13 della card
    # intera), B = perimetro/focus/stile (regole 2,6,10,11,12). Screening a
    # n=10 contro le ANCORE a n=20 (min 1/20, full 12/20), regole decise
    # prima: >=4/10 = il gruppo orienta; <=1/10 = non orienta; 2-3/10 =
    # estensione a 20.
    "card-bisA": {"RG_WORKER_CARD": "bisect-a"},
    "card-bisB": {"RG_WORKER_CARD": "bisect-b"},
    # F5.0-quinquies — leave-one-out: card INTERA meno la sola regola 10
    # ("il TASK e' sfondo, fai SOLO il tuo obiettivo"), candidata principale
    # emersa dalla bisezione. Verificato meccanicamente: unica differenza da
    # `full`, 12 regole contro 13, ~65 token in meno.
    "card-no10": {"RG_WORKER_CARD": "no10"},
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
    log(f"LADDER AGENTICA @ {sha} — {task_ids} × {arms}")
    out = ROOT / "bench" / "results"
    for arm in arms:
        env = ARMS[arm]
        for var in _ENV_VARS:          # sempre azzerate: nessuna perdita tra bracci
            os.environ.pop(var, None)
        for var, val in env.items():
            os.environ[var] = val
        log(f"[{arm}] env: " + (" ".join(f"{k}={v}" for k, v in env.items())
                                or "(default)"))
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
                log(f"[{arm}] run {n+1}/{runs}: "
                    + " ".join(f"{k}={v}" for k, v in greens.items())
                    + f" — report: {report}")
            except Exception as e:
                log(f"[{arm}] run {n+1} ERRORE: {e}")
        log(f"[{arm}] TOTALE "
            + " ".join(f"{k}={v}/{runs}" for k, v in greens.items())
            + f" in {time.time()-t0:.0f}s")
    for var in _ENV_VARS:
        os.environ.pop(var, None)
    log("LADDER AGENTICA COMPLETA")
    return 0


if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "severino-sim"
    ids = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["T055"])
    spec = sys.argv[3] if len(sys.argv) > 3 else "B2"
    a = {"B2": B2, "B4": B4, "all": B2 + B4,
         "SMOKE": SMOKE}.get(spec, spec.split(","))
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    sys.exit(main(prof, ids, a, n))
