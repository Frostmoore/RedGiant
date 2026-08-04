"""F5.2 — la contabilita' del riuso, e il bug che nascondeva.

`res["tokens_cached"]` di llama-server NON e' il riuso: e' quanti token stanno
nella cache dopo la chiamata, cioe' prompt+1 sempre. Misurato sul server:

    scenario     prompt reale   tokens_cached   timings.prompt_n
    freddo           721            722              721
    identico         721            722                1
    append           724            725                4

Il numero vero e' `timings.prompt_n`. Il bug faceva valere SEMPRE 0 la
sottrazione `MAX(prompt - cached, 0)` di `budget_used`: il budget dei task ha
contato solo la generazione, mai il prefill.
"""

import sqlite3

import pytest

from redgiant.core.cache_probe import reuse_by_step, reuse_stats
from redgiant.state.models import Budget, LlmCallRow
from redgiant.state.store import StateStore


def _store(tmp_path):
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("r", str(tmp_path), "test", Budget(
        max_total_tokens=100000, max_tool_calls=10,
        max_retries_per_subtask=1, max_wall_s=60))
    return store, tid


def _call(prompt: int, reprocessed: int, *, gen: int = 10, role: str = "worker",
          sub: str = "P1.S1") -> LlmCallRow:
    """Come lo scrive il client dopo il fix: cached = riuso REALE."""
    return LlmCallRow(
        role=role, subtask_id=sub, schema_name=None,
        t_start="2026-08-04T00:00:00+00:00", prompt_tokens=prompt,
        cached_tokens=max(prompt - reprocessed, 0), gen_tokens=gen,
        prefill_ms=1.0, gen_ms=1.0, outcome="ok")


def test_reuse_ratio_is_a_ratio(tmp_path):
    """Il sintomo del bug era un riuso del 102%: un rapporto sopra 1 significa
    che il numeratore non e' cio' che si crede."""
    store, tid = _store(tmp_path)
    store.log_llm_call(tid, _call(1000, 1000))   # freddo: nessun riuso
    store.log_llm_call(tid, _call(1000, 10))     # caldo: 99% riusato
    (s,) = [x for x in reuse_stats(tmp_path / "t.db") if x.role == "worker"]
    assert 0.0 <= s.avg_reuse_ratio <= 1.0
    assert s.avg_reuse_ratio == pytest.approx(0.495, abs=0.01)
    assert s.reprocessed_tokens == 1010          # 1000 freddi + 10 caldi


def test_the_budget_now_counts_the_prefill(tmp_path):
    """Col bug, MAX(prompt-cached,0) era sempre 0 e il prefill spariva dal
    budget. Con la correzione il primo prompt si paga per intero."""
    store, tid = _store(tmp_path)
    store.log_llm_call(tid, _call(2000, 2000, gen=50))   # freddo
    store.log_llm_call(tid, _call(2100, 100, gen=50))    # append
    used = store.budget_used(tid)
    # 2000 riprocessati + 100 riprocessati + 100 generati
    assert used.tokens == 2200


def test_append_only_shows_growing_reuse(tmp_path):
    """La firma di D20: allo step 1 il prefisso e' freddo, poi il riuso sale.
    Una curva piatta sarebbe un difetto da cercare (F5.3), non un dato."""
    store, tid = _store(tmp_path)
    for prompt, repro in ((1000, 1000), (1100, 100), (1200, 100), (1300, 90)):
        store.log_llm_call(tid, _call(prompt, repro))
    curve = reuse_by_step(tmp_path / "t.db", [tid])
    ratios = [r for _, r, _ in curve]
    assert ratios[0] == 0.0                      # step 1: tutto freddo
    assert all(r > 0.8 for r in ratios[1:])      # poi quasi tutto riusato
    assert ratios[1] < ratios[2] < ratios[3]     # e cresce


def test_stats_are_per_role(tmp_path):
    store, tid = _store(tmp_path)
    store.log_llm_call(tid, _call(1000, 500, role="worker"))
    store.log_llm_call(tid, _call(800, 800, role="senior_planner"))
    stats = {s.role: s for s in reuse_stats(tmp_path / "t.db")}
    assert set(stats) == {"worker", "senior_planner"}
    assert stats["worker"].avg_reuse_ratio == pytest.approx(0.5)
    assert stats["senior_planner"].avg_reuse_ratio == 0.0
