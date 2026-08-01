"""F2 — rotte della GUI via TestClient (nessun modello: il JobQueue gira ma i task
falliscono puliti su 'server non raggiungibile', che per questi test va benissimo)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from redgiant.config import Config
from redgiant.state.models import Budget
from redgiant.web.app import create_app

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    cfg = Config.load("dev-fast", CONFIG_DIR)
    # config isolata: db e tasks_dir nel tmp, porta non usata
    object.__setattr__(cfg.paths, "db", tmp_path / "web.db")
    object.__setattr__(cfg.paths, "tasks_dir", tmp_path / "tasks")
    app = create_app(cfg)
    return TestClient(app), app, tmp_path


def test_index_and_new_task_form(client):
    c, app, _ = client
    assert c.get("/").status_code == 200
    assert c.get("/tasks/new").status_code == 200


def test_task_create_validates_input(client):
    c, app, tmp = client
    r = c.post("/tasks", data={"prompt": "", "target_dir": str(tmp)})
    assert r.status_code == 400
    r = c.post("/tasks", data={"prompt": "x", "target_dir": str(tmp / "ghost")})
    assert r.status_code == 400


def test_task_create_and_detail_and_tree(client):
    c, app, tmp = client
    (tmp / "target").mkdir()
    r = c.post("/tasks", data={"prompt": "fix it", "target_dir": str(tmp / "target"),
                               "writable": "*.py", "test_commands": "pytest=pytest -q"},
               follow_redirects=False)
    assert r.status_code == 303
    tid = r.headers["location"].rsplit("/", 1)[-1]
    assert c.get(f"/tasks/{tid}").status_code == 200
    assert c.get(f"/tasks/{tid}/tree").status_code == 200
    assert c.get("/tasks/GHOST").status_code == 404
    # config per-task scritta su disco (la ripresa post-riavvio dipende da questo)
    tc = json.loads((app.state.cfg.paths.tasks_dir / tid / "task_config.json")
                    .read_text(encoding="utf-8"))
    assert tc["writable_globs"] == ["*.py"]
    assert tc["test_commands"]["pytest"] == ["pytest", "-q"]


def test_approval_flow_answer_and_requeue(client):
    c, app, tmp = client
    store = app.state.store
    tid = store.create_task("t", str(tmp), "dev-fast",
                            Budget(max_total_tokens=1, max_tool_calls=1,
                                   max_retries_per_subtask=1, max_wall_s=1))
    aid = store.add_approval(tid, kind="irreversible_op",
                             payload=json.dumps({"tool": "write_file",
                                                 "args": {"path": "x"},
                                                 "subtask_id": "P1.S1"}))
    store.set_task_status(tid, "blocked", actor="test")
    assert c.get("/approvals").status_code == 200
    r = c.post(f"/approvals/{aid}", data={"answer": "yes"}, follow_redirects=False)
    assert r.status_code == 303
    # doppia risposta -> 409; risposta a id ignoto -> 404
    assert c.post(f"/approvals/{aid}", data={"answer": "yes"}).status_code == 409
    assert c.post("/approvals/99999", data={"answer": "yes"}).status_code == 404
    # il consumo dell'approvazione matcha tool+args
    ans = store.consume_matching_approval(tid, "write_file",
                                          json.dumps({"path": "x"}, sort_keys=True))
    assert ans == "yes"


def test_metrics_page(client):
    c, _, _ = client
    assert c.get("/metrics").status_code == 200
