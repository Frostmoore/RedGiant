"""Plansys — il sistema di pianificazione S/M/J + Control Plane.

Piano di riferimento: memory/plan_planner_system.md (le firme qui dentro sono
il contratto di quel documento). Regola PS-D1: in questo package le chiamate
LLM vivono SOLO in roles.py e compiler.py; tutto il resto e' deterministico.
"""

import os


def thinking_roles() -> set[str]:
    """TH0.3 — leva di solo-esperimento (mai contratto config, come le
    ablation): RG_THINKING_ROLES = nomi ruolo REALI del DB, separati da
    virgola (senior_planner, phase_analyst, work_decomposer,
    verification_designer, test_author, worker)."""
    v = os.environ.get("RG_THINKING_ROLES", "").strip()
    return {r.strip() for r in v.split(",") if r.strip()} if v else set()


def thinking_budget() -> int:
    """TH0.3 — FUSIBILE del canale di pensiero, non bersaglio (decisione
    utente 2026-08-03): misurato sul GGUF, il modello chiude il canale da
    solo a 322-543 token; 1536 non scatta mai in condizioni normali e limita
    il caso patologico a ~43s su severino (F12: l'uscita esiste sempre)."""
    return int(os.environ.get("RG_THINKING_BUDGET", "1536"))


def ablated(component: str) -> bool:
    """PS6.2 — leva per le ablation dell'A/B (mai in produzione): la env var
    RG_PLANSYS_ABLATE="oracle,ledger,entry" spegne il componente indicato."""
    return component in os.environ.get("RG_PLANSYS_ABLATE", "").split(",")
