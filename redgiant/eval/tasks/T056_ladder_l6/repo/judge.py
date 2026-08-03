"""Giudice esterno L6 — NON modificabile. Controlla i FATTI.
Exit 0 = verified."""
import re
import sys
from pathlib import Path

EXPECTED = {'lyra_listen_port': '329', 'vela_retention_days': '151', 'aquila_worker_count': '204', 'hydra_max_connections': '398', 'atlas_cache_size_mb': '686', 'cygnus_listen_port': '707'}


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
