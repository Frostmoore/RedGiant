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
                artifacts=["mod.py", "helper.py"], decisions=[], risks=[])
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
                                                                 ("helper.py",))])
    assert validate_blueprint(good, an, ["C1"]) == []
    # PS-D4: una micro non puo' possedere file di test (li scrive il compiler)
    tests_owned = PhaseBlueprint(phase_id="P1",
                                 micro=[_micro(files=("test_mod.py",))])
    assert any("FORBIDDEN" in p for p in validate_blueprint(tests_owned, an,
                                                            ["C1"]))
    dup = PhaseBlueprint(phase_id="P1", micro=[_micro(), _micro("P1.S2")])
    assert any("EXCLUSIVE" in p for p in validate_blueprint(dup, an, ["C1"]))
    alien = PhaseBlueprint(phase_id="P1", micro=[_micro(files=("alien.py",))])
    assert any("neither in the" in p for p in validate_blueprint(alien, an, ["C1"]))
    wrong_c = PhaseBlueprint(phase_id="P1", micro=[_micro(proves=("C9",))])
    assert any("does not cover" in p for p in validate_blueprint(wrong_c, an, ["C1"]))


def test_validate_blueprint_prose_outside_perimeter():
    # PS5.5 tentativo 4: goal che ordina di creare file di un'altra micro
    an = _analysis(artifacts=["mod.py", "helper.py", "storage.py"])
    m = _micro()
    m.work.goal = "Create both storage.py and mod.py with the functions"
    bp = PhaseBlueprint(phase_id="P1", micro=[m])
    probs = validate_blueprint(bp, an, ["C1"], existing=set())
    assert any("chase files" in p and "storage.py" in p for p in probs)
    # citare un file esistente o nei propri inputs resta legittimo
    m2 = _micro()
    m2.work.goal = "Extend helper.py reading mod.py"
    m2.work.inputs = ["helper.py"]
    bp2 = PhaseBlueprint(phase_id="P1", micro=[m2])
    assert validate_blueprint(bp2, an, ["C1"],
                              existing={"helper.py"}) == []


def test_enum_schema_injection():
    # batch20, strategia n.1: enum dinamici nei punti giusti dello schema
    from redgiant.plansys.artifacts import (PhaseAnalysis as PA,
                                            PhaseBlueprint as PB,
                                            VerificationBlueprint as VB)
    s = PhaseCompiler._enum_schema(PA, [(None, "involved", ["a.py"], True)])
    assert s["properties"]["involved"]["items"]["enum"] == ["a.py"]
    s2 = PhaseCompiler._enum_schema(PB, [
        ("WorkContract", "files_owned", ["m.py"], True),
        ("MicroPhase", "proves", ["C1"], True)])
    assert s2["$defs"]["WorkContract"]["properties"]["files_owned"]["items"]["enum"] == ["m.py"]
    assert s2["$defs"]["MicroPhase"]["properties"]["proves"]["items"]["enum"] == ["C1"]
    s3 = PhaseCompiler._enum_schema(VB, [("ProofObligation", "cmd_id",
                                          ["pytest"], False)])
    assert s3["$defs"]["ProofObligation"]["properties"]["cmd_id"]["enum"] == ["pytest"]
    # valori vuoti -> nessuna specializzazione
    assert PhaseCompiler._enum_schema(PA, [(None, "involved", [], True)]) is None


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


def test_work_order_scoped_verification():
    # PS5.1: verification = SOLO le prove della micro (proof:*), mai la suite
    from redgiant.plansys.artifacts import (ProofObligation,
                                            VerificationBlueprint)
    from redgiant.plansys.engine import work_order
    micro = _micro()
    vbp = VerificationBlueprint(phase_id="P1", synthesis_cmds=["pytest"],
                                obligations=[ProofObligation(
                                    id="P1.S1.O1", micro_id="P1.S1",
                                    kind="new_behavior", behavior="beh",
                                    test_file="test_mod.py", test_name="test_x",
                                    cmd_id="pytest")])
    spec = work_order(micro, vbp)
    assert spec.id == "P1.S1" and spec.phase_id == "P1"
    assert spec.verification == ["proof:P1.S1.O1"]
    assert "BOUNDARY: b" in spec.objective and "test_mod.py::test_x" in spec.objective
    assert spec.completion_criteria == ["beh"]


def test_retry_gate_blocks_photocopy():
    from redgiant.plansys.gates import failure_signature, retry_gate
    s1 = failure_signature(["test:proof:P1.S1.O1"], "Tests   FAILED badly")
    s2 = failure_signature(["test:proof:P1.S1.O1"], "tests failed BADLY")
    assert s1 == s2                                   # normalizzazione
    assert retry_gate(None, s1).ok                    # primo fallimento: retry lecito
    assert not retry_gate(s1, s2).ok                  # fotocopia: vietato
    s3 = failure_signature(["output:mod.py"], "different failure")
    assert retry_gate(s1, s3).ok


def test_engine_phase_bookkeeping(tmp_path):
    # PS5.3: done set dai gate ok; eleggibilita' per dipendenze; proof commands
    from redgiant.config import Config as _C
    from redgiant.plansys.artifacts import (Criterion, MacroPhase, MacroPlan,
                                            ProofObligation,
                                            VerificationBlueprint)
    from redgiant.plansys.engine import PlanSysEngine
    from redgiant.prompts.assemble import PromptAssembler
    from redgiant.state.models import Budget
    from redgiant.state.store import StateStore
    from redgiant.tools.base import Scope
    from redgiant.tools.router import ToolRouter, default_catalog
    cfg = _C.load("dev-fast", CONFIG_DIR)
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("t", str(tmp_path), "dev-fast",
                            Budget(max_total_tokens=9, max_tool_calls=9,
                                   max_retries_per_subtask=1, max_wall_s=9))
    scope = Scope(tmp_path, ["*.py"])
    router = ToolRouter(default_catalog(cfg, scope,
                                        {"pytest": ["pytest", "-q"]}),
                        scope, store)
    asm = PromptAssembler(Path(__file__).resolve().parents[2] / "redgiant" / "prompts")
    eng = PlanSysEngine(cfg, store, llm=None, router=router, assembler=asm)
    plan = MacroPlan(goal="g", criteria=[Criterion(id="C1", text="t")],
                     phases=[MacroPhase(id="P1", title="a", intent="i",
                                        depends_on=[], covers=["C1"]),
                            MacroPhase(id="P2", title="b", intent="i",
                                       depends_on=["P1"], covers=["C1"])])
    assert eng._eligible_macro_phase(tid, plan).id == "P1"   # P2 aspetta P1
    store.log_ps_gate(tid, gate="phase_synthesis", target="P1", ok=True,
                      checks_json="[]")
    assert eng._eligible_macro_phase(tid, plan).id == "P2"
    store.log_ps_gate(tid, gate="phase_entry", target="P2", ok=True,
                      checks_json="[]")
    assert eng._eligible_macro_phase(tid, plan) is None      # tutte chiuse
    vbp = VerificationBlueprint(phase_id="P1", synthesis_cmds=["pytest"],
                                obligations=[ProofObligation(
                                    id="P1.S1.O1", micro_id="P1.S1",
                                    kind="new_behavior", behavior="b",
                                    test_file="test_m.py", test_name="test_x",
                                    cmd_id="pytest")])
    eng._register_proof_commands(vbp)
    assert "proof:P1.S1.O1" in eng._test_cmd_ids()           # prova registrata


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
