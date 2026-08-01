"""F1.5/F1.6 — validator del WorkerStep e trust boundary della verifica."""

from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.core.verify import verify_subtask
from redgiant.roles.worker import FinishReport, ToolCallSpec, WorkerStep
from redgiant.state.models import Budget, SubtaskSpec
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter, default_catalog

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _spec(**kw):
    base = dict(id="P1.S1", phase_id="P1", title="t", objective="o", inputs=[],
                tools=[], expected_outputs=[], completion_criteria=[], verification=[])
    base.update(kw)
    return SubtaskSpec(**base)


@pytest.fixture()
def env(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    scope = Scope(tmp_path, ["*.py"])
    cfg = Config.load("dev-fast", CONFIG_DIR)
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("t", str(tmp_path), "dev-fast",
                            Budget(max_total_tokens=1, max_tool_calls=99,
                                   max_retries_per_subtask=1, max_wall_s=99))
    router = ToolRouter(default_catalog(cfg, scope, {}), scope, store)
    return scope, router, tid


def _done(evidence=("did it",)):
    return FinishReport(status="done", summary="s", evidence=list(evidence),
                        verification_requested=[])


def test_blocked_never_passes(env):
    scope, router, tid = env
    rep = FinishReport(status="blocked", summary="stuck", evidence=["e"],
                       verification_requested=[])
    v = verify_subtask(_spec(), rep, scope, router, tid)
    assert v.verdict == "fail"
    assert any(c.name == "worker_done" and not c.ok for c in v.checks)


def test_done_with_evidence_and_existing_output_passes(env):
    scope, router, tid = env
    v = verify_subtask(_spec(expected_outputs=["a.py"]), _done(), scope, router, tid)
    assert v.verdict == "pass"


def test_missing_output_fails(env):
    scope, router, tid = env
    v = verify_subtask(_spec(expected_outputs=["ghost.py"]), _done(), scope, router, tid)
    assert v.verdict == "fail"


def test_no_evidence_fails(env):
    scope, router, tid = env
    v = verify_subtask(_spec(), _done(evidence=()), scope, router, tid)
    assert v.verdict == "fail"


def test_unknown_verification_is_a_failure_not_a_skip(env):
    scope, router, tid = env
    v = verify_subtask(_spec(verification=["mystery_check"]), _done(), scope, router, tid)
    assert v.verdict == "fail"
    assert any("unknown" in c.name for c in v.checks)


def test_workerstep_incoherence_is_data_not_validation_error():
    # La coerenza cross-campo NON e' un validator (la grammatica non puo'
    # esprimerla): il modello la accetta e il loop la gestisce come dato.
    s = WorkerStep(thought="t", action="tool", tool_call=None, finish=None)
    assert s.incoherence() == "action=tool but tool_call is null"
    s = WorkerStep(thought="t", action="finish", tool_call=None, finish=None)
    assert "finish is null" in s.incoherence()
    ok = WorkerStep(thought="t", action="tool",
                    tool_call=ToolCallSpec(tool="read_file", args={"path": "a"}))
    assert ok.incoherence() is None
