"""F5.0 — la composizione del prompt si rileva SEMPRE, non solo in overflow.

Motivazione (data.md §7.7.2): LAD.8 ha mostrato CHE la finestra di contesto si
riempie — L7 muore con `prompt of 9323 tokens exceeds budget` usando 8,5 passi
su 60 — ma non DI COSA. Il calcolo per sezione esisteva gia' nel client e
finiva solo dentro il messaggio d'errore. Senza questa tabella, scegliere quale
leva di F5 costruire sarebbe tirare a indovinare.
"""

import json
import sqlite3

from redgiant.state.models import Budget, LlmCallRow
from redgiant.state.store import StateStore


def _store(tmp_path) -> tuple[StateStore, str]:
    store = StateStore(tmp_path / "t.db")
    tid = store.create_task("r", str(tmp_path), "test", Budget(
        max_total_tokens=100, max_tool_calls=10,
        max_retries_per_subtask=1, max_wall_s=60))
    return store, tid


def _row(**kw) -> LlmCallRow:
    base = dict(role="worker", subtask_id="P1.S1", schema_name="WorkerStep",
                t_start="2026-08-04T00:00:00+00:00", prompt_tokens=1000,
                cached_tokens=0, gen_tokens=10, prefill_ms=1.0, gen_ms=1.0,
                outcome="ok")
    base.update(kw)
    return LlmCallRow(**base)


def test_sections_are_persisted_and_readable(tmp_path):
    store, tid = _store(tmp_path)
    sections = {"PREAMBLE": 314, "ROLE": 1521, "TOOLS": 402,
                "DURABLE": 88, "VOLATILE": 5900, "OUTPUT": 40}
    store.log_llm_call(tid, _row(sections=sections))

    con = sqlite3.connect(tmp_path / "t.db")
    raw = con.execute("SELECT sections FROM llm_calls").fetchone()[0]
    assert json.loads(raw) == sections
    # la sezione volatile e' quella che cresce: e' il dato che serve a F5
    assert json.loads(raw)["VOLATILE"] == 5900


def test_sections_are_optional(tmp_path):
    """Le chiamate storiche (e le sonde che non passano da PromptParts) non
    hanno la rilevazione: NULL, non zero — zero sarebbe una misura falsa."""
    store, tid = _store(tmp_path)
    store.log_llm_call(tid, _row())
    con = sqlite3.connect(tmp_path / "t.db")
    assert con.execute("SELECT sections FROM llm_calls").fetchone()[0] is None


def test_migration_is_idempotent_on_a_pre_existing_db(tmp_path):
    """Stessa garanzia della migrazione thinking_tokens: un DB creato prima
    della colonna si apre, si migra e resta usabile."""
    db = tmp_path / "old.db"
    StateStore(db)                       # crea lo schema corrente
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE llm_calls DROP COLUMN sections")   # simula il vecchio
    con.commit()
    con.close()

    store = StateStore(db)               # deve rimettere la colonna, senza errori
    StateStore(db)                       # e una seconda apertura non deve rompere
    tid = store.create_task("r", str(tmp_path), "test", Budget(
        max_total_tokens=100, max_tool_calls=10,
        max_retries_per_subtask=1, max_wall_s=60))
    store.log_llm_call(tid, _row(sections={"ROLE": 7}))
    con = sqlite3.connect(db)
    assert json.loads(
        con.execute("SELECT sections FROM llm_calls").fetchone()[0]) == {"ROLE": 7}


def test_the_client_measures_every_section_of_the_prompt():
    """Il contratto a monte: PromptParts sa scomporsi, e le sezioni coprono
    l'intero prompt renderizzato (nessun pezzo sfugge al conteggio)."""
    from redgiant.prompts.assemble import PromptParts
    parts = PromptParts(preamble="a" * 10, role_card="b" * 20, tool_card="c" * 30,
                        task_header="d" * 40, durable_state="e" * 50,
                        volatile_context="f" * 60, output_instruction="g" * 70)
    sec = parts.section_tokens(len)          # conteggio in caratteri: deterministico
    assert set(sec.values()) == {10, 20, 30, 40, 50, 60, 70}
    # la somma delle sezioni sta dentro il prompt reso (il resto sono i marcatori)
    assert sum(sec.values()) <= len(parts.render())
