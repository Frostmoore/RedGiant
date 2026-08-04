"""F5.0-bis — compattazione a ondate della catena volatile del Worker.

Misura che la motiva (data.md §7.12): la sezione CONTEXT e' l'UNICA che cresce
e al punto di rottura vale 4.600 token, il 65% del prompt. L7 muore li', usando
8,5 passi di media su 60 disponibili (§7.7.2).

Il contratto ha quattro parti, e ognuna ha un test:
  1. i risultati vecchi collassano sulla loro `evidence` — la riga di verita'
     DETERMINISTICA che ogni tool produce gia' (mai un riassunto del modello);
  2. gli ultimi N restano interi;
  3. succede A ONDATE, non a ogni passo (e' cio' che distingue la compattazione
     dallo sfratto continuo, e limita il costo dove il KV shifting non c'e');
  4. il preambolo della catena (spec, [PREVIOUS ATTEMPT FAILED]) non si tocca.
"""

from types import SimpleNamespace

import pytest

from redgiant.prompts.assemble import PromptParts
from redgiant.roles.worker import _COMPACT_KEEP_LAST, Worker


def _parts(volatile: str = "SPEC: fai la cosa") -> PromptParts:
    return PromptParts(preamble="p", role_card="r", tool_card="t",
                       task_header="h", durable_state="s",
                       volatile_context=volatile, output_instruction="o")


def _worker(ctx_size: int = 8192, ratio: int = 1) -> Worker:
    w = Worker.__new__(Worker)
    w.llm = SimpleNamespace(cfg=SimpleNamespace(ctx_size=ctx_size),
                            count_tokens=lambda s: len(s) // ratio)
    return w


def _blocks(n: int) -> list[tuple[int, str, str, str]]:
    return [(k, "search_code",
             f"\n[STEP {k}] {{...}}\n[STEP {k} RESULT] " + "X" * 4000,
             f"\n[STEP {k}] search_code -> 12 matches in 4 files")
            for k in range(1, n + 1)]


def test_old_results_collapse_onto_their_evidence(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("SPEC: fai la cosa"
                                   + "".join(b[2] for b in blocks))
    out, done = w._maybe_compact(parts, "SPEC: fai la cosa", blocks, False, None)

    assert done
    assert len(out.volatile_context) < len(parts.volatile_context) / 2
    # i vecchi ci sono ancora, ma come UNA RIGA ciascuno
    assert "[STEP 1] search_code -> 12 matches in 4 files" in out.volatile_context
    assert "X" * 4000 not in out.volatile_context.split("COLLAPSED")[0]
    # e il modello viene avvisato di cosa e' successo
    assert "EARLIER STEPS COLLAPSED" in out.volatile_context
    assert "do NOT search for it again" in out.volatile_context


def test_the_last_results_stay_whole(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    out, _ = w._maybe_compact(parts, "BASE", blocks, False, None)
    for k in range(8 - _COMPACT_KEEP_LAST + 1, 9):
        assert f"[STEP {k} RESULT] " + "X" * 100 in out.volatile_context, k
    # e i piu' vecchi no
    assert f"[STEP 1 RESULT] " + "X" * 100 not in out.volatile_context


def test_it_happens_in_waves_not_every_step(monkeypatch):
    """Se ricompattasse a ogni passo riscriverebbe il prefisso ogni volta —
    che e' esattamente il caso che la letteratura indica come peggiore per la
    cache. Una volta compattato, il flag lo impedisce."""
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    out, done = w._maybe_compact(parts, "BASE", blocks, False, None)
    assert done
    again, done2 = w._maybe_compact(out, "BASE", blocks, done, None)
    assert again is out and done2 is True      # nessuna riscrittura


def test_the_head_of_the_chain_is_never_touched(monkeypatch):
    """La spec della sottofase e il blocco [PREVIOUS ATTEMPT FAILED] stanno
    all'inizio della catena: perderli significherebbe dimenticare il compito."""
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    head = "SPEC: trova 8 fatti\n[PREVIOUS ATTEMPT FAILED] answer.txt missing"
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile(head + "".join(b[2] for b in blocks))
    out, _ = w._maybe_compact(parts, head, blocks, False, None)
    assert out.volatile_context.startswith(head)


def test_no_compaction_below_the_threshold_or_with_few_blocks(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w = _worker(ctx_size=8192)
    # catena corta: sotto la soglia di token
    blocks = _blocks(4)
    small = _parts().with_volatile("BASE" + "\n[STEP 1] piccolo")
    out, done = w._maybe_compact(small, "BASE", blocks, False, None)
    assert out is small and not done
    # pochi blocchi: non c'e' niente da collassare
    few = _blocks(_COMPACT_KEEP_LAST)
    big = _parts().with_volatile("BASE" + "".join(b[2] for b in few))
    out2, done2 = w._maybe_compact(big, "BASE", few, False, None)
    assert out2 is big and not done2


def test_compaction_is_ablatable(monkeypatch):
    monkeypatch.setenv("RG_WORKER_ABLATE", "compact")
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    out, done = w._maybe_compact(parts, "BASE", blocks, False, None)
    assert out is parts and not done


def test_with_volatile_keeps_every_other_section_byte_identical():
    """La compattazione tocca SOLO S6: e' l'unico punto autorizzato a rompere
    l'append-only di D20, e non deve intaccare il prefisso stabile S1-S4."""
    p = _parts("vecchio")
    q = p.with_volatile("nuovo")
    assert q.volatile_context == "nuovo"
    assert p.static_prefix_len() == q.static_prefix_len()
    for name in ("preamble", "role_card", "tool_card", "task_header",
                 "durable_state", "output_instruction"):
        assert getattr(p, name) == getattr(q, name)
