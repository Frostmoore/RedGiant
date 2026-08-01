"""Giudice esterno T006: answer.txt deve citare la definizione e il chiamante."""
import sys
from pathlib import Path

p = Path("answer.txt")
if not p.is_file():
    print("answer.txt missing")
    sys.exit(1)
text = p.read_text(encoding="utf-8").replace("\\", "/").lower()
ok = "config/loader.py" in text and "main.py" in text
bad = "util/misc.py" in text
if ok and not bad:
    print("OK")
    sys.exit(0)
print(f"wrong answer: ok={ok} bad={bad}\n{text}")
sys.exit(1)
