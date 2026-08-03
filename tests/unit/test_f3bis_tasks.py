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


def test_ladder_judges_are_satisfiable_and_scale():
    """LADDER: ogni gradino ha un giudice soddisfacibile (ricavo le attese
    dal judge stesso: il generatore le cabla) e la scala e' MONOTONA in
    ampiezza — se questa proprieta' si rompe, il confronto nudo/agentico
    non misura piu' l'ampiezza."""
    import ast
    import shutil
    import subprocess
    import sys
    import tempfile

    from redgiant.eval.harness import discover_tasks
    tasks = sorted((t for t in discover_tasks(TASKS)
                    if "ladder" in t.tags), key=lambda t: t.id)
    assert len(tasks) >= 5, "ladder non generata (bench/ladder/generate.py)"
    sizes = []
    for t in tasks:
        judge_src = (t.repo_dir / "judge.py").read_text(encoding="utf-8")
        expected = ast.literal_eval(
            judge_src.split("EXPECTED = ", 1)[1].split("\n", 1)[0])
        tmp = Path(tempfile.mkdtemp(prefix=f"ladder_{t.id}_"))
        shutil.copytree(t.repo_dir, tmp, dirs_exist_ok=True)
        (tmp / "answer.txt").write_text(
            "".join(f"{k}={v}\n" for k, v in expected.items()),
            encoding="utf-8")
        proc = subprocess.run([sys.executable, "judge.py"], cwd=tmp,
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"{t.id}: {proc.stdout}{proc.stderr}"
        sizes.append(sum(len(p.read_text(encoding="utf-8").split())
                         for p in (t.repo_dir / "docs").glob("*.md")))
    # monotona a meno del 5% (L5 ha la stessa ampiezza di L4 per costruzione:
    # e' la variante col calcolo, non un gradino di ampiezza) e almeno 4x
    # dal primo all'ultimo, con l'ultimo che SFONDA il contesto da 8192
    for a, b in zip(sizes, sizes[1:]):
        assert b >= a * 0.95, sizes
    assert sizes[-1] > 4 * sizes[0], sizes
    assert sizes[-1] * 1.35 > 8192, "l'ultimo gradino deve eccedere il ctx"


def test_search_is_smart_case_and_actionable(tmp_path):
    """Diagnosi ladder L7: il modello cercava 'service mensa' mentre la riga
    era 'Service **mensa**' → 0 risultati, e la ricerca non diceva NULLA di
    utile: query ripetuta 5 volte identica. Due difetti, due fix."""
    from redgiant.tools.base import Scope
    from redgiant.tools.search import search_python
    (tmp_path / "d.md").write_text("Service Mensa: the listen_port is 210.\n",
                                   encoding="utf-8")
    scope = Scope(tmp_path, ["*.md"])
    # smart-case: pattern tutto minuscolo trova comunque
    assert len(search_python(scope, "service mensa").data["matches"]) == 1
    # pattern con maiuscole = ricerca esatta (non si perde il controllo fine)
    assert search_python(scope, "SERVICE MENSA").data["matches"] == []
    # zero risultati => hint ATTUABILE, non silenzio
    r = search_python(scope, "totally absent words here")
    assert r.ok and "hint" in r.data and "ONE distinctive word" in r.data["hint"]


def test_ladder_corpus_is_uniform(tmp_path):
    """Il fatto bersaglio dev'essere INDISTINGUIBILE dai distrattori: l'unica
    difficolta' della ladder e' l'ampiezza, mai la tipografia."""
    for tid in ("T055_ladder_l5", "T057_ladder_l7"):
        docs = sorted((TASKS / tid / "repo" / "docs").glob("*.md"))
        assert docs
        for p in docs:
            assert "**" not in p.read_text(encoding="utf-8"), f"{tid}/{p.name}"


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
