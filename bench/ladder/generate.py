"""Generatore della LADDER (richiesta utente 2026-08-03: "batteria di test di
difficolta' crescente, nudo finche' non fallisce, poi col loop agentico").

Asse di difficolta' = AMPIEZZA, non cognizione: ogni singolo fatto resta
banale da estrarre; cresce SOLO la quantita' di materiale in cui e' sepolto
(+ distrattori, + fatti richiesti, + computazione, + catena di artefatti).
Cosi' il confronto nudo-vs-agentico isola esattamente cio' che la tesi
rivendica: i modelli piccoli non falliscono sul singolo passo, falliscono
sull'ampiezza.

Corpus DETERMINISTICO (seed fisso): rigenerando si ottengono gli stessi byte.
Uso: python bench/ladder/generate.py
"""

import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "redgiant" / "eval" / "tasks"

SYSTEMS = ["atlas", "borealis", "cygnus", "draco", "eridanus", "fornax",
           "gemini", "hydra", "indus", "lyra", "mensa", "norma", "orion",
           "pavo", "phoenix", "pyxis", "reticulum", "sagitta", "tucana",
           "vela", "volans", "aquila", "carina", "dorado", "grus"]
METRICS = ["listen_port", "retention_days", "worker_count", "max_connections",
           "cache_size_mb"]
FILLER = [
    "The deployment pipeline runs nightly and publishes artifacts to the "
    "internal registry.",
    "Ownership was transferred to the platform team after the last audit.",
    "Alerts are routed to the on-call rotation; escalation happens after "
    "fifteen minutes.",
    "Backups are taken hourly and pruned by the retention policy.",
    "The service exposes Prometheus metrics on the standard admin path.",
    "Configuration lives in the central repository and is applied by CI.",
    "Load tests are executed before every major release.",
    "The runbook documents the failover procedure in detail.",
]

# (rung, n_docs, n_facts, computed_total, chained)
RUNGS = [
    ("L1", 5, 2, False, False),
    ("L2", 15, 3, False, False),
    ("L3", 40, 4, False, False),
    ("L4", 90, 5, False, False),      # ~5.7K tok: ancora dentro gli 8192
    ("L5", 90, 5, True, False),       # idem + totale calcolato
    ("L6", 200, 6, False, False),     # ~12.8K tok: SFONDA il contesto
    ("L7", 400, 8, True, False),      # ~25K tok: 3x il contesto + calcolo
]

JUDGE = '''"""Giudice esterno {rid} — NON modificabile. Controlla i FATTI.
Exit 0 = verified."""
import re
import sys
from pathlib import Path

EXPECTED = {expected!r}


def main() -> int:
    p = Path("answer.txt")
    if not p.is_file():
        print("FAIL: answer.txt missing")
        return 1
    text = p.read_text(encoding="utf-8")
    for key, value in EXPECTED.items():
        m = re.search(re.escape(key) + r"\\s*=\\s*(\\S+)", text)
        got = m.group(1).strip().rstrip(",.;") if m else None
        if got != value:
            print(f"FAIL: {{key}} expected {{value}}, got {{got}}")
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def build_rung(rid: str, n_docs: int, n_facts: int, computed: bool,
               chained: bool) -> None:
    rng = random.Random(f"ladder-{rid}")
    task_dir = TASKS / f"T05{rid[1]}_ladder_{rid.lower()}"
    repo = task_dir / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    (repo / "docs").mkdir(parents=True)

    systems = SYSTEMS[:]
    rng.shuffle(systems)
    targets = [(systems[i], METRICS[i % len(METRICS)],
                100 + rng.randrange(1, 900))
               for i in range(n_facts)]
    target_docs = rng.sample(range(n_docs), n_facts)

    expected = {}
    for i, (sysname, metric, value) in enumerate(targets):
        expected[f"{sysname}_{metric}"] = str(value)
    if computed:
        expected["total"] = str(sum(v for _, _, v in targets))

    for d in range(n_docs):
        lines = [f"# Service note {d:03d}", ""]
        if d in target_docs:
            sysname, metric, value = targets[target_docs.index(d)]
            # FORMATO UNIFORME coi distrattori (fix 2026-08-03): il grassetto
            # markdown sui soli bersagli era un artefatto SLEALE — una ricerca
            # naturale "Service mensa" falliva per gli asterischi in mezzo,
            # penalizzando il braccio workflow e non quello nudo (che legge
            # tutto inline). L'unica difficolta' dev'essere l'AMPIEZZA.
            lines.append(f"Service {sysname}: the {metric} is {value}.")
            lines.append("")
        # distrattori: stessa metrica, sistema DIVERSO (mai ambiguo)
        for _ in range(2):
            other = systems[rng.randrange(n_facts, len(systems))]
            lines.append(f"Service {other}: the "
                         f"{METRICS[rng.randrange(len(METRICS))]} is "
                         f"{100 + rng.randrange(1, 900)}.")
        lines.append("")
        lines += [FILLER[rng.randrange(len(FILLER))] for _ in range(3)]
        (repo / "docs" / f"note_{d:03d}.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")

    (repo / "judge.py").write_text(
        JUDGE.format(rid=rid, expected=expected), encoding="utf-8")

    asked = "; ".join(f"the {m} of service {s}" for s, m, _ in targets)
    keys = ", ".join(f"'{s}_{m}=<value>'" for s, m, _ in targets)
    extra = (" Then add a final line 'total=<sum of all the values above>'."
             if computed else "")
    prompt = (f"The folder docs/ contains {n_docs} service notes. Find these "
              f"facts, reading ONLY what you need: {asked}. Write answer.txt "
              f"with one line per fact, exactly {keys}.{extra} Beware: other "
              f"services have similar metrics — match the service name "
              f"exactly. Verify with the 'check' command; it must pass.")

    (task_dir / "task.toml").write_text(
        f'id = "T05{rid[1]}"\n'
        f'domain = "research_local"\n'
        f'prompt = "{prompt}"\n'
        f'success_cmd = "python judge.py"\n'
        f'timeout_s = 3600\n'
        f'tags = ["ladder", "{rid.lower()}", "research_local"]\n'
        f'writable_globs = ["answer.txt"]\n'
        # il budget di passi e' proporzionale alla TAGLIA (ladder: 8 fatti in
        # 400 documenti non si raccolgono in 20 mosse — L7 moriva senza mai
        # scrivere il file, non per incapacita' ma per budget)
        f'worker_max_steps = {max(20, min(60, n_docs // 5 + n_facts * 3))}\n'
        f'naked_materials = ["docs/*.md"]\n'
        f'naked_instruction = "{prompt}"\n\n'
        f"# LADDER {rid}: {n_docs} documenti, {n_facts} fatti"
        f"{', totale calcolato' if computed else ''} — generato da"
        f" bench/ladder/generate.py (seed fisso).\n\n"
        + "[test_commands]\ncheck = [\"python\", \"judge.py\"]\n",
        encoding="utf-8")
    total_words = sum(len(p.read_text(encoding="utf-8").split())
                      for p in (repo / "docs").glob("*.md"))
    print(f"{rid}: {n_docs} docs, {n_facts} facts, ~{total_words} words "
          f"(~{int(total_words * 1.35)} tok) -> {task_dir.name}")


if __name__ == "__main__":
    for rung in RUNGS:
        build_rung(*rung)
