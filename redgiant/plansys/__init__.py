"""Plansys — il sistema di pianificazione S/M/J + Control Plane.

Piano di riferimento: memory/plan_planner_system.md (le firme qui dentro sono
il contratto di quel documento). Regola PS-D1: in questo package le chiamate
LLM vivono SOLO in roles.py e compiler.py; tutto il resto e' deterministico.
"""

import os


def ablated(component: str) -> bool:
    """PS6.2 — leva per le ablation dell'A/B (mai in produzione): la env var
    RG_PLANSYS_ABLATE="oracle,ledger,entry" spegne il componente indicato."""
    return component in os.environ.get("RG_PLANSYS_ABLATE", "").split(",")
