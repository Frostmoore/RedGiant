"""F5.0-bis + F5.6a — compattazione a ondate RIPETIBILI della catena volatile.

Misura che la motiva (data.md §7.12): la sezione CONTEXT e' l'UNICA che cresce
e al punto di rottura vale 4.600 token, il 65% del prompt. L7 muore li'.

⚠️ **Il difetto che questi test presidiano** (F5.6a, data.md §7.17): la prima
versione compattava UNA volta sola per tentativo. I log l'hanno smentita — su
89 tentativi che avevano compattato, **44 (49%) sono morti per contesto pieno
lo stesso**: la catena ricresce e risatura la finestra. L'errore era di
ragionamento, non di codice: *"a ondate e non a ogni passo"* giustifica il non
compattare a ogni passo, **non** il compattare una volta e basta.

Contratto, e ogni parte ha il suo test:
  1. i risultati vecchi collassano sulla loro `evidence` (mai un riassunto del
     modello: allucinare dentro la catena di verita' sarebbe peggio del testo);
  2. gli ultimi N restano interi;
  3. le ondate si RIARMANO quando la catena risupera la soglia...
  4. ...ma solo se c'e' roba NUOVA da collassare — senza questo vincolo una
     catena gia' tutta compressa verrebbe riscritta a ogni passo, cioe' proprio
     lo sfratto continuo che volevamo evitare;
  5. il preambolo della catena (spec, [PREVIOUS ATTEMPT FAILED]) non si tocca;
  6. c'e' un tetto alle ondate.
"""

from types import SimpleNamespace

import pytest

from redgiant.prompts.assemble import PromptParts
from redgiant.roles.worker import (_COMPACT_KEEP_LAST, _MAX_COMPACT_WAVES,
                                   Worker)


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


def _compact(w, parts, base, blocks, waves=0, upto=0):
    return w._maybe_compact(parts, base, blocks, waves, upto, None)


def test_old_results_collapse_onto_their_evidence(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("SPEC: fai la cosa"
                                   + "".join(b[2] for b in blocks))
    out, waves, upto = _compact(w, parts, "SPEC: fai la cosa", blocks)

    assert waves == 1 and upto == 8 - _COMPACT_KEEP_LAST
    assert len(out.volatile_context) < len(parts.volatile_context) / 2
    assert "[STEP 1] search_code -> 12 matches in 4 files" in out.volatile_context
    assert "EARLIER STEPS COLLAPSED" in out.volatile_context
    assert "do NOT search for it again" in out.volatile_context


def test_the_last_results_stay_whole(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    out, _, _ = _compact(w, parts, "BASE", blocks)
    for k in range(8 - _COMPACT_KEEP_LAST + 1, 9):
        assert f"[STEP {k} RESULT] " + "X" * 100 in out.volatile_context, k
    assert "[STEP 1 RESULT] " + "X" * 100 not in out.volatile_context


def test_waves_rearm_when_the_chain_grows_again(monkeypatch):
    """IL DIFETTO DI F5.6a: con una sola ondata, il 49% dei tentativi che
    avevano compattato moriva comunque per contesto pieno."""
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w = _worker()
    blocks = _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    parts, waves, upto = _compact(w, parts, "BASE", blocks)
    assert waves == 1

    # arrivano tre risultati nuovi: la catena risupera la soglia
    for k in range(9, 12):
        blocks.append((k, "search_code",
                       f"\n[STEP {k}] x\n[STEP {k} RESULT] " + "Y" * 4000,
                       f"\n[STEP {k}] search_code -> 3 matches"))
        parts = parts.with_appended_context(blocks[-1][2])
    parts2, waves2, upto2 = _compact(w, parts, "BASE", blocks, waves, upto)
    assert waves2 == 2, "la seconda ondata non e' scattata"
    assert upto2 > upto
    assert "Y" * 4000 in parts2.volatile_context      # i nuovi restano interi
    assert parts2.volatile_context.count("X" * 4000) == 0   # i vecchi no


def test_no_rewrite_when_there_is_nothing_new_to_collapse(monkeypatch):
    """Il vincolo che impedisce la degenerazione: una catena gia' compressa e
    ancora sopra soglia NON va riscritta a ogni passo — sarebbe lo sfratto
    continuo, il caso peggiore per la cache."""
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    parts, waves, upto = _compact(w, parts, "BASE", blocks)
    again, waves2, upto2 = _compact(w, parts, "BASE", blocks, waves, upto)
    assert again is parts and waves2 == waves and upto2 == upto


def test_there_is_a_cap_on_waves(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w, blocks = _worker(), _blocks(40)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    out, waves, _ = _compact(w, parts, "BASE", blocks,
                             waves=_MAX_COMPACT_WAVES, upto=0)
    assert out is parts and waves == _MAX_COMPACT_WAVES
    assert _MAX_COMPACT_WAVES == 8


def test_the_head_of_the_chain_is_never_touched(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    head = "SPEC: trova 8 fatti\n[PREVIOUS ATTEMPT FAILED] answer.txt missing"
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile(head + "".join(b[2] for b in blocks))
    out, _, _ = _compact(w, parts, head, blocks)
    assert out.volatile_context.startswith(head)


def test_no_compaction_below_the_threshold_or_with_few_blocks(monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    w = _worker()
    small = _parts().with_volatile("BASE\n[STEP 1] piccolo")
    out, waves, _ = _compact(w, small, "BASE", _blocks(4))
    assert out is small and waves == 0

    few = _blocks(_COMPACT_KEEP_LAST)
    big = _parts().with_volatile("BASE" + "".join(b[2] for b in few))
    out2, waves2, _ = _compact(w, big, "BASE", few)
    assert out2 is big and waves2 == 0


def test_compaction_is_ablatable(monkeypatch):
    monkeypatch.setenv("RG_WORKER_ABLATE", "compact")
    w, blocks = _worker(), _blocks(8)
    parts = _parts().with_volatile("BASE" + "".join(b[2] for b in blocks))
    out, waves, _ = _compact(w, parts, "BASE", blocks)
    assert out is parts and waves == 0


def test_with_volatile_keeps_every_other_section_byte_identical():
    p = _parts("vecchio")
    q = p.with_volatile("nuovo")
    assert q.volatile_context == "nuovo"
    assert p.static_prefix_len() == q.static_prefix_len()
    for name in ("preamble", "role_card", "tool_card", "task_header",
                 "durable_state", "output_instruction"):
        assert getattr(p, name) == getattr(q, name)
