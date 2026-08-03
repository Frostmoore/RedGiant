"""Calcolatrice deterministica (ladder L5: 5 fatti giusti, somma sbagliata)."""

from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.tools.base import Scope
from redgiant.tools.calc import calc
from redgiant.tools.router import default_catalog

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_arithmetic_is_exact():
    # il caso reale della ladder: 5 addendi, il modello aveva detto 1892
    r = calc("693+228+196+428+247")
    assert r.ok and r.data["result"] == 1792
    assert calc("(2+3)*4").data["result"] == 20
    assert calc("7/2").data["result"] == 3.5
    assert calc("-5 + 10").data["result"] == 5


def test_not_an_eval_in_disguise():
    for bad in ("__import__('os').system('x')", "open('f')", "a+1",
                "[1,2][0]", "lambda: 1"):
        r = calc(bad)
        assert not r.ok and "bad_expression" in r.error
    assert not calc("2**99999").ok          # niente bombe di calcolo
    assert not calc("1/0").ok               # divisione per zero come dato


def test_calc_is_in_catalog_and_ablatable(tmp_path, monkeypatch):
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.txt"])
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    assert "calc" in default_catalog(cfg, scope, {})
    monkeypatch.setenv("RG_WORKER_ABLATE", "calc")
    assert "calc" not in default_catalog(cfg, scope, {})


def test_unknown_tool_error_is_actionable(tmp_path):
    """Ladder: 13 task su 43 sprecavano passi chiamando 'tool_name_placeholder'
    e simili. L'errore deve suggerire il nome vicino (F2)."""
    from redgiant.state.store import StateStore
    from redgiant.tools.router import ToolRouter
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.txt"])
    store = StateStore(tmp_path / "t.db")
    router = ToolRouter(default_catalog(cfg, scope, {}), scope, store)
    tid = store.create_task("r", str(tmp_path), "test", __import__(
        "redgiant.state.models", fromlist=["Budget"]).Budget(
        max_total_tokens=100, max_tool_calls=10,
        max_retries_per_subtask=1, max_wall_s=60))
    r = router.dispatch(tid, "s1", "read_fil", {"path": "x"})
    assert not r.ok and "did you mean 'read_file'" in r.data["hint"]
    r2 = router.dispatch(tid, "s1", "tool_name_placeholder", {})
    assert not r2.ok and "placeholder" in r2.data["hint"]


def test_ladder_step_budget_scales_with_size():
    from redgiant.eval.harness import discover_tasks
    tasks = {t.id: t for t in discover_tasks(
        Path(__file__).resolve().parents[2] / "redgiant" / "eval" / "tasks")}
    # L7 (400 doc, 8 fatti) deve avere piu' passi di L5 (90 doc, 5 fatti)
    assert tasks["T057"].worker_max_steps > tasks["T055"].worker_max_steps
    assert tasks["T051"].worker_max_steps >= 20
