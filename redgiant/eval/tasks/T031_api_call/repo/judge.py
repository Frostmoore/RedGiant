"""Giudice esterno T031 — NON modificabile. Valori attesi CABLATI (il
giudice non chiama il servizio: verifica gli artefatti). Exit 0 = verified."""
import re
import sys
from pathlib import Path


def main() -> int:
    p = Path("report.txt")
    if not p.is_file():
        print("FAIL: report.txt missing")
        return 1
    text = p.read_text(encoding="utf-8")
    ver = re.search(r"version\s*=\s*([\w.\-]+)", text)
    upt = re.search(r"uptime_days\s*=\s*(\d+)", text)
    if not ver or ver.group(1) != "2.4.1":
        print(f"FAIL: version wrong or missing (got {ver and ver.group(1)})")
        return 1
    if not upt or upt.group(1) != "17":
        print(f"FAIL: uptime_days wrong or missing (got {upt and upt.group(1)})")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
