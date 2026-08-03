"""F3b.2 — i fixture multi-dominio si auto-verificano (richiesta utente:
i controlli di taratura NON si fanno a mano, stanno nella suite):
(1) ogni giudice e' SODDISFACIBILE con l'artefatto di riferimento;
(2) il servizio locale di T031 risponde col payload atteso;
(3) l'harness parsa le chiavi nuove (whitelist per-task, service_script)."""

import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

TASKS = Path(__file__).resolve().parents[2] / "redgiant" / "eval" / "tasks"

REFS = {
    "T030_doc_analysis": {
        "answer.txt": "staging_port=8443\nproject_start=2019\n"},
    "T031_api_call": {
        "report.txt": "version=2.4.1\nuptime_days=17\n"},
    "T032_doc_transform": {
        "out.csv": "name,email,role\n"
                   "Ada Moretti,ada.moretti@example.org,engineer\n"
                   "Luca Bianchi,luca.bianchi@example.org,designer\n"
                   "Sara Conti,sara.conti@example.org,manager\n"},
}


@pytest.mark.parametrize("task_id", sorted(REFS))
def test_judge_is_satisfiable(tmp_path: Path, task_id: str):
    shutil.copytree(TASKS / task_id / "repo", tmp_path, dirs_exist_ok=True)
    for name, content in REFS[task_id].items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    proc = subprocess.run([sys.executable, "judge.py"], cwd=tmp_path,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_t031_service_serves_expected_payload():
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 8765)) == 0:
            pytest.skip("porta 8765 occupata")
    svc = subprocess.Popen(
        [sys.executable, str(TASKS / "T031_api_call" / "service.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            time.sleep(0.2)
            try:
                r = httpx.get("http://127.0.0.1:8765/status", timeout=2.0)
                break
            except httpx.HTTPError:
                continue
        else:
            pytest.fail("servizio T031 mai partito")
        data = r.json()
        assert data["version"] == "2.4.1" and data["uptime_days"] == 17
        assert httpx.get("http://127.0.0.1:8765/altro",
                         timeout=2.0).status_code == 404
    finally:
        svc.terminate()


def test_harness_parses_f3bis_keys():
    from redgiant.eval.harness import discover_tasks
    tasks = {t.id: t for t in discover_tasks(TASKS)}
    t31 = tasks["T031"]
    assert t31.http_allowed_domains == ["127.0.0.1"]
    assert t31.service_script is not None and t31.service_script.is_file()
    assert tasks["T030"].domain == "research_local"
    assert tasks["T032"].domain == "docs"
    # la whitelist http di default resta VUOTA per tutti gli altri task
    assert tasks["T001"].http_allowed_domains == []
