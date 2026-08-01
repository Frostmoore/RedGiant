"""F1.4 — tool layer: Scope, write_patch, run_tests, dispatch. Nessun modello coinvolto."""

from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.state.models import Budget
from redgiant.state.store import StateStore
from redgiant.tools import fs, proc
from redgiant.tools.base import Scope, ScopeError
from redgiant.tools.router import ToolRouter, default_catalog

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture()
def root(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def scope(root):
    return Scope(root, writable_globs=["src/*.py"])


# ── Scope ────────────────────────────────────────────────────────────────────

def test_scope_denies_traversal(scope):
    with pytest.raises(ScopeError):
        scope.check_read("../outside.txt")


def test_scope_write_only_in_globs(scope):
    scope.check_write("src/a.py")
    with pytest.raises(ScopeError):
        scope.check_write("secrets.env")


# ── read_file / write_patch ──────────────────────────────────────────────────

def test_read_file_truncation_declared(scope, root):
    big = "\n".join(f"line{i}" for i in range(1, 1001))
    (root / "src" / "big.py").write_text(big, encoding="utf-8")
    r = fs.read_file(scope, "src/big.py")
    assert r.ok and r.data["truncated"] and r.data["total_lines"] == 1000


def test_write_patch_applies_clean_hunk(scope, root):
    diff = ("@@ -1,2 +1,2 @@\n"
            " def f():\n"
            "-    return 1\n"
            "+    return 2\n")
    r = fs.write_patch(scope, "src/a.py", diff)
    assert r.ok and r.data["applied"] == 1
    assert "return 2" in (root / "src" / "a.py").read_text(encoding="utf-8")


def test_write_patch_rejects_bad_context(scope):
    diff = ("@@ -1,2 +1,2 @@\n"
            " def NOT_THERE():\n"
            "-    return 1\n"
            "+    return 2\n")
    r = fs.write_patch(scope, "src/a.py", diff)
    assert not r.ok and r.error == "all_hunks_rejected"
    assert r.data["rejected"][0]["expected"]


def test_write_patch_creates_new_file(scope, root):
    diff = "@@ -0,0 +1,2 @@\n+x = 1\n+y = 2\n"
    r = fs.write_patch(scope, "src/new.py", diff)
    assert r.ok
    assert (root / "src" / "new.py").read_text(encoding="utf-8") == "x = 1\ny = 2\n"


# ── run_tests ────────────────────────────────────────────────────────────────

def test_run_tests_rejects_unknown_and_unwhitelisted(scope):
    r = proc.run_tests(scope, {}, ("pytest",), "nope")
    assert not r.ok and r.error == "unknown_cmd_id"
    r = proc.run_tests(scope, {"evil": ["rm", "-rf", "/"]}, ("pytest",), "evil")
    assert not r.ok and r.error.startswith("executable_not_whitelisted")


# ── dispatch ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def router(scope, tmp_path):
    cfg = Config.load("dev-fast", CONFIG_DIR)
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("t", str(scope.root), "dev-fast",
                            Budget(max_total_tokens=1, max_tool_calls=10,
                                   max_retries_per_subtask=1, max_wall_s=10))
    return ToolRouter(default_catalog(cfg, scope, {}), scope, store), store, tid


def test_dispatch_unknown_tool_and_bad_args_are_data(router):
    r_, store, tid = router
    res = r_.dispatch(tid, "P1.S1", "teleport", {})
    assert not res.ok and res.error == "unknown_tool"
    res = r_.dispatch(tid, "P1.S1", "read_file", {"nope": 1})
    assert not res.ok and res.error == "bad_args"
    # entrambe loggate: il log e' completo per costruzione
    assert store.budget_used(tid).tool_calls == 2


def test_dispatch_executes_and_logs(router):
    r_, store, tid = router
    res = r_.dispatch(tid, "P1.S1", "read_file", {"path": "src/a.py"})
    assert res.ok and "read src/a.py" in res.evidence[0]
    assert store.budget_used(tid).tool_calls == 1
