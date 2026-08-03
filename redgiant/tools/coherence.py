"""Guardia di coerenza aritmetica sulla scrittura (F4 applicato ai CONTENUTI).

Perche' esiste (esperimento sull'obbedienza, data.md §7.5): sul gradino L5
della ladder il modello trovava 5 fatti su 5 corretti e poi sbagliava la
somma (1892 invece di 1792, riporto perso). Tre livelli di persuasione
testuale — regola numerata nel prompt, nome esplicito del tool, descrizione
"MANDATORY" — hanno portato l'uso della calcolatrice dal 16% al 40% e il
punteggio del gradino non si e' mosso. Conclusione misurata: un'istruzione
non produce obbedienza.

Quindi l'operazione si TOGLIE dalle mani del modello. Un totale non e'
significato, e' *identita' derivata* dai valori che il modello stesso ha
scritto: appartiene al control plane (PS-D11). Questa guardia non giudica se
i fatti sono giusti — quello lo fa il giudice esterno — verifica solo che
l'artefatto non sia internamente incoerente, e se lo e' NON lo scrive,
restituendo il valore corretto. Stesso contratto di `fs.syntax_check`: un
file incoerente non deve mai esistere.

Deliberatamente CONSERVATIVA (un falso positivo qui blocca un lavoro
legittimo, che e' molto peggio di un mancato aiuto):
- solo file di testo (.txt, .md, senza estensione), mai codice o config;
- serve una riga di totale riconoscibile, ULTIMA fra le assegnazioni
  numeriche (un totale sta in fondo: un `total=` in mezzo ad altre chiavi e'
  quasi sempre un dato non derivato);
- servono almeno 2 addendi;
- una sola riga di totale: due totali significano sezioni distinte, e la
  somma "di tutto" non e' piu' definita.

Ablabile con RG_WORKER_ABLATE=coherence (regola di metodo: ogni componente
aggiunto dev'essere ablabile, sennò il suo contributo non e' attribuibile).
"""

from __future__ import annotations

import re
from pathlib import Path

# suffissi su cui la guardia e' applicabile: prosa e artefatti di risposta.
# Il codice e i file di configurazione sono ESCLUSI di proposito: la' un
# 'total = 100' accanto ad altri numeri e' un valore indipendente, non una
# somma, e rifiutare la scrittura sarebbe un falso positivo grave.
_TEXTUAL = {"", ".txt", ".md", ".text", ".answer", ".out"}

_TOTAL_KEYS = {"total", "totale", "sum", "somma", "grand_total", "grandtotal",
               "sum_total", "overall", "totale_generale"}

# 'chiave = numero' da sola sulla riga (niente unita', niente commenti):
# il formato in cui un artefatto dichiara un fatto atomico.
_ASSIGN = re.compile(
    r"^\s*[-*]?\s*([A-Za-z_][A-Za-z0-9_.\-]*)\s*[=:]\s*(-?\d+(?:\.\d+)?)\s*[,.;]?\s*$")

_TOL = 1e-9


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(v)


def arithmetic_check(path: Path, content: str) -> str | None:
    """Messaggio d'errore azionabile, o None se l'artefatto e' coerente."""
    if path.suffix.lower() not in _TEXTUAL:
        return None

    pairs: list[tuple[str, float]] = []
    for line in content.splitlines():
        m = _ASSIGN.match(line)
        if m:
            pairs.append((m.group(1), float(m.group(2))))
    if len(pairs) < 3:  # almeno 2 addendi + 1 totale
        return None

    totals = [i for i, (k, _) in enumerate(pairs) if k.lower() in _TOTAL_KEYS]
    if len(totals) != 1 or totals[0] != len(pairs) - 1:
        return None

    addends = [v for _, v in pairs[:-1]]
    declared = pairs[-1][1]
    real = sum(addends)
    if abs(real - declared) <= _TOL:
        return None

    shown = addends if len(addends) <= 12 else addends[:12]
    expr = " + ".join(_fmt(v) for v in shown) + (" + ..." if len(shown) < len(addends) else "")
    return (f"{pairs[-1][0]}={_fmt(declared)} is WRONG: the {len(addends)} "
            f"values you wrote sum to {_fmt(real)} "
            f"({expr} = {_fmt(real)}). Send the SAME content again with "
            f"{pairs[-1][0]}={_fmt(real)} — change nothing else.")
