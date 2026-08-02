"""PS1 — Ledger Builder e Phase Context Projection."""

from pathlib import Path

from redgiant.plansys.artifacts import Criterion, MacroPhase, MacroPlan
from redgiant.plansys.astscan import file_signatures
from redgiant.plansys.ledger import build_ledger, project_for_phase, render_ledger
from redgiant.state.models import Budget, ToolCallRow
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope


def _env(tmp_path):
    (tmp_path / "mod.py").write_text(
        "class Acc:\n    def take(self, amount: int) -> int:\n        return amount\n"
        "def top() -> None:\n    pass\n", encoding="utf-8")
    (tmp_path / "test_mod.py").write_text(
        "def test_take():\n    assert True\n", encoding="utf-8")
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("t", str(tmp_path), "dev-fast",
                            Budget(max_total_tokens=1, max_tool_calls=9,
                                   max_retries_per_subtask=1, max_wall_s=9))
    scope = Scope(tmp_path, ["*.py"])
    return store, scope, tid


def test_file_signatures_qualified(tmp_path):
    (tmp_path / "x.py").write_text(
        "class A:\n    def m(self, k: int) -> str:\n        return ''\n",
        encoding="utf-8")
    sigs = file_signatures(tmp_path / "x.py")
    assert sigs[0] == "class A" and sigs[1].startswith("A.def m(")
    (tmp_path / "broken.py").write_text("def x(:\n", encoding="utf-8")
    assert file_signatures(tmp_path / "broken.py") == []


def test_build_ledger_deterministic(tmp_path):
    store, scope, tid = _env(tmp_path)
    store.log_tool_call(tid, ToolCallRow(subtask_id=None, tool="read_file",
                                         args={"path": "mod.py"}, ok=True,
                                         evidence=[], duration_ms=1.0))
    store.add_decision(tid, actor="user", decision="use-int", reason="r")
    l1 = build_ledger(store, scope, tid)
    l2 = build_ledger(store, scope, tid)
    assert l1 == l2                                   # determinismo
    sigs = [e for e in l1.entries if e.kind == "signature"]
    assert any(e.text == "class Acc" for e in sigs)   # firme vere via AST
    assert any(e.text.startswith("Acc.def take(") for e in sigs)
    assert any(e.kind == "test" and "test_take" in e.text for e in l1.entries)
    assert any(e.kind == "decision" and "use-int" in e.text for e in l1.entries)
    md = render_ledger(l1)
    assert "## Signatures" in md and "`mod.py`" in md


def test_projection_budget(tmp_path):
    store, scope, tid = _env(tmp_path)
    store.log_tool_call(tid, ToolCallRow(subtask_id=None, tool="read_file",
                                         args={"path": "mod.py"}, ok=True,
                                         evidence=[], duration_ms=1.0))
    ledger = build_ledger(store, scope, tid)
    plan = MacroPlan(goal="g", criteria=[Criterion(id="C1", text="crit")],
                     phases=[MacroPhase(id="P1", title="t", intent="intent",
                                        depends_on=[], covers=["C1"])])
    count = lambda s: len(s.split())                  # contatore fittizio ma reale
    full = project_for_phase(ledger, plan, "P1", max_tokens=10_000, count=count)
    assert "[PHASE] P1" in full and "[CRITERION] C1: crit" in full
    assert "[SIG] mod.py" in full and "TRUNCATED" not in full
    tiny = project_for_phase(ledger, plan, "P1", max_tokens=12, count=count)
    assert "[PHASE] P1" in tiny and "[CRITERION] C1: crit" in tiny  # obbligatori SEMPRE
    assert "TRUNCATED" in tiny                        # e il taglio e' dichiarato
