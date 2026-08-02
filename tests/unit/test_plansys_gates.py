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

    llm2 = _Llm([bad, bad, bad])   # fast #4: 2 correttive -> 3 chiamate totali
    s2 = SeniorPlanner(llm=llm2, assembler=asm, router=None)
    try:
        s2.run(ctx)
        raise AssertionError("doveva alzare MacroRejected")
    except MacroRejected as e:
        assert any("coverage_total" in p for p in e.problems)


def _mk(tmp_path, name, content):
    (tmp_path / name).write_text(content, encoding="utf-8")


def _fixture_repo(tmp_path):
    from redgiant.plansys.artifacts import (MicroPhase, PhaseBlueprint,
                                            ProofObligation, TestArtifact,
                                            TestBundle, VerificationBlueprint,
                                            WorkContract)
    from redgiant.tools.base import Scope
    _mk(tmp_path, "mod.py", "def add(a: int, b: int) -> int:\n    return a + b\n")
    bp = PhaseBlueprint(phase_id="P1", micro=[MicroPhase(
        id="P1.S1", title="t", proves=["C1"],
        work=WorkContract(goal="g", boundary="b", files_owned=["mod.py"],
                          signatures=["def subtract(a: int, b: int) -> int"],
                          inputs=[], outputs=["mod.py"]))])
    vbp = VerificationBlueprint(phase_id="P1", synthesis_cmds=["pytest"],
                                obligations=[
        ProofObligation(id="P1.S1.O1", micro_id="P1.S1", kind="characterization",
                        behavior="add works", test_file="test_mod.py",
                        test_name="test_add", cmd_id="pytest"),
        ProofObligation(id="P1.S1.O2", micro_id="P1.S1", kind="new_behavior",
                        behavior="subtract missing", test_file="test_mod.py",
                        test_name="test_subtract", cmd_id="pytest")])
    good_tests = ("from mod import add\n\n"
                  "def test_add():\n    assert add(2, 3) == 5\n\n"
                  "def test_subtract():\n    from mod import subtract\n"
                  "    assert subtract(5, 3) == 2\n")
    bundle = TestBundle(phase_id="P1", artifacts=[
        TestArtifact(path="test_mod.py", content=good_tests)])
    return Scope(tmp_path, ["*.py"]), bp, vbp, bundle


def test_validate_verification_rules():
    from redgiant.plansys.artifacts import (MicroPhase, PhaseBlueprint,
                                            ProofObligation,
                                            VerificationBlueprint, WorkContract)
    from redgiant.plansys.gates import validate_verification
    bp = PhaseBlueprint(phase_id="P1", micro=[MicroPhase(
        id="P1.S1", title="t", proves=[],
        work=WorkContract(goal="g", boundary="b", files_owned=["a.py"],
                          signatures=[], inputs=[], outputs=[]))])
    orphan = VerificationBlueprint(phase_id="P1", synthesis_cmds=["ghost"],
                                   obligations=[ProofObligation(
                                       id="O1", micro_id="P9.S9",
                                       kind="new_behavior", behavior="b",
                                       test_file="checks.py", test_name="verify",
                                       cmd_id="pytest test.py")])
    probs = validate_verification(orphan, bp, {"pytest"})
    assert any("has NO proof obligation" in p for p in probs)      # micro scoperta
    assert any("unknown micro" in p for p in probs)
    assert any("not a known test command" in p for p in probs)     # cmd inventato
    assert any("must be named test_*.py" in p for p in probs)
    assert any("must start with 'test'" in p for p in probs)
    assert any("synthesis cmd 'ghost'" in p for p in probs)


def test_oracle_gate_qualifies_good_oracle(tmp_path):
    from redgiant.plansys.gates import oracle_qualification_gate
    scope, bp, vbp, bundle = _fixture_repo(tmp_path)
    _mk(tmp_path, "test_mod.py", bundle.artifacts[0].content)   # materializzato
    rep = oracle_qualification_gate(vbp, bundle, bp, scope, None, "T")
    assert rep.ok, [c.model_dump() for c in rep.checks if not c.ok]
    # red-baseline provata davvero: il new_behavior fallisce ORA
    assert any(c.name == "P1.S1.O2:baseline_new_behavior" and c.ok
               for c in rep.checks)


def test_oracle_gate_rejects_weak_oracles(tmp_path):
    from redgiant.plansys.artifacts import TestArtifact, TestBundle
    from redgiant.plansys.gates import oracle_qualification_gate
    scope, bp, vbp, _ = _fixture_repo(tmp_path)
    weak = ("def test_add():\n    assert True\n\n"                 # tautologia
            "def test_subtract():\n    x = 1\n    assert x == 1\n")  # scollegato
    bundle = TestBundle(phase_id="P1", artifacts=[
        TestArtifact(path="test_mod.py", content=weak)])
    _mk(tmp_path, "test_mod.py", weak)
    rep = oracle_qualification_gate(vbp, bundle, bp, scope, None, "T")
    assert not rep.ok
    ko = {c.name for c in rep.checks if not c.ok}
    assert "P1.S1.O1:asserts" in ko                                # tautologia beccata
    assert "P1.S1.O2:targets_contract" in ko                       # niente aggancio


def test_oracle_gate_rejects_passing_new_behavior(tmp_path):
    from redgiant.plansys.artifacts import TestArtifact, TestBundle
    from redgiant.plansys.gates import oracle_qualification_gate
    scope, bp, vbp, _ = _fixture_repo(tmp_path)
    # 'new_behavior' che gia' passa: non prova nessun comportamento nuovo
    cheating = ("from mod import add\n\n"
                "def test_add():\n    assert add(2, 3) == 5\n\n"
                "def test_subtract():\n    assert add(5, -3) == 2\n")
    bundle = TestBundle(phase_id="P1", artifacts=[
        TestArtifact(path="test_mod.py", content=cheating)])
    _mk(tmp_path, "test_mod.py", cheating)
    rep = oracle_qualification_gate(vbp, bundle, bp, scope, None, "T")
    assert any(c.name == "P1.S1.O2:baseline_new_behavior" and not c.ok
               for c in rep.checks)


def test_validate_bundle_rules(tmp_path):
    from redgiant.plansys.artifacts import TestArtifact, TestBundle
    from redgiant.plansys.gates import validate_bundle
    _, _, vbp, _ = _fixture_repo(tmp_path)
    broken = TestBundle(phase_id="P1", artifacts=[
        TestArtifact(path="checks.py", content="def test_x(:\n")])
    probs = validate_bundle(broken, vbp)
    assert any("has no artifact" in p for p in probs)      # test_mod.py mancante
    assert any("must be named test_*.py" in p for p in probs)
    assert any("does not parse" in p for p in probs)


def test_config_still_loads():
    cfg = Config.load("dev-fast",
                      Path(__file__).resolve().parents[2] / "config")
    assert cfg.plansys.max_phases == 6
