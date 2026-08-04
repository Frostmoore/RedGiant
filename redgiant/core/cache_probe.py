"""F5.2 — Strumentazione del riuso della KV cache.

Senza questa misura F5 sarebbe ottimizzazione a sentimento: `cached_tokens` e'
gia' su ogni riga di `llm_calls` dal F1.2, qui si aggrega e si espone.

Serve a due domande diverse:

1. **D9 funziona?** Il loop del Worker e' append-only per costruzione (D20):
   il riuso deve CRESCERE passo dopo passo. Se non cresce, qualcosa sta
   rompendo il prefisso stabile e va trovato (F5.3).

2. **Quanto costa la compattazione?** E' la condizione (b) dell'accettazione di
   F5.0-bis: riscrivere la catena volatile compra contesto ma paga in riuso.
   Sapere quanto compra senza sapere quanto paga non e' una misura, e' meta'
   misura — e su un profilo senza `--swa-full` il conto puo' essere molto
   diverso da quello su GPU (`data.md` §7.11).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ReuseStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    calls: int
    avg_reuse_ratio: float      # cached/prompt, 0..1
    prompt_tokens: int          # totale, per pesare il ruolo
    cached_tokens: int
    reprocessed_tokens: int     # prompt - cached: cio' che si paga davvero
    avg_prefill_ms: float


def _rows(db: Path, task_ids: list[str] | None) -> list[sqlite3.Row]:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    if task_ids:
        qs = ",".join("?" * len(task_ids))
        sql = (f"SELECT role, prompt_tokens, cached_tokens, prefill_ms"
               f" FROM llm_calls WHERE task_id IN ({qs})")
        return con.execute(sql, task_ids).fetchall()
    return con.execute(
        "SELECT role, prompt_tokens, cached_tokens, prefill_ms"
        " FROM llm_calls").fetchall()


def reuse_stats(db: Path, task_ids: list[str] | None = None) -> list[ReuseStats]:
    """Aggregato per ruolo. `task_ids=None` = tutto il DB."""
    by_role: dict[str, list[sqlite3.Row]] = {}
    for r in _rows(db, task_ids):
        by_role.setdefault(r["role"], []).append(r)

    out: list[ReuseStats] = []
    for role, rows in sorted(by_role.items()):
        prompt = sum(r["prompt_tokens"] or 0 for r in rows)
        cached = sum(r["cached_tokens"] or 0 for r in rows)
        # media dei rapporti per chiamata, non rapporto delle somme: una
        # chiamata enorme non deve mascherare venti chiamate senza riuso
        ratios = [(r["cached_tokens"] or 0) / r["prompt_tokens"]
                  for r in rows if r["prompt_tokens"]]
        out.append(ReuseStats(
            role=role, calls=len(rows),
            avg_reuse_ratio=sum(ratios) / len(ratios) if ratios else 0.0,
            prompt_tokens=prompt, cached_tokens=cached,
            reprocessed_tokens=max(prompt - cached, 0),
            avg_prefill_ms=sum(r["prefill_ms"] or 0.0 for r in rows) / len(rows)))
    return out


def reuse_by_step(db: Path, task_ids: list[str]) -> list[tuple[int, float, int]]:
    """(posizione dello step, riuso medio, n) — la firma dell'append-only.

    In un loop append-only il riuso deve CRESCERE: allo step 1 il prefisso e'
    freddo, dal secondo in poi la parte stabile e' gia' in cache. Una curva
    piatta o decrescente e' un difetto, non un dato.
    """
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    qs = ",".join("?" * len(task_ids))
    rows = con.execute(
        f"SELECT task_id, subtask_id, prompt_tokens, cached_tokens FROM llm_calls"
        f" WHERE task_id IN ({qs}) ORDER BY id", task_ids).fetchall()

    pos: dict[tuple, int] = {}
    buckets: dict[int, list[float]] = {}
    for r in rows:
        if not r["prompt_tokens"]:
            continue
        key = (r["task_id"], r["subtask_id"])
        pos[key] = pos.get(key, 0) + 1
        buckets.setdefault(pos[key], []).append(
            (r["cached_tokens"] or 0) / r["prompt_tokens"])
    return [(k, sum(v) / len(v), len(v)) for k, v in sorted(buckets.items())]
