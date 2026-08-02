"""PS2 — macro validation gate e SeniorPlanner (corrective re-call)."""

from pathlib import Path
from types import SimpleNamespace

from redgiant.config import Config
from redgiant.plansys.artifacts import Criterion, MacroPhase, MacroPlan
from redgiant.plansys.gates import (dag_problems, macro_validation_gate,
                                    normalize_macro)
from redgiant.plansys.roles import MacroRejected, SeniorPlanner
from redgiant.prompts.assemble import PromptAssembler
from redgiant.roles.base import RoleContext
from redgiant.state.models import Budget
from redgiant.state.store import StateStore

_PROMPTS = Path(__file__).resolve().parents[2] / "redgiant" / "prompts"


def _plan(covers=("C1",), deps=(), cid="C1", pid="P1") -> MacroPlan:
    return MacroPlan(goal="g", criteria=[Criterion(id=cid, text="t")],
                     phases=[MacroPhase(id=pid, title="a", intent="i",
                                        depends_on=list(deps),
                                        covers=list(covers))])


def test_macro_gate_coverage_and_ids():
    ok = macro_validation_gate(_plan())
    assert ok.ok and ok.gate == "macro_validation"
    # criterio scoperto: C1 esiste ma nessuna fase lo copre (copre un fantasma)
    ghost = macro_validation_gate(_plan(covers=("C9",)))
    names_ko = {c.name for c in ghost.checks if not c.ok}
    assert {"covers_exist", "coverage_total"} <= names_ko
    bad = macro_validation_gate(_plan(cid="X1", pid="fase1", covers=("X1",)))
    names_ko = {c.name for c in bad.checks if not c.ok}
    assert {"criterion_ids", "phase_ids"} <= names_ko


def test_macro_gate_dag_and_normalize():
    two = MacroPlan(goal="g", criteria=[Criterion(id="C1", text="t")],
                    phases=[MacroPhase(id="P1", title="a", intent="i",
                                       depends_on=["P2"], covers=["C1"]),
                            MacroPhase(id="P2", title="b", intent="i",
                                       depends_on=["P1"], covers=["C1"])])
    rep = macro_validation_gate(two)
    assert not rep.ok and any("cycle" in c.detail or "root" in c.detail
                              for c in rep.checks if not c.ok)
    selfdep = _plan(deps=("P1", "none"))
    assert macro_validation_gate(normalize_macro(selfdep)).ok
    assert selfdep.phases[0].depends_on == []
    # helper condiviso: stessi messaggi di F3
    probs = dag_problems([("P1", ["ghost"])])
    assert any("unknown phase 'ghost'" in p for p in probs)


def _ctx(tmp_path):
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("build a small tool", str(tmp_path), "dev-fast",
                            Budget(max_total_tokens=9, max_tool_calls=9,
                                   max_retries_per_subtask=1, max_wall_s=9))
    return RoleContext(task=store.load_task(tid), subtask=None, volatile="v")


def test_senior_corrective_recall_then_reject(tmp_path):
    ctx = _ctx(tmp_path)
    bad = _plan(covers=("C9",))          # criterio scoperto -> gate ko
    good = _plan()

    class _Llm:
        def __init__(self, outputs):
            self.outputs = list(outputs)
            self.prompts = []

        def complete(self, parts, **kw):
            self.prompts.append(parts.render())
            return SimpleNamespace(parsed=self.outputs.pop(0))

    asm = PromptAssembler(_PROMPTS)
    llm = _Llm([bad, good])
    s = SeniorPlanner(llm=llm, assembler=asm, router=None)
    out = s.run(ctx)
    assert out == good and len(llm.prompts) == 2
    assert "[PLAN REJECTED]" in llm.prompts[1]        # la richiamata cita le regole
    assert "[RULES]" in llm.prompts[1]

    llm2 = _Llm([bad, bad])
    s2 = SeniorPlanner(llm=llm2, assembler=asm, router=None)
    try:
        s2.run(ctx)
        raise AssertionError("doveva alzare MacroRejected")
    except MacroRejected as e:
        assert any("coverage_total" in p for p in e.problems)


def test_config_still_loads():
    cfg = Config.load("dev-fast",
                      Path(__file__).resolve().parents[2] / "config")
    assert cfg.plansys.max_phases == 6
