"""F5.0 — Dove vanno gli 8192 token: composizione del prompt, passo per passo.

Criterio di accettazione di F5.0 (piano): la tabella della composizione media
del prompt agli step 1 / 5 / 10 e **al punto di sfondamento**. Nessuna leva di
F5 si costruisce prima di aver letto questa tabella — LAD.8 aveva mostrato CHE
la finestra si riempie, non DI COSA.

Legge `llm_calls.sections` (JSON per sezione, rilevato a ogni chiamata dal
2026-08-04) e aggrega per posizione dello step dentro il tentativo.

Uso:  python bench/context_breakdown.py [--task-like L7] [--last 40]
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "redgiant.db")
    ap.add_argument("--last", type=int, default=40,
                    help="quanti task recenti considerare")
    ap.add_argument("--ctx", type=int, default=8192)
    ns = ap.parse_args()

    if not ns.db.is_file():
        print(f"DB assente: {ns.db}")
        return 1
    # la colonna `sections` nasce con F5.0 e la migrazione additiva scatta
    # aprendo il DB con StateStore: farlo qui evita di chiedere all'utente un
    # passo che possiamo eseguire noi (e un traceback al posto di una spiegazione)
    sys.path.insert(0, str(ROOT))
    from redgiant.state.store import StateStore
    StateStore(ns.db)

    con = sqlite3.connect(ns.db)
    con.row_factory = sqlite3.Row
    tids = [r[0] for r in con.execute(
        "SELECT id FROM tasks ORDER BY created_at DESC LIMIT ?", (ns.last,))]
    if not tids:
        print("nessun task nel DB")
        return 1
    qs = ",".join("?" * len(tids))
    rows = con.execute(
        f"SELECT task_id, subtask_id, prompt_tokens, sections FROM llm_calls"
        f" WHERE task_id IN ({qs}) AND sections IS NOT NULL ORDER BY id", tids
    ).fetchall()
    if not rows:
        print("nessuna chiamata con la rilevazione per sezione.\n"
              "La colonna `sections` esiste dal 2026-08-04 (F5.0): servono run\n"
              "NUOVE. Le vecchie hanno NULL, che e' corretto — non zero.")
        return 1

    # posizione dello step dentro il tentativo (chiave: task+subtask)
    step_no: dict[tuple, int] = defaultdict(int)
    by_step: dict[int, list[dict]] = defaultdict(list)
    overflow: list[dict] = []
    for r in rows:
        key = (r["task_id"], r["subtask_id"])
        step_no[key] += 1
        sec = json.loads(r["sections"])
        sec["_prompt"] = r["prompt_tokens"]
        by_step[step_no[key]].append(sec)
        if r["prompt_tokens"] >= ns.ctx * 0.85:
            overflow.append(sec)

    names = [k for k in rows and json.loads(rows[0]["sections"]).keys()]
    print(f"F5.0 — composizione del prompt · {len(rows)} chiamate su "
          f"{len(tids)} task · ctx {ns.ctx}\n")
    head = "| step |" + "".join(f" {n[:9]:>9} |" for n in names) + "  totale | n |"
    print(head)
    print("|---" * (len(names) + 3) + "|")

    def line(label: str, bucket: list[dict]) -> None:
        if not bucket:
            return
        cells = "".join(
            f" {sum(b.get(n, 0) for b in bucket) / len(bucket):9.0f} |"
            for n in names)
        tot = sum(b["_prompt"] for b in bucket) / len(bucket)
        print(f"| {label:>4} |{cells} {tot:8.0f} | {len(bucket):2d} |")

    for s in (1, 5, 10, 15):
        line(str(s), by_step.get(s, []))
    line("MAX", overflow)

    if overflow:
        avg = {n: sum(b.get(n, 0) for b in overflow) / len(overflow)
               for n in names}
        worst = max(avg, key=avg.get)
        share = avg[worst] / sum(avg.values()) * 100 if sum(avg.values()) else 0
        print(f"\nVicino al tetto ({len(overflow)} chiamate oltre l'85% di "
              f"{ns.ctx}): la sezione piu' pesante e' **{worst}** "
              f"({avg[worst]:.0f} token, {share:.0f}% del prompt).")
        print("E' li' che va puntata la leva di F5.0-bis.")
    else:
        print(f"\nNessuna chiamata oltre l'85% di {ns.ctx}: per vedere il punto "
              f"di sfondamento serve una run del gradino piu' largo (L7).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
