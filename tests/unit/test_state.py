"""F1.1 — test dello stato: roundtrip, attempts, aggregati, errori espliciti."""

import pytest

from redgiant.state.models import (Budget, LlmCallRow, Plan, PhaseSpec, SubtaskSpec,
                                   ToolCallRow)
from redgiant.state.store import StateStore


@pytest.fixture()
def store(tmp_path):
    return StateStore(tmp_path / "test.db")


@pytest.fixture()
def budget():
    return Budget(max_total_tokens=1000, max_tool_calls=10,
                  max_retries_per_subtask=2, max_wall_s=60)


def _spec(sid="P1.S1"):
    return SubtaskSpec(id=sid, phase_id="P1", title="fix", objective="fix the bug",
                       inputs=["a.py"], tools=["read_file"], expected_outputs=["a.py"],
                       completion_criteria=["tests pass"], verification=["pytest"])


def test_roundtrip(store, budget):
    tid = store.create_task("fix it", "/tmp/x", "severino-sim", budget)
    plan = Plan(version=1, goal="g", success_criteria=["ok"],
                phases=[PhaseSpec(id="P1", title="t", depends_on=[],
                                  completion_criteria=["done"])])
    store.save_plan(tid, plan, actor="planner", reason="initial")
    store.upsert_subtask(tid, _spec(), actor="phase_designer")

    st = store.load_task(tid)
    assert st.id == tid and st.status == "queued"
    assert st.plan == plan
    assert st.current_subtask == "P1.S1" and st.current_phase == "P1"
    assert st.budget == budget


def test_unknown_task_raises(store):
    with pytest.raises(KeyError):
        store.load_task("NOPE")


def test_attempts_increment_on_retry_and_repair(store, budget):
    tid = store.create_task("r", "/tmp/x", "p", budget)
    store.upsert_subtask(tid, _spec(), actor="t")
    store.set_subtask_status(tid, "P1.S1", "retry", actor="orch")
    store.set_subtask_status(tid, "P1.S1", "repair", actor="orch")
    store.set_subtask_status(tid, "P1.S1", "completed", actor="orch", result={"ok": True})
    _, status, attempts = store.get_subtask(tid, "P1.S1")
    assert status == "completed" and attempts == 2


def test_upsert_is_idempotent(store, budget):
    tid = store.create_task("r", "/tmp/x", "p", budget)
    store.upsert_subtask(tid, _spec(), actor="t")
    store.set_subtask_status(tid, "P1.S1", "running", actor="orch")
    store.upsert_subtask(tid, _spec(), actor="t")  # ri-upsert: aggiorna spec, non lo stato
    _, status, _ = store.get_subtask(tid, "P1.S1")
    assert status == "running"
    assert len(store.list_subtasks(tid)) == 1


def test_budget_used_aggregates_from_db(store, budget):
    tid = store.create_task("r", "/tmp/x", "p", budget)
    for _ in range(2):
        store.log_llm_call(tid, LlmCallRow(
            role="worker", subtask_id="P1.S1", schema_name="WorkerStep",
            t_start="2026-08-01T00:00:00+00:00", prompt_tokens=100, cached_tokens=90,
            gen_tokens=50, prefill_ms=10.0, gen_ms=20.0, outcome="ok"))
    store.log_tool_call(tid, ToolCallRow(
        subtask_id="P1.S1", tool="read_file", args={"path": "a.py"}, ok=True,
        evidence=["read a.py:1-10"], duration_ms=5.0))
    used = store.budget_used(tid)
    # il budget misura il LAVORO: (prompt - cached) + gen = (100-90+50) * 2
    assert used.tokens == 120 and used.tool_calls == 1


def test_plan_versioning_monotonic(store, budget):
    tid = store.create_task("r", "/tmp/x", "p", budget)
    p = Plan(version=1, goal="g", success_criteria=[], phases=[])
    store.save_plan(tid, p, actor="planner", reason="initial")
    store.save_plan(tid, p, actor="planner", reason="replan")  # stessa version chiesta
    st = store.load_task(tid)
    assert st.plan.version == 2  # lo store la rende monotona
