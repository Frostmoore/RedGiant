"""Giudice esterno T032 — NON modificabile. CSV esatto, ordine incluso.
Exit 0 = verified."""
import sys
from pathlib import Path

EXPECTED = [
    "name,email,role",
    "Ada Moretti,ada.moretti@example.org,engineer",
    "Luca Bianchi,luca.bianchi@example.org,designer",
    "Sara Conti,sara.conti@example.org,manager",
]


def main() -> int:
    p = Path("out.csv")
    if not p.is_file():
        print("FAIL: out.csv missing")
        return 1
    lines = [l.rstrip("\r") for l in
             p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if lines != EXPECTED:
        print(f"FAIL: got {lines!r}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
