"""Equità del braccio NUDO — il braccio contro cui la tesi del progetto si misura.

Un difetto che penalizza il nudo gonfia i nostri stessi risultati, quindi vale
la pena di un test permanente (come quello sul grassetto nel corpus, che
penalizzava il braccio opposto).

Difetto trovato su T058 (LAD.14): il modello emette a volte i marcatori del
chat template come TESTO (`total=1913</start_of_turn>`); il giudice li cattura
dentro il valore e fa fallire anche una risposta GIUSTA. Il braccio agentico
non ne soffre perche' li' l'output e' vincolato dalla grammatica JSON.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench" / "ladder"))

from run_naked import strip_template_markers  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    ("total=1913</start_of_turn>", "total=1913"),
    ("a=1\nb=2\ntotal=3\n<end_of_turn>", "a=1\nb=2\ntotal=3\n"),
    ("x=5<|channel>thought\nblah", "x=5"),
    ("clean=42\n", "clean=42\n"),          # nessun marcatore: intatto
    ("", ""),
])
def test_markers_are_stripped_but_content_is_not(raw, expected):
    assert strip_template_markers(raw) == expected


def test_a_correct_answer_would_now_pass_the_judge(tmp_path):
    """Il punto vero: prima del fix, una risposta ESATTA falliva."""
    judge = (ROOT / "redgiant" / "eval" / "tasks" / "T058_ladder_l5c"
             / "repo" / "judge.py")
    expected = eval(re.search(r"EXPECTED = (\{.*?\})\n",
                              judge.read_text(encoding="utf-8"), re.S).group(1))
    perfect = "\n".join(f"{k}={v}" for k, v in expected.items())

    import subprocess

    seq = iter(range(100))

    def judge_verdict(answer: str) -> int:
        work = tmp_path / f"w{next(seq)}"
        work.mkdir()
        (work / "judge.py").write_text(judge.read_text(encoding="utf-8"),
                                       encoding="utf-8")
        (work / "answer.txt").write_text(answer + "\n", encoding="utf-8")
        return subprocess.run([sys.executable, "judge.py"], cwd=work,
                              capture_output=True, text=True,
                              timeout=60).returncode

    dirty = perfect + "</start_of_turn>"
    # il difetto: una risposta ESATTA veniva bocciata dal solo marcatore
    assert judge_verdict(dirty) != 0
    # il fix: la stessa risposta, ripulita, passa
    assert judge_verdict(strip_template_markers(dirty)) == 0
    # e il fix non altera una risposta gia' pulita
    assert judge_verdict(strip_template_markers(perfect)) == 0


def test_the_rung_fits_both_naked_arms_without_truncation():
    """Condizione di validita' di LAD.14: su L5c nessun braccio deve troncare.
    Budget nudo = 8192 − 256 − 400 = 7536 · col pensiero pieno = 6000."""
    docs = (ROOT / "redgiant" / "eval" / "tasks" / "T058_ladder_l5c"
            / "repo" / "docs")
    words = sum(len(p.read_text(encoding="utf-8").split())
                for p in docs.glob("*.md"))
    approx_tokens = words * 1.35
    assert approx_tokens < 6000 * 0.75, (
        f"L5c ha ~{approx_tokens:.0f} token: troppo vicino al budget del "
        f"braccio col pensiero (6000), la misura non sarebbe controllata")
