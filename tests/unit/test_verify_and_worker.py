"""F1.5/F1.6 — validator del WorkerStep e trust boundary della verifica."""

from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.core.verify import verify_subtask
from redgiant.roles.base import RoleContext
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


def test_plan_logic_validation_and_eligibility():
    # F3.1: validazioni deterministiche della LOGICA del piano
    from redgiant.roles.planner import PlannerOutput, validate_plan_logic
    from redgiant.state.models import PhaseSpec as PS
    ok = PlannerOutput(goal="g", success_criteria=[], phases=[
        PS(id="P1", title="a", depends_on=[], completion_criteria=[]),
        PS(id="P2", title="b", depends_on=["P1"], completion_criteria=[])])
    assert validate_plan_logic(ok) == []
    dup = PlannerOutput(goal="g", success_criteria=[], phases=[
        PS(id="P1", title="a", depends_on=[], completion_criteria=[]),
        PS(id="P1", title="b", depends_on=[], completion_criteria=[])])
    assert any("duplicate" in p for p in validate_plan_logic(dup))
    cyc = PlannerOutput(goal="g", success_criteria=[], phases=[
        PS(id="P1", title="a", depends_on=["P2"], completion_criteria=[]),
        PS(id="P2", title="b", depends_on=["P1"], completion_criteria=[])])
    probs = validate_plan_logic(cyc)
    assert any("cycle" in p or "root" in p for p in probs)
    dropped = validate_plan_logic(ok, required_phase_ids=["P9"])
    assert any("dropped" in p for p in dropped)


def test_plan_normalization_repairs_dep_sentinels():
    # A/B 2026-08-02: il modello scrive depends_on ["none"] per dire "nessuna
    # dipendenza" -> riparazione deterministica; le allucinazioni vere restano.
    from redgiant.roles.planner import PlannerOutput, normalize_plan, validate_plan_logic
    from redgiant.state.models import PhaseSpec as PS
    out = PlannerOutput(goal="g", success_criteria=[], phases=[
        PS(id="P1", title="a", depends_on=["none"], completion_criteria=[]),
        PS(id="P2", title="b", depends_on=["P1", "NULL"], completion_criteria=[])])
    assert validate_plan_logic(normalize_plan(out)) == []
    assert out.phases[0].depends_on == [] and out.phases[1].depends_on == ["P1"]
    # rerun A/B: auto-dipendenza ("P1 depends on P1") = sentinello, riparata
    selfdep = PlannerOutput(goal="g", success_criteria=[], phases=[
        PS(id="P1", title="a", depends_on=["P1"], completion_criteria=[])])
    assert validate_plan_logic(normalize_plan(selfdep)) == []
    assert selfdep.phases[0].depends_on == []
    halluc = PlannerOutput(goal="g", success_criteria=[], phases=[
        PS(id="P1", title="a", depends_on=["geometry.py"], completion_criteria=[])])
    assert any("unknown phase" in p for p in validate_plan_logic(normalize_plan(halluc)))


def test_identical_repeat_counts_into_cumulative_guard(env):
    # A/B 2026-08-02: 15 chiamate identiche "riuscite" di fila esaurivano gli
    # step. La ripetizione identica consecutiva entra nel guard cumulativo.
    from types import SimpleNamespace
    from redgiant.roles.worker import Worker
    from redgiant.tools.base import ToolResult
    scope, router, tid = env
    step = WorkerStep.model_validate({"thought": "t", "action": "tool",
                                      "tool_call": {"tool": "read_file",
                                                    "args": {"path": "a.py"}}})

    class _Parts:
        volatile_context = ""

        def with_appended_context(self, s):
            return self

    class _Llm:
        def complete(self, parts, **kw):
            return SimpleNamespace(parsed=step)

    class _Asm:
        def build(self, *a, **k):
            return _Parts()

    class _Router:
        def allowed_for(self, name, domain):
            return []

        def dispatch(self, tid_, sid, tool, args):
            return ToolResult(ok=True, data={"content": "x"}, error=None)

    w = Worker(llm=_Llm(), assembler=_Asm(), router=_Router())
    ctx = RoleContext(task=router.store.load_task(tid), subtask=_spec(), volatile="")
    rep = w.run(ctx, max_steps=30)
    assert rep.status == "blocked"
    assert "identical_repeat" in rep.summary  # abortito dal guard, non da max_steps

    # rerun A/B: run_tests ESENTATO — rieseguire l'oracolo non e' degenere
    # (il guard abortiva le sottofasi di sola analisi a 8 pytest identici)
    step_tests = WorkerStep.model_validate({"thought": "t", "action": "tool",
                                            "tool_call": {"tool": "run_tests",
                                                          "args": {"cmd_id": "pytest"}}})

    class _LlmTests:
        def complete(self, parts, **kw):
            return SimpleNamespace(parsed=step_tests)

    w2 = Worker(llm=_LlmTests(), assembler=_Asm(), router=_Router())
    rep2 = w2.run(ctx, max_steps=12)
    assert rep2.summary == "step budget exhausted"  # nessun aborto anticipato


def test_design_logic_validation():
    # F3.2: D10 — sottofase senza verifica NE' output = respinta
    from redgiant.roles.phase_designer import PhaseDesign, validate_design_logic
    from redgiant.state.models import SubtaskSpec as SS
    good = PhaseDesign(phase_id="P1", subtasks=[
        SS(id="P1.S1", phase_id="P1", title="t", objective="o", inputs=[], tools=[],
           expected_outputs=["a.py"], completion_criteria=[], verification=["pytest"])])
    assert validate_design_logic(good, "P1", {"pytest"}) == []
    bad = PhaseDesign(phase_id="P1", subtasks=[
        SS(id="P1.S1", phase_id="P1", title="t", objective="o", inputs=[], tools=[],
           expected_outputs=[], completion_criteria=[], verification=[])])
    assert any("nothing mechanical" in p for p in validate_design_logic(bad, "P1", set()))
    wrong_cmd = PhaseDesign(phase_id="P1", subtasks=[
        SS(id="P1.S1", phase_id="P1", title="t", objective="o", inputs=[], tools=[],
           expected_outputs=[], completion_criteria=[], verification=["ghost"])])
    assert any("not a known" in p for p in validate_design_logic(wrong_cmd, "P1", {"pytest"}))
    assert any("phase_id" in p for p in validate_design_logic(good, "P2", {"pytest"}))
    # REVISIONE F3.2: suite di test solo sull'ULTIMA sottofase (perimetro=verifica)
    multi = PhaseDesign(phase_id="P1", subtasks=[
        SS(id="P1.S1", phase_id="P1", title="prep", objective="o", inputs=[], tools=[],
           expected_outputs=["a.py"], completion_criteria=[], verification=["pytest"]),
        SS(id="P1.S2", phase_id="P1", title="final", objective="o", inputs=[], tools=[],
           expected_outputs=[], completion_criteria=[], verification=["pytest"])])
    assert any("ONLY on the LAST" in p for p in validate_design_logic(multi, "P1", {"pytest"}))
    multi_ok = PhaseDesign(phase_id="P1", subtasks=[
        SS(id="P1.S1", phase_id="P1", title="prep", objective="o", inputs=[], tools=[],
           expected_outputs=["a.py"], completion_criteria=[], verification=[]),
        SS(id="P1.S2", phase_id="P1", title="final", objective="o", inputs=[], tools=[],
           expected_outputs=[], completion_criteria=[], verification=["pytest"])])
    assert validate_design_logic(multi_ok, "P1", {"pytest"}) == []


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
    from redgiant.state.models import Plan, PhaseSpec
    store.save_plan(tid, Plan(version=0, goal="g", success_criteria=[],
                              phases=[PhaseSpec(id="P1", title="t", depends_on=[],
                                                completion_criteria=[])]),
                    actor="system", reason="static (test)")
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


def test_planner_gate_naive_plan_and_no_replan(env, tmp_path):
    # Verdetto D11 (A/B 2026-08-02): planner OFF di default -> piano ingenuo
    # deterministico (zero LLM) e replanning rifiutato (fallimento esplicito).
    from redgiant.config import Config
    from redgiant.core.orchestrator import Orchestrator, TaskLog
    scope, router, tid = env
    cfg = Config.load("dev-fast", CONFIG_DIR)
    assert cfg.planner_enabled is False  # il default DEVE essere spento
    object.__setattr__(cfg.paths, "tasks_dir", tmp_path)
    orch = Orchestrator(cfg, router.store, llm=None, router=router, assembler=None)
    log = TaskLog(tmp_path, tid)
    orch._naive_plan(tid, log)
    state = router.store.load_task(tid)
    assert state.plan is not None
    assert [p.id for p in state.plan.phases] == ["P1"]
    spec, status, _ = router.store.get_subtask(tid, "P1.S1")
    assert status == "pending" and spec.objective == state.request
    assert orch._replan(tid, "whatever", log) is False


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
