"""Leva di ablazione del percorso Worker (regola di metodo 2026-08-03: ogni
misura si fa su tre bracci — nudo, workflow completo, ABLAZIONI — sennò il
delta non e' attribuibile a nessun componente).

Stessa filosofia di `plansys.ablated()`: env var di SOLO A/B, mai contratto di
config, mai in produzione. `RG_WORKER_ABLATE="search,verify,retry"`:
- search: il catalogo perde `search_code` (il modello deve listare e leggere)
- verify: la verifica deterministica NON gira, si crede al report del Worker
  (= "agente senza oracoli", il braccio che misura quanto vale la verifica)
- retry: nessun secondo tentativo (un colpo solo, come il nudo ma con i tool)
- calc: il catalogo perde `calculator` (aritmetica solo mentale)
- coherence: la guardia di coerenza aritmetica in scrittura non gira, cioe'
  un artefatto con un totale sbagliato finisce sul disco (braccio che misura
  quanto vale togliere l'operazione dalle mani del modello invece di
  raccomandargliela — data.md §7.5)

NOTA — non tutto sta qui: un componente MISURATO COME NON PAGANTE non si abla,
si spegne. Il gate sul finish (LAD.9) vive dietro `RG_FINISH_GATE=1` in
`roles/worker.py::finish_gate_enabled`, spento di default, come il planner
(D11) e il thinking (TH3). La convenzione dei bracci lo rispecchia: `-x` abla
un componente attivo, `+x` accende uno spento.
"""

from __future__ import annotations

import os


def worker_ablated(component: str) -> bool:
    return component in os.environ.get("RG_WORKER_ABLATE", "").split(",")


def active_ablations() -> list[str]:
    v = os.environ.get("RG_WORKER_ABLATE", "").strip()
    return [c.strip() for c in v.split(",") if c.strip()] if v else []
