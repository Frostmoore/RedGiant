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


def test_calculator_is_off_by_default(tmp_path, monkeypatch):
    """VERDETTO LAD.13 (2026-08-04): fuori dal catalogo di default.
    A/B su L5, 20 run per braccio: full 16/20 contro -calc 17/20, Fisher
    p = 1.000 — la guardia di coerenza l'ha resa superflua, e la sua voce nella
    card costava token a ogni step. Riaccendibile con RG_CALCULATOR=1; verdetto
    APERTO per i domini di F7, dove la guardia non si applica."""
    from redgiant.tools.router import calculator_enabled
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.txt"])
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)

    monkeypatch.delenv("RG_CALCULATOR", raising=False)
    assert not calculator_enabled()
    assert "calculator" not in default_catalog(cfg, scope, {})

    monkeypatch.setenv("RG_CALCULATOR", "1")
    assert calculator_enabled()
    assert "calculator" in default_catalog(cfg, scope, {})

    # riaccesa MA ablata: l'ablazione storica continua a funzionare
    monkeypatch.setenv("RG_WORKER_ABLATE", "calc")
    assert "calculator" not in default_catalog(cfg, scope, {})


def test_the_tool_card_shrinks_when_the_calculator_is_off(tmp_path, monkeypatch):
    """Il beneficio concreto della rimozione: token di prompt risparmiati a
    OGNI step di OGNI task."""
    from redgiant.prompts.assemble import PromptAssembler
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.txt"])
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)

    monkeypatch.setenv("RG_CALCULATOR", "1")
    with_calc = PromptAssembler._tool_card(
        sorted(default_catalog(cfg, scope, {}).values(), key=lambda s: s.name))
    monkeypatch.delenv("RG_CALCULATOR", raising=False)
    without = PromptAssembler._tool_card(
        sorted(default_catalog(cfg, scope, {}).values(), key=lambda s: s.name))
    assert len(without) < len(with_calc)
    assert "calculator" not in without


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


def test_bad_args_error_is_actionable(tmp_path, monkeypatch):
    """LAD.10: 27 chiamate su 67 (40%) a `calculator` arrivavano con
    expression=None e il router rispondeva col dump di pydantic; il modello ci
    ciclava 5 step prima di arrendersi (data.md §7.6.5). L'errore deve NOMINARE
    il campo mancante e mostrare la forma esatta della chiamata.

    (La calcolatrice va accesa esplicitamente: dopo LAD.13 e' fuori dal
    catalogo di default. Il fix di LAD.10 vale per OGNI strumento — vedi le due
    asserzioni su read_file — ma qui si riproduce il caso storico esatto.)"""
    from redgiant.state.store import StateStore
    from redgiant.tools.router import ToolRouter
    monkeypatch.setenv("RG_CALCULATOR", "1")
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.txt"])
    store = StateStore(tmp_path / "t.db")
    router = ToolRouter(default_catalog(cfg, scope, {}), scope, store)
    tid = store.create_task("r", str(tmp_path), "test", __import__(
        "redgiant.state.models", fromlist=["Budget"]).Budget(
        max_total_tokens=100, max_tool_calls=10,
        max_retries_per_subtask=1, max_wall_s=60))

    # il caso reale: chiamata senza argomenti
    r = router.dispatch(tid, "s1", "calculator", {})
    assert not r.ok and r.error == "bad_args"
    hint = r.data["hint"]
    assert "'expression'" in hint and "missing required" in hint
    assert '"tool": "calculator"' in hint       # la forma esatta da emettere
    assert '"expression"' in hint

    # argomento sconosciuto: va nominato anche quello
    r2 = router.dispatch(tid, "s1", "read_file", {"filename": "x"})
    assert not r2.ok and "'filename'" in r2.data["hint"]
    assert "'path'" in r2.data["hint"]          # e quello giusto suggerito

    # tipo sbagliato: il messaggio resta leggibile
    r3 = router.dispatch(tid, "s1", "read_file",
                         {"path": "x", "start_line": "molte"})
    assert not r3.ok and "start_line" in r3.data["hint"]


def test_ladder_step_budget_scales_with_size():
    from redgiant.eval.harness import discover_tasks
    tasks = {t.id: t for t in discover_tasks(
        Path(__file__).resolve().parents[2] / "redgiant" / "eval" / "tasks")}
    # L7 (400 doc, 8 fatti) deve avere piu' passi di L5 (90 doc, 5 fatti)
    assert tasks["T057"].worker_max_steps > tasks["T055"].worker_max_steps
    assert tasks["T051"].worker_max_steps >= 20
