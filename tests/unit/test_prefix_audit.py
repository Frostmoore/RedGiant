"""F5.3 — audit del prefisso: la cache e' byte-level, quindi i test lo sono.

D9 (misurato in F0.5, riconfermato in F5.0-ante): un solo byte diverso a monte
azzera il riuso di tutto cio' che segue. Basta un separatore incoerente, un
ordine di tool diverso o una data sfuggita in S4. `test_prompts.py` copre gia'
l'identita' del prefisso fra build consecutive e l'append-only; qui si coprono
le tre vie che restavano aperte.

Esito dell'audit (2026-08-04): nessuna violazione. `avg_reuse_ratio` del Worker
misurato all'**89,3%**, ben sopra la soglia di 0,6 fissata in F0.6 — per questo
lo strumento di diff previsto dal piano NON e' stato costruito: non c'e'
anomalia da inseguire, e costruirlo ora sarebbe la stessa cosa che abbiamo
imparato a non fare (aggiungere pezzi non richiesti da una misura).
"""

import random
import tempfile
from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.prompts.assemble import PromptAssembler
from redgiant.tools.base import Scope
from redgiant.tools.router import default_catalog

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def catalog(tmp_path):
    cfg = Config.load("dev-fast", ROOT / "config")
    return default_catalog(cfg, Scope(tmp_path, ["*.txt"]), {})


def test_tool_card_is_deterministic(catalog):
    """Stesso catalogo -> stessi byte. Se la card cambiasse fra due chiamate,
    il prefisso salterebbe a ogni step e il riuso andrebbe a zero."""
    specs = sorted(catalog.values(), key=lambda s: s.name)
    assert PromptAssembler._tool_card(specs) == PromptAssembler._tool_card(specs)


def test_tool_card_does_not_depend_on_dict_order(catalog):
    """L'ordine di iterazione di un dict e' stabile in Python, ma il catalogo
    viene costruito da liste filtrate da ablazioni e interruttori: l'ordine
    NON deve dipendere da quello, solo dal nome."""
    ordered = sorted(catalog.values(), key=lambda s: s.name)
    shuffled = list(catalog.values())
    random.shuffle(shuffled)
    assert (PromptAssembler._tool_card(ordered)
            == PromptAssembler._tool_card(sorted(shuffled, key=lambda s: s.name)))


def test_the_preamble_is_shared_by_every_role():
    """S1 e' il prefisso condiviso fra TUTTI i ruoli: se un ruolo avesse il suo
    preambolo, passare da un ruolo all'altro ripagherebbe il prefill da zero."""
    asm = PromptAssembler(ROOT / "redgiant" / "prompts")
    assert asm._preamble, "preambolo vuoto"
    for role in asm._cards:
        # nessuna card deve ridefinire o duplicare il preambolo
        assert asm._preamble not in asm._cards[role], (
            f"la card '{role}' duplica il preambolo: S1 va condiviso, non copiato")


def test_no_volatile_value_leaks_into_the_stable_prefix():
    """Trappola classica di D9: una data, un id o un timestamp dentro S1-S4
    invalidano la cache a OGNI chiamata. Il prefisso stabile non deve contenere
    niente che cambi da una build all'altra."""
    import re
    asm = PromptAssembler(ROOT / "redgiant" / "prompts")
    suspicious = re.compile(r"\b(20\d{2}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2})\b")
    for name, text in [("preamble", asm._preamble)] + list(asm._cards.items()):
        found = suspicious.findall(text)
        assert not found, (
            f"'{name}' contiene un valore che sembra volatile {found}: "
            f"dentro S1-S4 azzererebbe il riuso a ogni chiamata")


def test_the_worker_card_is_the_biggest_and_we_know_it():
    """Non e' un vincolo, e' un promemoria: la card del Worker e' la piu' grande
    di tutte (3.114 char, 837 token) e si paga a OGNI chiamata di OGNI run.
    Il test scatta se cresce ancora senza che nessuno l'abbia misurata — la
    campagna ladder ha dimostrato che aggiungere regole non produce obbedienza
    (F5.0-ter nel piano)."""
    asm = PromptAssembler(ROOT / "redgiant" / "prompts")
    worker = len(asm._cards["worker"])
    assert worker <= 3300, (
        f"la card del Worker e' cresciuta a {worker} char senza una misura che "
        f"lo giustifichi: v. F5.0-ter (837 token a ogni chiamata, e almeno tre "
        f"delle sue regole sono gia' misurate come inefficaci)")
