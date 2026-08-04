"""F5.2 — Riuso della KV: il conto che chiude la condizione (b) di F5.0-bis.

Confronta i due bracci dell'A/B della compattazione usando i dati GIA' raccolti:
quanto contesto compra la compattazione, e quanto paga in riuso del prefisso.

Uso: python bench/reuse_report.py [--last 80]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from redgiant.core.cache_probe import reuse_by_step, reuse_stats  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "redgiant.db")
    ap.add_argument("--last", type=int, default=80,
                    help="task recenti (i due bracci dell'ultimo A/B)")
    ns = ap.parse_args()

    con = sqlite3.connect(ns.db)
    tids = [r[0] for r in con.execute(
        "SELECT id FROM tasks ORDER BY created_at DESC LIMIT ?", (ns.last,))]
    if not tids:
        print("nessun task")
        return 1
    # l'A/B gira il braccio `full` per primo: la meta' PIU' RECENTE e' l'ablato
    half = len(tids) // 2
    arms = {"-compact (ablato)": tids[:half], "full (compattazione)": tids[half:]}

    print(f"F5.2 — riuso della KV · {ns.last} task\n")
    print("| braccio | chiamate | riuso medio | token riprocessati | prefill medio |")
    print("|---|---|---|---|---|")
    saved: dict[str, int] = {}
    for arm, ids in arms.items():
        for s in reuse_stats(ns.db, ids):
            if s.role != "worker":
                continue
            saved[arm] = s.reprocessed_tokens
            print(f"| {arm} | {s.calls} | **{s.avg_reuse_ratio*100:.1f}%** | "
                  f"{s.reprocessed_tokens:,} | {s.avg_prefill_ms:.0f} ms |")

    print("\n**Riuso per posizione dello step** (la firma dell'append-only: "
          "deve CRESCERE)\n")
    print("| step | " + " | ".join(arms) + " |")
    print("|---|" + "---|" * len(arms))
    curves = {a: dict((k, v) for k, v, _ in reuse_by_step(ns.db, ids))
              for a, ids in arms.items()}
    for k in (1, 2, 3, 5, 8, 12, 16):
        cells = " | ".join(f"{curves[a].get(k, float('nan'))*100:.0f}%"
                           if k in curves[a] else "—" for a in arms)
        print(f"| {k} | {cells} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
