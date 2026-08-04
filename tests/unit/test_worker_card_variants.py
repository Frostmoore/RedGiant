"""F5.0-ter — la leva di A/B sulla card del Worker.

Motivazione misurata (data.md §7.12): la card costa **837 token a ogni chiamata
di ogni run** (il 10% della finestra) ed e' la piu' grande di tutte. La campagna
ladder ha dimostrato che almeno tre delle sue regole non producono obbedienza, e
una citava uno strumento che avevamo rimosso dal catalogo.

La variante `minimal` non e' un taglio a gusto: **ogni regola tolta cita il
motivo per cui e' stata tolta.** Tre categorie, e i test le presidiano tutte e
tre — perche' se domani qualcuno rimette una regola gia' imposta dalla
struttura, la card ricomincia a gonfiarsi senza che nessuno se ne accorga.
"""

import os
from pathlib import Path

import pytest

from redgiant.prompts.assemble import PromptAssembler

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "redgiant" / "prompts"


def _card(variant: str | None, monkeypatch) -> str:
    if variant is None:
        monkeypatch.delenv("RG_WORKER_CARD", raising=False)
    else:
        monkeypatch.setenv("RG_WORKER_CARD", variant)
    return PromptAssembler(PROMPTS)._cards["worker"]


def test_default_is_the_full_card(monkeypatch):
    """Si cambia coi numeri, non per fede: finche' l'A/B non parla, il default
    resta la card completa."""
    assert len(_card(None, monkeypatch)) > 3000
    assert len(_card("full", monkeypatch)) > 3000


def test_minimal_is_selected_and_is_much_smaller(monkeypatch):
    full, minimal = _card(None, monkeypatch), _card("minimal", monkeypatch)
    assert len(minimal) < len(full) * 0.6, "la variante non e' abbastanza ridotta"


def test_an_unknown_variant_fails_loudly(monkeypatch):
    """Un braccio d'esperimento che silenziosamente usa la card sbagliata
    produce una misura senza senso: meglio esplodere."""
    monkeypatch.setenv("RG_WORKER_CARD", "inesistente")
    with pytest.raises(FileNotFoundError, match="RG_WORKER_CARD"):
        PromptAssembler(PROMPTS)


def test_minimal_keeps_what_has_evidence(monkeypatch):
    """Cio' che resta, resta per un motivo misurato."""
    m = _card("minimal", monkeypatch)
    assert "edit_file" in m and "old_string" in m      # 20+ chiamate -> 5-6 (F1.11)
    assert "unknown_cmd_id" in m                       # scoperta dei comandi (F2)
    assert '"done"' in m and '"blocked"' in m          # semantica del FinishReport


@pytest.mark.parametrize("frammento,motivo", [
    ("at most 300 characters", "gia' imposto da Field(max_length=300)"),
    ("One action per step", "gia' imposto dall'unione discriminata"),
    ("outside the subtask scope", "gia' imposto da Scope.check_write"),
    ("does not make it happen", "misurata inefficace: violata nel 40% dei tentativi"),
    ("belong to OTHER subtasks", "inerte col planner spento: non ci sono altre sottofasi"),
    ("Later subtasks own the rest", "inerte col planner spento"),
    ("EXACT name", "duplicata dall'errore azionabile del router (difflib)"),
    ("f-strings", "duplicata da syntax_hint, che arriva al momento del fallimento"),
])
def test_minimal_drops_what_has_a_reason_to_go(frammento, motivo, monkeypatch):
    m = _card("minimal", monkeypatch)
    assert frammento not in m, f"'{frammento}' andava tolta: {motivo}"


def test_both_variants_are_stable_across_builds(monkeypatch):
    """La card sta in S2: due build consecutive devono darla byte-identica,
    altrimenti il prefisso salta e il riuso va a zero (D9)."""
    for variant in (None, "minimal"):
        assert _card(variant, monkeypatch) == _card(variant, monkeypatch)
