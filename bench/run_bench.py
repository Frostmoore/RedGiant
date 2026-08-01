"""F0.5 — Benchmark di baseline (piano): prefill, generazione, riuso del prefisso, slot KV.

Misure (ripetute --repeats volte, media e deviazione):
  1. prefill puro     : prompt sintetico deterministico da ~N token, n_predict=1
  2. generazione      : prompt corto fisso, n_predict=256
  3. riuso prefisso   : A(P) -> B(P+coda)          => riprocessati ~ |coda|
                        C(P con 1 byte cambiato a meta') => riuso si ferma li' (prova di D9)
  4. slot save/restore: A -> save; prompt estraneo (evict); restore -> B
                        NOTA: senza riavvio del server; la persistenza attraverso restart
                        si valida in F5.4 con lo SlotManager.

Uso:
    python bench/run_bench.py --profile severino-sim [--url http://...] \
        [--ctx 1024 4096 8192 16384] [--repeats 3] [--out bench/results]

Output: CSV grezzo in <out>/raw/ (gitignored) + tabella MD committabile in <out>/.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from redgiant.config import Config  # noqa: E402

_SENTENCE = ("The orchestrator selects one subtask, builds the minimal context, "
             "invokes the worker, verifies the result with deterministic oracles, "
             "and records evidence before moving on. ")
_GEN_PROMPT = "<start_of_turn>user\nExplain in two sentences why small language models benefit from short, verifiable subtasks.<end_of_turn>\n<start_of_turn>model\n"


def _mk_prompt(client: httpx.Client, url: str, target_tokens: int) -> str:
    """Testo deterministico di ~target_tokens (mai random: riproducibilita')."""
    n_per = len(_tokenize(client, url, _SENTENCE))
    return _SENTENCE * (target_tokens // n_per + 1)


def _tokenize(client: httpx.Client, url: str, text: str) -> list[int]:
    r = client.post(f"{url}/tokenize", json={"content": text}, timeout=120.0)
    r.raise_for_status()
    return r.json()["tokens"]


def _completion(client: httpx.Client, url: str, prompt: str, *, n_predict: int,
                cache_prompt: bool) -> dict:
    r = client.post(f"{url}/completion", json={
        "prompt": prompt, "n_predict": n_predict, "temperature": 0.0,
        "cache_prompt": cache_prompt, "seed": 42,
    }, timeout=1800.0)
    r.raise_for_status()
    return r.json()["timings"] | {"content_len": len(r.json().get("content", ""))}


def _slot(client: httpx.Client, url: str, action: str, filename: str) -> dict:
    r = client.post(f"{url}/slots/0", params={"action": action},
                    json={"filename": filename}, timeout=600.0)
    r.raise_for_status()
    return r.json()


def run(profile: str, url: str, ctx_sizes: list[int], repeats: int, out_dir: Path) -> Path:
    client = httpx.Client()
    props = client.get(f"{url}/props", timeout=30.0).json()
    build = props.get("build_info", "n/a")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"baseline_{profile}_{stamp}.csv"
    rows: list[dict] = []

    def rec(kind: str, ctx: int, rep: int, t: dict) -> None:
        rows.append({"kind": kind, "ctx": ctx, "rep": rep,
                     "prompt_n": t.get("prompt_n"), "prompt_ms": t.get("prompt_ms"),
                     "prompt_tps": t.get("prompt_per_second"),
                     "gen_n": t.get("predicted_n"), "gen_ms": t.get("predicted_ms"),
                     "gen_tps": t.get("predicted_per_second")})

    # 1) prefill puro per ctx  (cache_prompt=False: ogni run paga tutto)
    prefill_stats: dict[int, list[float]] = {}
    for ctx in ctx_sizes:
        prompt = _mk_prompt(client, url, ctx)
        for rep in range(repeats):
            t = _completion(client, url, prompt, n_predict=1, cache_prompt=False)
            rec("prefill", ctx, rep, t)
            prefill_stats.setdefault(ctx, []).append(t["prompt_per_second"])

    # 2) generazione
    gen_tps: list[float] = []
    for rep in range(repeats):
        t = _completion(client, url, _GEN_PROMPT, n_predict=256, cache_prompt=False)
        rec("generate", 0, rep, t)
        gen_tps.append(t["predicted_per_second"])

    # 3) riuso del prefisso (ctx medio della lista)
    ctx_mid = ctx_sizes[len(ctx_sizes) // 2]
    base = _mk_prompt(client, url, ctx_mid)
    tail = _SENTENCE * 2
    ta = _completion(client, url, base, n_predict=1, cache_prompt=True)
    rec("reuse_A_cold", ctx_mid, 0, ta)
    tb = _completion(client, url, base + tail, n_predict=1, cache_prompt=True)
    rec("reuse_B_appended", ctx_mid, 0, tb)
    mutated = base[: len(base) // 2] + "X" + base[len(base) // 2 + 1:]
    tc = _completion(client, url, mutated, n_predict=1, cache_prompt=True)
    rec("reuse_C_mutated_mid", ctx_mid, 0, tc)

    # 4) slot save/restore (senza riavvio: v. docstring)
    slot_note = "ok"
    try:
        _completion(client, url, base, n_predict=1, cache_prompt=True)   # cache = base
        _slot(client, url, "save", f"bench_{stamp}.bin")
        _completion(client, url, _mk_prompt(client, url, ctx_mid) [::-1], n_predict=1,
                    cache_prompt=True)                                    # evict con testo diverso
        _slot(client, url, "restore", f"bench_{stamp}.bin")
        td = _completion(client, url, base + tail, n_predict=1, cache_prompt=True)
        rec("slot_restore_then_append", ctx_mid, 0, td)
    except httpx.HTTPStatusError as e:
        slot_note = f"FALLITO: {e.response.status_code} {e.response.text[:200]}"

    with raw_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # report MD
    md = [
        f"# F0.5 — Baseline `{profile}`",
        "",
        f"Data: {stamp} UTC · endpoint `{url}` · server `{build}` · repeats {repeats}",
        "",
        "## Prefill freddo",
        "",
        "| ctx target | tok/s (media) | dev.std | tempo per prompt pieno |",
        "|---|---|---|---|",
    ]
    for ctx, vals in prefill_stats.items():
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        md.append(f"| {ctx} | {mean:.0f} | {sd:.0f} | {ctx / mean:.1f}s |")
    md += [
        "",
        f"## Generazione: **{statistics.mean(gen_tps):.1f} tok/s** "
        f"(dev.std {statistics.stdev(gen_tps) if len(gen_tps) > 1 else 0:.1f})",
        "",
        "## Riuso del prefisso (ctx ~" + str(ctx_mid) + ")",
        "",
        "| scenario | token riprocessati | atteso |",
        "|---|---|---|",
        f"| A freddo | {ta['prompt_n']} | ~{ctx_mid} (tutto) |",
        f"| B = A+coda | {tb['prompt_n']} | ~|coda| (pochi) |",
        f"| C = byte cambiato a meta' | {tc['prompt_n']} | ~meta' di A |",
        "",
        f"**Prova di D9:** un byte a meta' prompt costa {tc['prompt_n']} token riprocessati "
        f"contro i {tb['prompt_n']} dell'append puro.",
        "",
        f"## Slot save/restore: {slot_note}",
        "",
        "Numeri grezzi: `" + str(raw_path.relative_to(out_dir.parent)) + "`",
        "",
    ]
    if profile == "dev-fast":
        md.insert(1, "\n> ⚠️ PROFILO NON UFFICIALE (D6): numeri validi solo come confronto informale.\n")
    md_path = out_dir / f"f0_baseline_{profile}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"report: {md_path}")
    return md_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--url", default=None, help="override dell'endpoint del profilo")
    ap.add_argument("--ctx", type=int, nargs="+", default=[1024, 4096, 8192, 16384])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, default=Path("bench/results"))
    ns = ap.parse_args()
    url = ns.url or Config.load(ns.profile).llm.base_url
    run(ns.profile, url.rstrip("/"), ns.ctx, ns.repeats, ns.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
