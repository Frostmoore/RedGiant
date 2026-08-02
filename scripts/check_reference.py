"""Verifica meccanica atlante <-> codice (piano F0.7, Passo 3 del rituale di fine fase).

Estrae via AST le classi e le funzioni reali di redgiant/ e le confronta con le
firme documentate nel codebase_reference.md (blocchi ```python nella sezione
"Classi e metodi"). Exit != 0 su qualunque divergenza: il rituale si ferma.

Regole:
- i nomi che iniziano con "_" (tranne __init__) sono opzionali nell'atlante,
  ma SE documentati devono coincidere;
- tests/, bench/ e scripts/ sono fuori perimetro: l'atlante documenta il pacchetto.

Uso:  python scripts/check_reference.py [--package redgiant] [--reference memory/codebase_reference.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # eseguibile anche senza install -e

# PS1.1: l'estrattore vive in redgiant/plansys/astscan.py (lo usa anche il
# Ledger Builder); qui si importa — un solo estrattore in tutto il repo.
from redgiant.plansys.astscan import extract_signatures, normalize_signature  # noqa: E402

_normalize = normalize_signature

_SECTION_RE = re.compile(r"^##\s+\d*\.?\s*Classi e metodi\s*$", re.MULTILINE)
_NEXT_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)
_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_DOC_DEF_RE = re.compile(r"^(class\s+\w+(\(.*\))?\s*:?|(?:async\s+)?def\s+\w+\s*\(.*\)(\s*->\s*.+?)?\s*:?)$")


def extract_documented(md_path: Path) -> dict[str, list[str]]:
    """Firme documentate nell'atlante, sezione 'Classi e metodi'."""
    text = md_path.read_text(encoding="utf-8")
    m = _SECTION_RE.search(text)
    if not m:
        raise SystemExit(f"{md_path.name}: sezione 'Classi e metodi' non trovata")
    tail = text[m.end():]
    nxt = _NEXT_SECTION_RE.search(tail)
    section = tail[: nxt.start()] if nxt else tail

    out: dict[str, list[str]] = {}
    for block in _FENCE_RE.findall(section):
        current_class: str | None = None
        for raw in block.splitlines():
            line = re.sub(r"\s*#.*$", "", raw).rstrip()   # via i commenti PRIMA del match
            stripped = line.strip()
            if not _DOC_DEF_RE.match(stripped):
                continue
            sig = _normalize(stripped)
            if stripped.startswith("class "):
                name = re.match(r"class\s+(\w+)", stripped).group(1)
                current_class = name
                out.setdefault(name, []).append(f"class {name}")  # basi ignorate
            else:
                name = re.search(r"def\s+(\w+)", stripped).group(1)
                indented = line != stripped  # metodo se indentato sotto una classe
                key = f"{current_class}.{name}" if (indented and current_class) else name
                out.setdefault(key, []).append(sig)
    return out


def _is_optional(name: str) -> bool:
    leaf = name.rsplit(".", 1)[-1]
    return leaf.startswith("_") and leaf != "__init__"


def compare(real: dict[str, list[str]], doc: dict[str, list[str]]) -> list[str]:
    problems: list[str] = []
    for name, sigs in sorted(real.items()):
        if name not in doc:
            if not _is_optional(name):
                problems.append(f"[non documentato]   {name}: {sigs[0]}")
            continue
        if not set(sigs) & set(doc[name]):
            problems.append(
                f"[firma divergente]  {name}:\n    codice:  {sigs[0]}\n    atlante: {doc[name][0]}"
            )
    for name, sigs in sorted(doc.items()):
        if name not in real:
            problems.append(f"[solo nell'atlante] {name}: {sigs[0]}  <- PEGGIO: documentato ma inesistente")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="verifica firme atlante <-> codice")
    ap.add_argument("--package", default="redgiant")
    ap.add_argument("--reference", default="memory/codebase_reference.md")
    ns = ap.parse_args()

    real = extract_signatures(ROOT / ns.package)
    doc = extract_documented(ROOT / ns.reference)
    problems = compare(real, doc)
    if problems:
        print(f"ATLANTE NON ALLINEATO — {len(problems)} problemi:\n")
        print("\n".join(problems))
        return 1
    print(f"OK: atlante allineato ({len(real)} simboli reali, {len(doc)} documentati).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
