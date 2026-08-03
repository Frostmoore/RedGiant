"""TH0 (plan_thinking_ab.md) — il two-call protocol del canale di pensiero.

Accettazione TH0.4: (1) think=None = payload identico a oggi; (2) two-call con
stop e budget; (3) pensiero troncato non e' errore; (4) canale nel prompt della
chiamata 2; (5) migrazione DB idempotente + budget che conta i thinking token;
(6) TH-D2: le parts del chiamante restano intatte.
"""

from pathlib import Path

import pytest

from redgiant.config import LlmProfileCfg
from redgiant.llm.client import LlamaClient, LlmError
from redgiant.prompts.assemble import PromptParts
from redgiant.state.models import LlmCallRow
from redgiant.state.store import StateStore

CFG = LlmProfileCfg(base_url="http://127.0.0.1:1", ctx_size=8192, timeout_s=5,
                    temperature=0.2, max_tokens_default=256, idle_shutdown_s=1,
                    think_open="<|channel>thought\n", think_close="<channel|>")

PARTS = PromptParts(preamble="P", role_card="R", tool_card="T", task_header="H",
                    durable_state="S", volatile_context="V",
                    output_instruction="O")


def _client(monkeypatch, responses: list[dict],
            captured: list[dict]) -> LlamaClient:
    c = LlamaClient(CFG, store=None)
    monkeypatch.setattr(c, "count_tokens", lambda text: len(text) // 4)

    def fake_post(path, payload):
        captured.append(payload)
        return responses[len(captured) - 1]

    monkeypatch.setattr(c, "_post_with_transport_retry", fake_post)
    return c


def _resp(content: str, n: int = 10, **extra) -> dict:
    return {"content": content, "tokens_cached": 0,
            "timings": {"predicted_n": n, "predicted_ms": 5.0,
                        "prompt_ms": 1.0}, **extra}


def test_no_think_payload_identical(monkeypatch):
    captured: list[dict] = []
    c = _client(monkeypatch, [_resp("out")], captured)
    c.complete(PARTS, role="worker", max_tokens=100)
    assert len(captured) == 1
    p = captured[0]
    assert p["prompt"] == PARTS.render()
    assert "stop" not in p and p["n_predict"] == 100 and p["seed"] == 42


def test_two_call_protocol(monkeypatch):
    captured: list[dict] = []
    c = _client(monkeypatch, [_resp("ragiono..."), _resp("out")], captured)
    r = c.complete(PARTS, role="worker", max_tokens=100, think=64)
    assert len(captured) == 2
    p1, p2 = captured
    assert p1["prompt"].endswith(CFG.think_open)
    assert p1["stop"] == [CFG.think_close]
    assert p1["n_predict"] == 64 and "json_schema" not in p1
    assert (CFG.think_open + "ragiono..." + CFG.think_close) in p2["prompt"]
    assert p2["n_predict"] == 100
    assert r.thinking_tokens == 10 and r.thinking_text == "ragiono..."


def test_think_truncation_is_not_error(monkeypatch):
    captured: list[dict] = []
    c = _client(monkeypatch,
                [_resp("pensiero tronca", stop_type="limit"), _resp("out")],
                captured)
    r = c.complete(PARTS, role="worker", max_tokens=100, think=8)
    assert r.text == "out" and r.thinking_text == "pensiero tronca"


def test_markers_required(monkeypatch):
    from dataclasses import replace
    captured: list[dict] = []
    c = _client(monkeypatch, [_resp("x")], captured)
    c.cfg = replace(CFG, think_open="", think_close="")
    with pytest.raises(LlmError):
        c.complete(PARTS, role="worker", max_tokens=100, think=64)


def test_parts_untouched_th_d2(monkeypatch):
    before = PARTS.render()
    captured: list[dict] = []
    c = _client(monkeypatch, [_resp("pensiero"), _resp("out")], captured)
    c.complete(PARTS, role="worker", max_tokens=100, think=64)
    assert PARTS.render() == before          # il chiamante non vede il canale
    assert CFG.think_open not in before


def test_db_migration_and_budget(tmp_path: Path):
    store = StateStore(tmp_path / "t.db")
    store.init_schema()                       # idempotente (migrazione TH0.2)
    from redgiant.state.models import Budget
    tid = store.create_task("req", str(tmp_path), "test",
                            Budget(max_total_tokens=1000, max_tool_calls=10,
                                   max_retries_per_subtask=1, max_wall_s=60))
    store.log_llm_call(tid, LlmCallRow(
        role="senior_planner", subtask_id=None, schema_name=None,
        t_start="2026-08-03T00:00:00", prompt_tokens=100, cached_tokens=90,
        gen_tokens=20, prefill_ms=1.0, gen_ms=2.0, outcome="ok",
        thinking_tokens=64, thinking_ms=7.0))
    used = store.budget_used(tid)
    assert used.tokens == (100 - 90) + 20 + 64   # il pensiero conta UNA volta


def test_think_clamped_to_context_room(monkeypatch):
    # decisione utente: fusibile, non bersaglio — ma la risposta ha SEMPRE
    # il suo spazio: think si clampa a ctx - prompt - max_tokens - 64
    from dataclasses import replace
    captured: list[dict] = []
    c = _client(monkeypatch, [_resp("t"), _resp("out")], captured)
    c.cfg = replace(CFG, ctx_size=200)
    c.complete(PARTS, role="worker", max_tokens=100, think=99999)
    room = 200 - (len(PARTS.render()) // 4) - 100 - 64
    assert captured[0]["n_predict"] == room > 0


def test_thinking_roles_lever(monkeypatch):
    from redgiant.plansys import thinking_budget, thinking_roles
    monkeypatch.delenv("RG_THINKING_ROLES", raising=False)
    assert thinking_roles() == set()
    monkeypatch.setenv("RG_THINKING_ROLES", "senior_planner, worker")
    monkeypatch.setenv("RG_THINKING_BUDGET", "128")
    assert thinking_roles() == {"senior_planner", "worker"}
    assert thinking_budget() == 128
    monkeypatch.delenv("RG_THINKING_BUDGET")
    assert thinking_budget() == 1536          # fusibile, non bersaglio
