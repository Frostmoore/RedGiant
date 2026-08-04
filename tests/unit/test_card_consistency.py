"""La card non deve nominare strumenti che il catalogo non offre.

Bug trovato da F5.0 (2026-08-04): la regola 13 di `worker.md` imponeva di usare
SEMPRE `calculator` — uno strumento che LAD.13 aveva tolto dal catalogo. Il
modello riceveva l'ordine di usare un tool che non poteva vedere, a ogni passo,
per ~59 token a chiamata. Spiega anche le 8 chiamate a `calculator` inesistente
osservate nel braccio ablato (`data.md` §7.9.4).

E' una classe di errore che si ripresenta a ogni componente spento: il test la
rende impossibile da reintrodurre in silenzio.
"""

import re
from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.tools.base import Scope
from redgiant.tools.router import default_catalog

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "redgiant" / "prompts" / "roles"
CONFIG_DIR = ROOT / "config"


def _default_tool_names(tmp_path) -> set[str]:
    cfg = Config.load("dev-fast", CONFIG_DIR)
    return set(default_catalog(cfg, Scope(tmp_path, ["*.txt"]), {}))


@pytest.mark.parametrize("card", sorted(CARDS.glob("*.md")), ids=lambda p: p.name)
def test_cards_only_reference_tools_that_exist(card, tmp_path, monkeypatch):
    """Ogni `nome_tool` citato nella card dev'essere nel catalogo di DEFAULT.
    I nomi in backtick sono la convenzione con cui le card citano gli
    strumenti; i segnaposto negativi (quelli che la card insegna a NON usare)
    sono esclusi esplicitamente."""
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    monkeypatch.delenv("RG_CALCULATOR", raising=False)
    available = _default_tool_names(tmp_path)
    text = card.read_text(encoding="utf-8")

    # esempi negativi che la card cita apposta per insegnare a evitarli
    negative = {"tool_name", "tool_call_spec_id_1"}
    known_tools = {"read_file", "list_files", "search_code", "edit_file",
                   "write_file", "write_patch", "run_tests",
                   "register_test_command", "calculator", "http_get",
                   "git_status", "git_diff"}

    cited = {m for m in re.findall(r"\b([a-z_]{4,})\b", text)
             if m in known_tools} - negative
    missing = cited - available
    assert not missing, (
        f"{card.name} cita strumenti FUORI dal catalogo di default: {missing}. "
        f"Un ordine di usare un tool che il modello non vede e' un bug: "
        f"o si riaccende lo strumento, o si toglie la regola.")
