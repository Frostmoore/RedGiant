"""Giudice esterno L7 — NON modificabile. Controlla i FATTI.
Exit 0 = verified."""
import re
import sys
from pathlib import Path

EXPECTED = {'mensa_listen_port': '210', 'pyxis_retention_days': '383', 'norma_worker_count': '459', 'phoenix_max_connections': '476', 'orion_cache_size_mb': '759', 'borealis_listen_port': '695', 'dorado_retention_days': '504', 'tucana_worker_count': '733', 'total': '4219'}


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
