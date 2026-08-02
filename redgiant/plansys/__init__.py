"""Plansys — il sistema di pianificazione S/M/J + Control Plane.

Piano di riferimento: memory/plan_planner_system.md (le firme qui dentro sono
il contratto di quel documento). Regola PS-D1: in questo package le chiamate
LLM vivono SOLO in roles.py e compiler.py; tutto il resto e' deterministico.
"""
