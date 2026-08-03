"""Giudice esterno L4 — NON modificabile. Controlla i FATTI.
Exit 0 = verified."""
import re
import sys
from pathlib import Path

EXPECTED = {'pavo_listen_port': '146', 'borealis_retention_days': '479', 'eridanus_worker_count': '913', 'dorado_max_connections': '247', 'carina_cache_size_mb': '666'}


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
            print(f"FAIL: {key} expected {value}, got {got}")
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
