"""Ledger Builder (PS1) — la memoria esterna deterministica del task.

PS-D7: M non riceve mai lo storico grezzo. Il ledger si RICOSTRUISCE da DB +
AST + esiti gate (mai dal modello), si renderizza in data/tasks/<id>/plan/
ledger.md (ricercabile coi tool), e per ogni fase se ne PROIETTA il minimo
budgetato nel prompt. Zero chiamate LLM in questo modulo (PS-D1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from redgiant.plansys.artifacts import MacroPlan, PhaseAnalysis, PhaseBlueprint
from redgiant.plansys.astscan import file_signatures
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope

_TEXT_MAX = 300


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["signature", "test", "artifact", "decision", "failure", "fact"]
    ref: str
    text: str = Field(max_length=_TEXT_MAX)


class TaskLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    entries: list[LedgerEntry]


def _entry(kind: str, ref: str, text: str) -> LedgerEntry:
    return LedgerEntry(kind=kind, ref=ref, text=text[:_TEXT_MAX])


def _touched_paths(store: StateStore, scope: Scope, task_id: str) -> list[Path]:
    """File .py dentro lo Scope citati dalle tool call del task + dagli inputs
    dei blueprint persistiti. Ordinati e deduplicati: il ledger e' deterministico."""
    rels: set[str] = set()
    with store._conn() as c:  # lettura pura; il write-path resta in store.py
        rows = c.execute("SELECT args FROM tool_calls WHERE task_id=?",
                         (task_id,)).fetchall()
    for r in rows:
        try:
            args = json.loads(r["args"])
        except (json.JSONDecodeError, TypeError):
            continue
        p = args.get("path")
        if isinstance(p, str):
            rels.add(p)
    for row in store.list_ps_artifacts(task_id, kind="phase_blueprint"):
        bp = PhaseBlueprint.model_validate_json(row["json"])
        for m in bp.micro:
            rels.update(m.work.files_owned)
            rels.update(m.work.inputs)
    out: list[Path] = []
    for rel in sorted(rels):
        if not rel.endswith(".py"):
            continue
        try:
            real = scope.check_read(rel)
        except Exception:
            continue
        if real.is_file():
            out.append(real)
    return out


def build_ledger(store: StateStore, scope: Scope, task_id: str) -> TaskLedger:
    entries: list[LedgerEntry] = []

    # 0. listato repo come fact (max 40): a task fresco e' l'UNICO ancoraggio
    #    possibile per gli 'involved' di M1 (anti-invenzione senza storia)
    listed = 0
    for p in sorted(scope.root.rglob("*")):
        if p.is_dir() or ".git" in p.parts or p.suffix in (".db", ".rgedit"):
            continue
        rel = p.relative_to(scope.root).as_posix()
        entries.append(_entry("fact", rel, "exists"))
        listed += 1
        if listed >= 40:
            entries.append(_entry("fact", "...", "repo listing truncated at 40"))
            break

    # 1. firme reali (AST) dei file toccati — la verita' sul codice, mai ricordata
    for real in _touched_paths(store, scope, task_id):
        rel = real.relative_to(scope.root).as_posix()
        sigs = file_signatures(real)
        if not sigs:
            entries.append(_entry("failure", rel, "unparseable (syntax error?)"))
            continue
        for s in sigs:
            entries.append(_entry("signature", rel, s))

    # 2. test esistenti nello scope (file test_*)
    for t in sorted(scope.root.rglob("test_*.py")):
        rel = t.relative_to(scope.root).as_posix()
        names = [s for s in file_signatures(t) if "def test" in s]
        entries.append(_entry("test", rel, f"{len(names)} tests: "
                              + ", ".join(n.split("(")[0].replace("def ", "")
                                          for n in names[:8])))

    # 3. decisioni: tabella decisions + DesignDecision dalle analisi persistite
    for d in store.list_decisions(task_id):
        entries.append(_entry("decision", f"{d['actor']}",
                              f"{d['decision']}: {d['reason']}"))
    for row in store.list_ps_artifacts(task_id, kind="phase_analysis"):
        an = PhaseAnalysis.model_validate_json(row["json"])
        for dd in an.decisions:
            entries.append(_entry("decision", dd.id,
                                  f"{dd.decision} (constraint: {dd.constraint})"))

    # 4. fallimenti: gate non-ok (firma corta: gate + primo check ko)
    for g in store.ps_gate_history(task_id):
        if g["ok"]:
            continue
        try:
            checks = json.loads(g["checks"])
            first_ko = next((c["name"] for c in checks if not c.get("ok")), "?")
        except (json.JSONDecodeError, StopIteration, TypeError):
            first_ko = "?"
        entries.append(_entry("failure", f"{g['gate']}:{g['target']}", first_ko))

    # 5. artefatti prodotti: sottofasi completate -> expected_outputs
    for r in store.list_subtasks(task_id):
        if r["status"] in ("completed", "completed_with_warnings"):
            spec, _, _ = store.get_subtask(task_id, r["subtask_id"])
            for outp in spec.expected_outputs:
                entries.append(_entry("artifact", outp,
                                      f"produced by {r['subtask_id']}"))

    return TaskLedger(task_id=task_id, entries=entries)


def render_ledger(ledger: TaskLedger) -> str:
    out = ["# Task Ledger", ""]
    for kind in ("signature", "test", "artifact", "decision", "failure", "fact"):
        block = [e for e in ledger.entries if e.kind == kind]
        if not block:
            continue
        out += [f"## {kind.capitalize()}s", ""]
        out += [f"- `{e.ref}` — {e.text}" for e in block] + [""]
    return "\n".join(out)


def project_for_phase(ledger: TaskLedger, plan: MacroPlan, phase_id: str,
                      max_tokens: int, count: Callable[[str], int]) -> str:
    """La Phase Context Projection (PS1.2). Ordine di riempimento NORMATIVO:
    (1) criteri coperti dalla fase; (2) intent; (3) firme/test; (4) decisioni;
    (5) failure; il resto cade con troncamento DICHIARATO. Gli obbligatori
    (1)(2) entrano sempre: se non ci stanno, e' il budget a essere sbagliato."""
    phase = next(p for p in plan.phases if p.id == phase_id)
    crit = {c.id: c.text for c in plan.criteria}
    mandatory = [f"[PHASE] {phase.id} — {phase.title}: {phase.intent}"]
    mandatory += [f"[CRITERION] {cid}: {crit[cid]}" for cid in phase.covers
                  if cid in crit]

    optional: list[str] = []
    for kind, tag in (("signature", "SIG"), ("test", "TEST"),
                      ("decision", "DECISION"), ("failure", "FAILURE"),
                      ("artifact", "ARTIFACT"), ("fact", "FACT")):
        optional += [f"[{tag}] {e.ref}: {e.text}"
                     for e in ledger.entries if e.kind == kind]

    lines = list(mandatory)
    used = count("\n".join(lines))
    truncated = False
    for ln in optional:
        cost = count(ln) + 1
        if used + cost > max_tokens:
            truncated = True
            break
        lines.append(ln)
        used += cost
    if truncated:
        lines.append("[LEDGER TRUNCATED — search plan/ledger.md via tools for more]")
    return "\n".join(lines)
