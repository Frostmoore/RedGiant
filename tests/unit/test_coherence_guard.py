"""Guardia di coerenza aritmetica in scrittura (F4 sui contenuti).

Contesto: data.md §7.5 — tre livelli di persuasione testuale non hanno reso
affidabile l'uso della calcolatrice (16% -> 40% di invocazione, L5 fermo a
2/5). Qui l'operazione e' tolta dalle mani del modello: un artefatto con un
totale incoerente NON arriva al disco. I test coprono le due meta' del
contratto: blocca cio' che deve, e — piu' importante — NON blocca tutto il
resto (un falso positivo qui rompe lavoro legittimo).
"""

from pathlib import Path

import pytest

from redgiant.tools.base import Scope
from redgiant.tools.coherence import arithmetic_check
from redgiant.tools.fs import write_file

L5_FACTS = ("mensa_listen_port=693\nvela_retention_days=228\n"
            "orion_worker_count=196\nhydra_max_connections=428\n"
            "pyxis_cache_size_mb=247\n")


def test_blocks_the_real_l5_failure():
    """Il caso vero: 5 fatti giusti, somma sbagliata di 100 (riporto perso)."""
    err = arithmetic_check(Path("answer.txt"), L5_FACTS + "total=1892\n")
    assert err is not None
    assert "1792" in err and "total=1892 is WRONG" in err
    assert arithmetic_check(Path("answer.txt"), L5_FACTS + "total=1792\n") is None


def test_accepts_variants_of_shape_and_wording():
    for total_line in ("total = 1792", "Total: 1792", "somma=1792", "- sum = 1792"):
        assert arithmetic_check(Path("a.md"), L5_FACTS + total_line + "\n") is None
    assert arithmetic_check(Path("a.txt"), "a=1.5\nb=2.25\ntotal=3.75\n") is None
    assert arithmetic_check(Path("a.txt"), "a=1.5\nb=2.25\ntotal=3.8\n") is not None


@pytest.mark.parametrize("content,why", [
    ("a=1\nb=2\n", "nessun totale dichiarato"),
    ("a=1\ntotal=5\n", "un solo addendo: non e' una somma"),
    ("a=1\ntotal=5\nb=2\n", "totale non in fondo: e' un dato, non un derivato"),
    ("a=1\nb=2\ntotal=3\ntotal=99\n", "due totali: la somma 'di tutto' non e' definita"),
    ("port=8080\ntimeout=30\ntotal=100 requests\n", "unita' di misura: non e' un'assegnazione atomica"),
    ("| a | 1 |\n| b | 2 |\n| total | 9 |\n", "tabella markdown: non e' key=value"),
])
def test_does_not_fire_when_it_cannot_be_sure(content, why):
    assert arithmetic_check(Path("a.txt"), content) is None, why


def test_never_touches_code_or_config():
    """Un 'total = 100' in un config e' un valore indipendente, non una somma:
    rifiutare la scrittura sarebbe un falso positivo grave."""
    bad = "a = 1\nb = 2\ntotal = 999\n"
    for name in ("s.py", "s.json", "s.toml", "s.ini", "s.php", "s.yaml"):
        assert arithmetic_check(Path(name), bad) is None


def test_write_file_refuses_and_the_message_is_actionable(tmp_path, monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    scope = Scope(tmp_path, ["answer.txt"])
    r = write_file(scope, "answer.txt", L5_FACTS + "total=1892\n")
    assert not r.ok and r.error == "incoherent_arithmetic"
    assert "1792" in r.data["hint"] and "NOT written" in r.data["hint"]
    assert not (tmp_path / "answer.txt").exists()   # il file NON esiste: F4
    # ...e il messaggio lo DICE: 2 run su 4 morivano qui, una chiamando
    # edit_file su un file mai creato (data.md §7.6)
    assert "does NOT exist" in r.data["hint"]
    assert "edit_file cannot work" in r.data["hint"]
    # il messaggio contiene il numero da scrivere -> il giro dopo passa
    assert write_file(scope, "answer.txt", L5_FACTS + "total=1792\n").ok
    assert "total=1792" in (tmp_path / "answer.txt").read_text(encoding="utf-8")


def test_refusal_on_an_existing_file_says_it_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    scope = Scope(tmp_path, ["answer.txt"])
    assert write_file(scope, "answer.txt", "a=1\nb=2\ntotal=3\n").ok
    r = write_file(scope, "answer.txt", "a=1\nb=2\ntotal=9\n")
    assert not r.ok and "still has its PREVIOUS content" in r.data["hint"]
    assert (tmp_path / "answer.txt").read_text(encoding="utf-8").endswith("total=3\n")


def test_guard_is_ablatable(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_WORKER_ABLATE", "coherence")
    scope = Scope(tmp_path, ["answer.txt"])
    assert write_file(scope, "answer.txt", L5_FACTS + "total=1892\n").ok
    assert "total=1892" in (tmp_path / "answer.txt").read_text(encoding="utf-8")


def test_guard_does_not_reveal_the_task_answer(tmp_path):
    """Il totale calcolato viene dai valori che il MODELLO ha scritto: se i
    fatti sono sbagliati, la guardia certifica una somma sbagliata. Non e' un
    oracolo sul task (che sarebbe un leak come quello del giudice, data.md
    §7.5), e' solo coerenza interna."""
    wrong_facts = "a_x=1\nb_y=2\nc_z=3\n"
    assert arithmetic_check(Path("answer.txt"), wrong_facts + "total=6\n") is None
