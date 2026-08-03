"""Giudice esterno T030 — NON modificabile (fuori writable_globs).
Controlla i FATTI, non la forma: answer.txt deve contenere i due valori
scritti nei documenti. Exit 0 = verified."""
import re
import sys
from pathlib import Path


def main() -> int:
    p = Path("answer.txt")
    if not p.is_file():
        print("FAIL: answer.txt missing")
        return 1
    text = p.read_text(encoding="utf-8")
    port = re.search(r"staging_port\s*=\s*(\d+)", text)
    year = re.search(r"project_start\s*=\s*(\d+)", text)
    if not port or port.group(1) != "8443":
        print(f"FAIL: staging_port wrong or missing (got {port and port.group(1)})")
        return 1
    if not year or year.group(1) != "2019":
        print(f"FAIL: project_start wrong or missing (got {year and year.group(1)})")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
