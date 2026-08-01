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


def test_oracles_beat_claims_in_both_directions(env, tmp_path):
    # F2.5: worker blocked MA output esistente + test verdi -> pass (con warning).
    scope, router, tid = env
    (scope.root / "t_ok.py").write_text("def test_ok():\n    assert True\n",
                                        encoding="utf-8")
    from redgiant.config import Config
    from redgiant.tools.router import ToolRouter as _TR, default_catalog as _dc
    cfg = Config.load("dev-fast", CONFIG_DIR)
    router2 = _TR(_dc(cfg, scope, {"pytest": ["pytest", "-q", "t_ok.py"]}),
                  scope, router.store)
    rep = FinishReport(status="blocked", summary="step budget exhausted",
                       evidence=[], verification_requested=[])
    v = verify_subtask(_spec(expected_outputs=["a.py"], verification=["pytest"]),
                       rep, scope, router2, tid)
    assert v.verdict == "pass"
    assert any(not c.ok for c in v.checks)  # i soggettivi restano segnati (warning)


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


def test_resume_reclaims_orphan_running_subtasks(env, tmp_path):
    # F1.7: una sottofase 'running' di un processo morto torna 'pending' alla ripresa
    from redgiant.config import Config
    from redgiant.core.orchestrator import Orchestrator, TaskLog
    scope, router, tid = env
    store = router.store
    store.upsert_subtask(tid, _spec(), actor="t")
    store.set_subtask_status(tid, "P1.S1", "running", actor="orch")
    cfg = Config.load("dev-fast", CONFIG_DIR)
    orch = Orchestrator(cfg, store, llm=None, router=router,  # llm inutilizzato qui
                        assembler=None)
    orch._reclaim_orphans(tid, TaskLog(tmp_path, tid))
    _, status, _ = store.get_subtask(tid, "P1.S1")
    assert status == "pending"


def test_budget_exhaustion_asks_instead_of_killing(env, tmp_path, monkeypatch):
    # F2.5 (richiesta utente): budget esaurito -> blocked + richiesta di estensione;
    # Approva -> budget +add e si prosegue; Nega -> fallimento per decisione esplicita.
    import json as _json
    from redgiant.config import Config
    from redgiant.core.orchestrator import Orchestrator
    from redgiant.core.verify import CheckResult, Verdict
    from redgiant.state.models import LlmCallRow
    scope, router, tid = env
    store = router.store
    store.upsert_subtask(tid, _spec(), actor="t")
    # budget tokens = 1, gia' sforato da una chiamata loggata
    store.log_llm_call(tid, LlmCallRow(
        role="worker", subtask_id="P1.S1", schema_name=None,
        t_start="2026-08-01T00:00:00+00:00", prompt_tokens=100, cached_tokens=0,
        gen_tokens=10, prefill_ms=1.0, gen_ms=1.0, outcome="ok"))
    cfg = Config.load("dev-fast", CONFIG_DIR)
    object.__setattr__(cfg.paths, "tasks_dir", tmp_path)  # dataclass frozen
    orch = Orchestrator(cfg, store, llm=None, router=router, assembler=None)

    st = orch.run_task(tid)
    assert st.status == "blocked"
    pend = store.pending_approvals(tid)
    assert pend and _json.loads(pend[0]["payload"])["tool"] == "extend_budget"

    # Approva: il budget cresce e il task prosegue (sottofase eseguita: mock pass)
    store.answer_approval(pend[0]["id"], "yes")
    store.set_task_status(tid, "queued", actor="user")
    monkeypatch.setattr(orch, "_execute_subtask",
                        lambda state, spec, worker, log: Verdict(
                            verdict="pass",
                            checks=[CheckResult(name="mock", ok=True, detail="")]))
    st = orch.run_task(tid)
    assert st.status == "completed"
    assert st.budget.max_total_tokens > 1  # esteso davvero


def test_workerstep_coherence_is_structural():
    # F2.5: union discriminata — il ramo incompleto (finish:null) non e' nemmeno
    # rappresentabile: la grammatica non puo' produrlo, Pydantic non lo valida.
    import pytest as _pt
    from pydantic import ValidationError
    ok = WorkerStep.model_validate({"thought": "t", "action": "tool",
                                    "tool_call": {"tool": "read_file",
                                                  "args": {"path": "a"}}})
    assert ok.root.action == "tool" and ok.root.tool_call.tool == "read_file"
    with _pt.raises(ValidationError):
        WorkerStep.model_validate({"thought": "t", "action": "finish",
                                   "tool_call": None, "finish": None})
    with _pt.raises(ValidationError):
        WorkerStep.model_validate({"thought": "t", "action": "tool"})
    # lo schema JSON espone la discriminazione (oneOf/anyOf con mapping)
    schema = WorkerStep.model_json_schema()
    assert "oneOf" in json_dumps(schema) or "anyOf" in json_dumps(schema)


def json_dumps(o):
    import json as _j
    return _j.dumps(o)
