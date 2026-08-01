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
    # la grant matcha tool+path ed e' PERMANENTE per il task (non un gettone):
    # il modello deve poter iterare sul file concesso
    ans = store.consume_matching_approval(tid, "write_file",
                                          json.dumps({"path": "x"}, sort_keys=True))
    assert ans == "yes"
    ans = store.consume_matching_approval(
        tid, "write_file",
        json.dumps({"path": "x", "content": "altro edit"}, sort_keys=True))
    assert ans == "yes"  # stessa path, edit diverso: ancora concesso
    # famiglia di scrittura: la grant su write_file vale anche per edit_file
    ans = store.consume_matching_approval(
        tid, "edit_file", json.dumps({"path": "x", "old_string": "a",
                                      "new_string": "b"}, sort_keys=True))
    assert ans == "yes"
    assert store.consume_matching_approval(
        tid, "write_file", json.dumps({"path": "ALTRO_FILE"}, sort_keys=True)) is None


def test_relaunch_clones_task_with_guidance(client):
    c, app, tmp = client
    store = app.state.store
    (tmp / "tgt").mkdir()
    r = c.post("/tasks", data={"prompt": "fix it", "target_dir": str(tmp / "tgt"),
                               "writable": "*.py", "test_commands": "pytest=pytest -q"},
               follow_redirects=False)
    tid = r.headers["location"].rsplit("/", 1)[-1]
    r = c.post(f"/tasks/{tid}/relaunch", data={"guidance": "use pytest -q"},
               follow_redirects=False)
    assert r.status_code == 303
    new_id = r.headers["location"].rsplit("/", 1)[-1]
    assert new_id != tid
    st = store.load_task(new_id)
    assert "[USER GUIDANCE] use pytest -q" in st.request
    assert st.request.count("[USER GUIDANCE]") == 1
    # rilancio del rilancio: la guidance vecchia non si accumula
    r = c.post(f"/tasks/{new_id}/relaunch", data={"guidance": "altra guida"},
               follow_redirects=False)
    st2 = store.load_task(r.headers["location"].rsplit("/", 1)[-1])
    assert st2.request.count("[USER GUIDANCE]") == 1
    assert "altra guida" in st2.request


def test_creation_without_test_commands_is_allowed(client):
    # F2 (richiesta utente): i comandi di test li trova il sistema, non l'utente —
    # niente pre-flight bloccante.
    c, app, tmp = client
    (tmp / "tgt2").mkdir()
    plan = json.dumps({"plan": {"goal": "g", "success_criteria": [], "phases": []},
                       "subtasks": [{"id": "P1.S1", "phase_id": "P1", "title": "t",
                                     "objective": "o", "inputs": [], "tools": [],
                                     "expected_outputs": [], "completion_criteria": [],
                                     "verification": ["pytest"]}]})
    r = c.post("/tasks", data={"prompt": "x", "target_dir": str(tmp / "tgt2"),
                               "plan_json": plan}, follow_redirects=False)
    assert r.status_code == 303


def test_grant_override_and_revoke(client):
    c, app, tmp = client
    store = app.state.store
    tid = store.create_task("t", str(tmp), "dev-fast",
                            Budget(max_total_tokens=1, max_tool_calls=1,
                                   max_retries_per_subtask=1, max_wall_s=1))
    aid = store.add_approval(tid, kind="irreversible_op",
                             payload=json.dumps({"tool": "edit_file",
                                                 "args": {"path": "s.py"}}))
    store.answer_approval(aid, "no")
    key = json.dumps({"path": "s.py"}, sort_keys=True)
    assert store.consume_matching_approval(tid, "edit_file", key) == "no"
    # override no -> yes (richiesta utente)
    r = c.post(f"/approvals/{aid}/override", data={"answer": "yes"},
               follow_redirects=False)
    assert r.status_code == 303
    assert store.consume_matching_approval(tid, "edit_file", key) == "yes"
    # revoca: la grant sparisce, si richiedera'
    c.post(f"/approvals/{aid}/override", data={"answer": "revoke"})
    assert store.consume_matching_approval(tid, "edit_file", key) is None
    # una grant revocata non e' piu' attiva: override -> 409
    assert c.post(f"/approvals/{aid}/override", data={"answer": "no"}).status_code == 409


def test_metrics_page(client):
    c, _, _ = client
    assert c.get("/metrics").status_code == 200
