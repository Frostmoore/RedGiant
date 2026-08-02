"""PS0 — artefatti, persistenza, renderer, config (plan_planner_system.md)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from redgiant.config import Config
from redgiant.plansys.artifacts import (BlueprintPatch, Criterion, MacroPhase,
                                        MacroPlan, MicroPhase, PatchOp,
                                        PhaseBlueprint, ProofObligation,
                                        TestBundle, TestArtifact,
                                        VerificationBlueprint, WorkContract)
from redgiant.plansys.render import (render_blueprint, render_macro_plan,
                                     write_plan_doc)
from redgiant.state.models import Budget
from redgiant.state.store import StateStore

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _plan() -> MacroPlan:
    return MacroPlan(goal="g", criteria=[Criterion(id="C1", text="t")],
                     phases=[MacroPhase(id="P1", title="a", intent="i",
                                        depends_on=[], covers=["C1"])])


def _bp() -> PhaseBlueprint:
    return PhaseBlueprint(phase_id="P1", micro=[MicroPhase(
        id="P1.S1", title="m", proves=["C1"],
        work=WorkContract(goal="g", boundary="b", files_owned=["a.py"],
                          signatures=[], inputs=[], outputs=["a.py"]))])


def _vbp() -> VerificationBlueprint:
    return VerificationBlueprint(phase_id="P1", synthesis_cmds=["pytest"],
                                 obligations=[ProofObligation(
                                     id="P1.S1.O1", micro_id="P1.S1",
                                     kind="new_behavior", behavior="b",
                                     test_file="test_a.py", test_name="test_x",
                                     cmd_id="pytest")])


def test_roundtrip_and_forbid():
    # PS0.1: round-trip identico; extra="forbid" respinge campi ignoti
    for art in (_plan(), _bp(), _vbp(),
                TestBundle(phase_id="P1",
                           artifacts=[TestArtifact(path="t.py", content="x")])):
        assert type(art).model_validate_json(art.model_dump_json()) == art
    with pytest.raises(ValidationError):
        Criterion.model_validate({"id": "C1", "text": "t", "ghost": 1})


def test_limits_bite():
    with pytest.raises(ValidationError):   # covers min_length=1
        MacroPhase(id="P1", title="a", intent="i", depends_on=[], covers=[])
    with pytest.raises(ValidationError):   # files_owned min_length=1
        WorkContract(goal="g", boundary="b", files_owned=[], signatures=[],
                     inputs=[], outputs=[])
    ok = BlueprintPatch(phase_id="P1", ops=[PatchOp(op="remove", target="P1.S1",
                                                    payload_json="")])
    assert ok.ops[0].payload_json == ""    # remove con payload vuoto valida


def test_ps_artifact_versioning(tmp_path):
    # PS0.2: versioni monotone; load senza version = ultima; KeyError se assente
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("t", str(tmp_path), "dev-fast",
                            Budget(max_total_tokens=1, max_tool_calls=1,
                                   max_retries_per_subtask=1, max_wall_s=1))
    v1 = store.save_ps_artifact(tid, kind="macro_plan", ref="",
                                payload_json=_plan().model_dump_json(), actor="senior")
    v2 = store.save_ps_artifact(tid, kind="macro_plan", ref="",
                                payload_json=_plan().model_dump_json(), actor="senior")
    assert (v1, v2) == (1, 2)
    assert store.load_ps_artifact(tid, "macro_plan")["version"] == 2
    assert store.load_ps_artifact(tid, "macro_plan", version=1)["version"] == 1
    with pytest.raises(KeyError):
        store.load_ps_artifact(tid, "phase_blueprint", "P9")
    store.log_ps_gate(tid, gate="macro_validation", target="plan", ok=True,
                      checks_json="[]")
    assert store.ps_gate_history(tid)[0]["gate"] == "macro_validation"


def test_renderer_deterministic_and_greppable(tmp_path):
    # PS0.3: byte-identico tra due render; intestazioni con gli id
    md1 = render_blueprint(_bp(), _vbp(), None)
    md2 = render_blueprint(_bp(), _vbp(), None)
    assert md1 == md2
    assert "## P1.S1 — m" in md1 and "P1.S1.O1 [new_behavior]" in md1
    plan_md = render_macro_plan(_plan())
    assert "- [ ] C1: t" in plan_md and "## P1 — a" in plan_md
    p = write_plan_doc(tmp_path, "TASK", "macro_plan", plan_md)
    assert p.read_text(encoding="utf-8") == plan_md
    assert p == tmp_path / "TASK" / "plan" / "macro_plan.md"


def test_plansys_config_defaults():
    # PS0.4: default spento, valori PS-A4
    cfg = Config.load("dev-fast", CONFIG_DIR)
    assert cfg.plansys_enabled is False
    assert cfg.plansys.max_phases == 6
    assert cfg.plansys.projection_max_tokens == 2500
    assert cfg.plansys.mutation_probe is False
