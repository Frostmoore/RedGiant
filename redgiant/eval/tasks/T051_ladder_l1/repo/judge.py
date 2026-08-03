"""Giudice esterno L1 — NON modificabile. Controlla i FATTI.
Exit 0 = verified."""
import re
import sys
from pathlib import Path

EXPECTED = {'eridanus_listen_port': '915', 'norma_retention_days': '888'}


def main() -> int:
    p = Path("answer.txt")
    if not p.is_file():
        print("FAIL: answer.txt missing")
        return 1
    text = p.read_text(encoding="utf-8")
    for key, value in EXPECTED.items():
        m = re.search(re.escape(key) + r"\s*=\s*(\S+)", text)
        got = m.group(1).strip().rstrip(",.;") if m else None
        if got != value:
            # il giudice NON rivela il valore atteso (fix 2026-08-03): prima
            # stampava 'expected X, got Y', cioe' regalava la risposta a
            # chiunque eseguisse il check — il task misurava la lettura di un
            # messaggio d'errore, non la capacita' di trovare e sommare
            print(f"FAIL: {key} is missing or wrong (got {got})")
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
