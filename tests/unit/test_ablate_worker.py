"""Leva di ablazione del percorso Worker (regola della triade 2026-08-03)."""

from pathlib import Path

from redgiant.config import Config
from redgiant.core.ablate import active_ablations, worker_ablated
from redgiant.tools.base import Scope
from redgiant.tools.router import default_catalog

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_lever_off_by_default(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    assert active_ablations() == []
    assert not worker_ablated("search") and not worker_ablated("verify")


def test_search_ablation_removes_the_tool(tmp_path, monkeypatch):
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.py"])
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    assert "search_code" in default_catalog(cfg, scope, {})
    monkeypatch.setenv("RG_WORKER_ABLATE", "search")
    cat = default_catalog(cfg, scope, {})
    assert "search_code" not in cat
    # gli altri tool restano: si ablate UN componente per volta
    assert {"read_file", "list_files", "write_file"} <= set(cat)
    assert active_ablations() == ["search"]


def test_multiple_ablations_parse(monkeypatch):
    monkeypatch.setenv("RG_WORKER_ABLATE", "search,verify,retry")
    assert all(worker_ablated(c) for c in ("search", "verify", "retry"))
    assert active_ablations() == ["search", "verify", "retry"]
