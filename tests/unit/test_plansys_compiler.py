"""PS3 — validatori M1/M2 e meccanica delle patch del PhaseCompiler."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from redgiant.config import Config
from redgiant.plansys.artifacts import (BlueprintPatch, ChoicePoint,
                                        DesignDecision, MacroPhase, MicroPhase,
                                        PatchOp, PhaseAnalysis, PhaseBlueprint,
                                        WorkContract)
from redgiant.plansys.compiler import (CompileFailed, NeedsDecision,
                                       PhaseCompiler)
from redgiant.plansys.gates import validate_analysis, validate_blueprint

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _analysis(**kw) -> PhaseAnalysis:
    base = dict(phase_id="P1", objective="o", involved=[],
                artifacts=["mod.py", "test_mod.py"], decisions=[], risks=[])
    base.update(kw)
    return PhaseAnalysis(**base)


def _micro(mid="P1.S1", files=("mod.py",), proves=("C1",)) -> MicroPhase:
    return MicroPhase(id=mid, title="t", proves=list(proves),
                      work=WorkContract(goal="g", boundary="b",
                                        files_owned=list(files), signatures=[],
                                        inputs=[], outputs=list(files)))


def test_validate_analysis_anti_invention():
    proj = "[SIG] mod.py: class Acc\n[MACRO PHASE] P1"
    ok = _analysis(involved=["mod.py"])
    assert validate_analysis(ok, proj, "P1") == []
    invented = _analysis(involved=["ghost.py"])
    probs = validate_analysis(invented, proj, "P1")
    assert any("ghost.py" in p and "never invent" in p for p in probs)
    dup = _analysis(decisions=[DesignDecision(id="P1.D1", decision="d",
                                              alternatives=[], constraint="c")] * 2)
    assert any("duplicate decision" in p for p in validate_analysis(dup, proj, "P1"))


def test_validate_blueprint_exclusive_ownership():
    an = _analysis()
    good = PhaseBlueprint(phase_id="P1", micro=[_micro(), _micro("P1.S2",
                                                                 ("test_mod.py",))])
    assert validate_blueprint(good, an, ["C1"]) == []
    dup = PhaseBlueprint(phase_id="P1", micro=[_micro(), _micro("P1.S2")])
    assert any("EXCLUSIVE" in p for p in validate_blueprint(dup, an, ["C1"]))
    alien = PhaseBlueprint(phase_id="P1", micro=[_micro(files=("alien.py",))])
    assert any("neither in the" in p for p in validate_blueprint(alien, an, ["C1"]))
    wrong_c = PhaseBlueprint(phase_id="P1", micro=[_micro(proves=("C9",))])
    assert any("does not cover" in p for p in validate_blueprint(wrong_c, an, ["C1"]))


def test_apply_patch_replace_add_remove():
    bp = PhaseBlueprint(phase_id="P1", micro=[_micro(), _micro("P1.S2",
                                                               ("test_mod.py",))])
    fixed = _micro("P1.S2", ("test_mod.py",), proves=("C1",))
    patch = BlueprintPatch(phase_id="P1", ops=[
        PatchOp(op="replace", target="P1.S2",
                payload_json=fixed.model_dump_json()),
        PatchOp(op="remove", target="P1.S1", payload_json="")])
    out = json.loads(PhaseCompiler._apply_patch(PhaseBlueprint,
                                                bp.model_dump_json(), patch))
    assert [m["id"] for m in out["micro"]] == ["P1.S2"]
    with pytest.raises(ValueError):
        PhaseCompiler._apply_patch(PhaseBlueprint, bp.model_dump_json(),
                                   BlueprintPatch(phase_id="P1", ops=[
                                       PatchOp(op="replace", target="P9.S9",
                                               payload_json=fixed.model_dump_json())]))


class _Log:
    def line(self, actor, msg):
        pass


def _compiler(tmp_path, llm):
    from redgiant.prompts.assemble import PromptAssembler
    from redgiant.state.models import Budget
    from redgiant.state.store import StateStore
    from redgiant.tools.base import Scope
    cfg = Config.load("dev-fast", CONFIG_DIR)
    object.__setattr__(cfg.paths, "tasks_dir", tmp_path)
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("t", str(tmp_path), "dev-fast",
                            Budget(max_total_tokens=9, max_tool_calls=9,
                                   max_retries_per_subtask=1, max_wall_s=9))
    asm = PromptAssembler(Path(__file__).resolve().parents[2] / "redgiant" / "prompts")
    scope = Scope(tmp_path, ["*.py"])
    comp = PhaseCompiler(cfg, store, llm, asm, router=None, scope=scope)
    return comp, store, tid


class _SeqLlm:
    """Mock: sequenza di .parsed; count_tokens finto per la proiezione."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def complete(self, parts, **kw):
        self.calls += 1
        return SimpleNamespace(parsed=self.outputs.pop(0))

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def test_analyze_patch_flow_and_needs_decision(tmp_path):
    phase = MacroPhase(id="P1", title="t", intent="i", depends_on=[],
                       covers=["C1"])
    bad = _analysis(involved=["ghost.py"])
    fix_patch = BlueprintPatch(phase_id="P1", ops=[
        PatchOp(op="remove", target="none", payload_json="")])
    # la patch non tocca 'involved' (lista non patchabile) -> il loop esaurisce
    # le patch e passa alla rigenerazione unica, che qui restituisce l'analisi buona
    good = _analysis(involved=[])
    llm = _SeqLlm([bad, fix_patch, fix_patch, good])
    comp, store, tid = _compiler(tmp_path, llm)
    from redgiant.plansys.artifacts import Criterion, MacroPlan
    plan = MacroPlan(goal="g", criteria=[Criterion(id="C1", text="t")],
                     phases=[phase])
    out = comp.analyze(tid, plan, phase, "proiezione senza ghost", _Log())
    assert out == good and llm.calls == 4
    assert store.load_ps_artifact(tid, "phase_analysis", "P1")["version"] == 1

    # decision_required -> NeedsDecision, analisi comunque persistita
    ask = _analysis(decision_required=ChoicePoint(
        question="q?", options=["a", "b"], recommended="a", reason="r"))
    llm2 = _SeqLlm([ask])
    comp2, store2, tid2 = _compiler(tmp_path / "b", llm2)
    with pytest.raises(NeedsDecision):
        comp2.analyze(tid2, plan, phase, "p", _Log())
    assert store2.load_ps_artifact(tid2, "phase_analysis", "P1")


def test_compile_failed_after_regeneration(tmp_path):
    phase = MacroPhase(id="P1", title="t", intent="i", depends_on=[],
                       covers=["C1"])
    bad = _analysis(involved=["ghost.py"])
    nopatch = BlueprintPatch(phase_id="P1", ops=[
        PatchOp(op="remove", target="x", payload_json="")])
    llm = _SeqLlm([bad, nopatch, nopatch, bad])   # anche la rigenerazione e' cattiva
    comp, store, tid = _compiler(tmp_path, llm)
    from redgiant.plansys.artifacts import Criterion, MacroPlan
    plan = MacroPlan(goal="g", criteria=[Criterion(id="C1", text="t")],
                     phases=[phase])
    with pytest.raises(CompileFailed) as e:
        comp.analyze(tid, plan, phase, "clean projection", _Log())
    assert e.value.step == "M1"
