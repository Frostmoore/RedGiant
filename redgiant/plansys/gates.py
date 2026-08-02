"""Gate deterministici del plansys (PS2+). Zero token per costruzione (PS-D1).

Ogni gate produce un GateReport con TUTTI i check eseguiti (mai fermarsi al
primo ko: il quadro completo e' cio' che la patch correttiva deve vedere).
"""

from __future__ import annotations

import re

from redgiant.core.verify import CheckResult
from redgiant.plansys.artifacts import GateReport, MacroPlan


def dag_problems(pairs: list[tuple[str, list[str]]]) -> list[str]:
    """Check condivisi su un grafo (id, depends_on) — estratto da
    roles/planner.py::validate_plan_logic (PS2.2): un solo validatore di
    dipendenze in tutto il repo, messaggi identici a F3."""
    problems: list[str] = []
    ids = [i for i, _ in pairs]
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate phase ids: {ids}")
    known = set(ids)
    for pid, deps in pairs:
        for dep in deps:
            if dep not in known:
                problems.append(f"phase {pid} depends on unknown phase '{dep}'")
            if dep == pid:
                problems.append(f"phase {pid} depends on itself")
    graph = {pid: [d for d in deps if d in known] for pid, deps in pairs}
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    def dfs(node: str) -> bool:
        color[node] = GREY
        for nxt in graph[node]:
            if color[nxt] == GREY or (color[nxt] == WHITE and dfs(nxt)):
                return True
        color[node] = BLACK
        return False

    if any(dfs(n) for n in graph if color[n] == WHITE):
        problems.append("dependency cycle detected")
    if ids and not any(not deps for _, deps in pairs):
        problems.append("no root phase (every phase has dependencies)")
    return problems


def normalize_macro(plan: MacroPlan) -> MacroPlan:
    """Sentinelli inequivoci riparati (stessa politica di roles/planner.py:
    'none'/'null'/... e auto-dipendenza significano 'nessuna dipendenza')."""
    from redgiant.roles.planner import _DEP_SENTINELS
    for p in plan.phases:
        p.depends_on = [d for d in p.depends_on
                        if d.strip().lower() not in _DEP_SENTINELS and d != p.id]
    return plan


_CRIT_ID = re.compile(r"^C\d+$")
_PHASE_ID = re.compile(r"^P\d+$")


def macro_validation_gate(plan: MacroPlan) -> GateReport:
    """PS2.2 — la logica del MacroPlan, validata in codice. Include la matrice
    di copertura (PS-D9/13): un criterio scoperto e' un piano respinto."""
    checks: list[CheckResult] = []

    bad_crit = [c.id for c in plan.criteria if not _CRIT_ID.match(c.id)]
    dup_crit = len({c.id for c in plan.criteria}) != len(plan.criteria)
    checks.append(CheckResult(
        name="criterion_ids", ok=not bad_crit and not dup_crit,
        detail=f"bad: {bad_crit}, duplicates: {dup_crit}"))

    bad_phase = [p.id for p in plan.phases if not _PHASE_ID.match(p.id)]
    checks.append(CheckResult(name="phase_ids", ok=not bad_phase,
                              detail=f"bad: {bad_phase}"))

    dag = dag_problems([(p.id, p.depends_on) for p in plan.phases])
    checks.append(CheckResult(name="dependencies", ok=not dag,
                              detail="; ".join(dag) or "acyclic, root present"))

    crit_ids = {c.id for c in plan.criteria}
    ghost = sorted({cid for p in plan.phases for cid in p.covers
                    if cid not in crit_ids})
    checks.append(CheckResult(name="covers_exist", ok=not ghost,
                              detail=f"unknown criteria referenced: {ghost}"))

    covered = {cid for p in plan.phases for cid in p.covers}
    uncovered = sorted(crit_ids - covered)
    checks.append(CheckResult(
        name="coverage_total", ok=not uncovered,
        detail=f"criteria covered by no phase: {uncovered}" if uncovered
        else "every criterion covered"))

    return GateReport(gate="macro_validation", target="macro_plan",
                      ok=all(c.ok for c in checks), checks=checks)
