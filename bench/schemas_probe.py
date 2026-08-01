"""F0.3 — Verifica del constrained decoding su Gemma 4 E2B (piano, protocollo esatto).

Tre schemi realistici (simulano SupervisorDecision, PlannerOutput, PhaseDesign);
per ciascuno N generazioni con guided decoding (json_schema) contro llama-server,
piu' un confronto di velocita' con/senza grammatica a parita' di prompt.

Uso:
    python bench/schemas_probe.py --url http://127.0.0.1:8080 --n 20 \
        --out bench/results/f0_constrained_decoding.md

Modulo "usa-e-getta" per contratto di piano: gli schemi veri nascono in F1+.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProbeDecision(_Strict):
    """Simula SupervisorDecision (enum a 9 valori + ragione corta)."""
    decision: Literal["accept", "retry_subtask", "repair", "redesign_phase",
                      "replan_global", "rollback", "ask_user", "stop_partial", "stop_failed"]
    reason: str = Field(max_length=200)


class ProbePhase(_Strict):
    id: str
    title: str
    depends_on: list[str]
    completion_criteria: list[str] = Field(max_length=4)


class ProbePlan(_Strict):
    """Simula PlannerOutput (oggetto annidato)."""
    goal: str = Field(max_length=300)
    success_criteria: list[str] = Field(max_length=5)
    phases: list[ProbePhase] = Field(max_length=5)


class ProbeSubtask(_Strict):
    id: str
    title: str
    objective: str = Field(max_length=300)
    inputs: list[str]
    tools: list[str]
    expected_outputs: list[str]
    completion_criteria: list[str]
    verification: list[str]


class ProbeSubtasks(_Strict):
    """Simula PhaseDesign (lista di oggetti a 8 campi)."""
    phase_id: str
    subtasks: list[ProbeSubtask] = Field(max_length=4)


# LEZIONE F0.3 (prima esecuzione, 2026-08-01): la grammatica VINCOLA ma non INFORMA.
# Senza (a) il template di turno di Gemma e (b) lo schema visibile nel prompt, il modello
# produce struttura valida con contenuto placeholder ("...", "$id"). Quindi: turn markers
# sempre, e lo schema JSON va incluso nel prompt (il futuro S7 fara' esattamente questo).
_TASK = (
    "<start_of_turn>user\n"
    "You are the {role} of a deterministic coding pipeline.\n"
    "User request: \"In a PHP billing service, extract the tax computation out of "
    "InvoiceController into a dedicated TaxCalculator class without changing the public "
    "API, and keep the existing PHPUnit suite green.\"\n{instruction}\n"
    "Respond with exactly one JSON object matching this JSON Schema, filled with real, "
    "meaningful content (never placeholders):\n{schema}\n"
    "Output COMPACT single-line JSON: no pretty-printing, no extra whitespace.\n"
    "<end_of_turn>\n<start_of_turn>model\n"
)
# LEZIONE F0.3 (seconda esecuzione): la grammatica garantisce la forma solo se il budget di
# generazione basta — output troncato a n_predict = JSON rotto NONOSTANTE la grammatica.
# Quindi: max_tokens dimensionato per schema (con margine) + JSON compatto (il pretty-print
# spreca ~20-30% dei token) + lo stop reason va SEMPRE controllato (il futuro LlamaClient
# trattera' 'limit' come errore esplicito, mai come output buono).

def _probes() -> list[tuple[str, type[BaseModel], str, int]]:
    # (nome, modello, ruolo, istruzione, max_tokens dimensionato con margine ~2x)
    specs = [
        ("ProbeDecision", ProbeDecision, "SUPERVISOR",
         "The last subtask failed one regression test (unexpected rounding in totals) "
         "after 1 attempt of 2 allowed. Decide the next action.", 512),
        ("ProbePlan", ProbePlan, "PLANNER",
         "Produce a global plan: goal, success criteria, and at most 5 phases with dependencies.", 1536),
        ("ProbeSubtasks", ProbeSubtasks, "PHASE DESIGNER",
         "Expand phase P3 'Implement the extraction' into at most 4 operative subtasks "
         "with observable completion criteria and verification steps.", 2048),
    ]
    return [(name, model, _TASK.format(
                role=role, instruction=instr,
                schema=json.dumps(model.model_json_schema())), max_tok)
            for name, model, role, instr, max_tok in specs]


_PLACEHOLDERS = {"...", "..", "$id", "$ref", "string", "N/A", ""}


def _degenerate(obj: object) -> int:
    """Conta i campi stringa riempiti con placeholder: la misura della qualita' minima."""
    if isinstance(obj, str):
        return 1 if obj.strip() in _PLACEHOLDERS else 0
    if isinstance(obj, list):
        return sum(_degenerate(x) for x in obj)
    if isinstance(obj, dict):
        return sum(_degenerate(v) for v in obj.values())
    return 0


def _complete(client: httpx.Client, url: str, prompt: str, *, schema: dict | None,
              seed: int, max_tokens: int) -> dict:
    payload: dict = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": 0.2,
        "seed": seed,
        "cache_prompt": True,
    }
    if schema is not None:
        payload["json_schema"] = schema
    r = client.post(f"{url}/completion", json=payload, timeout=600.0)
    r.raise_for_status()
    return r.json()


def run(url: str, n: int, out_path: Path) -> int:
    client = httpx.Client()
    props = client.get(f"{url}/props", timeout=30.0).json()
    lines = [
        "# F0.3 — Constrained decoding su Gemma 4 E2B (QAT UD-Q4_K_XL)",
        "",
        f"Data: {datetime.now(timezone.utc).isoformat(timespec='seconds')} · endpoint: `{url}` · "
        f"n per schema: {n} · temperature 0.2, seed variabile",
        "",
        f"Server: `{json.dumps(props.get('build_info', 'n/a'))}`",
        "",
        "| Schema | JSON validi | Schema validi (Pydantic) | contenuto pieno (no placeholder) | troncati | gen tok/s con grammatica | gen tok/s senza | costo grammatica |",
        "|---|---|---|---|---|---|---|---|",
    ]
    all_valid = True
    for name, model, prompt, max_tok in _probes():
        schema = model.model_json_schema()
        json_ok = 0
        pyd_ok = 0
        full_ok = 0
        truncated = 0
        tps_g: list[float] = []
        samples: list[str] = []
        for i in range(n):
            res = _complete(client, url, prompt, schema=schema, seed=1000 + i, max_tokens=max_tok)
            t = res.get("timings", {})
            if t.get("predicted_per_second"):
                tps_g.append(t["predicted_per_second"])
            content = res.get("content", "")
            if res.get("stop_type") == "limit" or res.get("stopped_limit"):
                truncated += 1
                samples.append(f"[{name} run {i}] TRONCATO a {max_tok} tok: {content[-120:]!r}")
                continue
            try:
                data = json.loads(content)
                json_ok += 1
            except json.JSONDecodeError:
                samples.append(f"[{name} run {i}] JSON rotto: {content[:200]!r}")
                continue
            try:
                model.model_validate(data)
                pyd_ok += 1
                deg = _degenerate(data)
                if deg == 0:
                    full_ok += 1
                if i < 2 or (deg and len(samples) < 6):
                    samples.append(f"[{name} run {i}] deg={deg} {json.dumps(data)[:400]}")
            except ValidationError as e:
                samples.append(f"[{name} run {i}] schema violato: {e.errors()[:2]!r}")
        # confronto senza grammatica (3 run bastano per il tok/s)
        tps_free: list[float] = []
        for i in range(3):
            res = _complete(client, url, prompt, schema=None, seed=2000 + i, max_tokens=max_tok)
            t = res.get("timings", {})
            if t.get("predicted_per_second"):
                tps_free.append(t["predicted_per_second"])
        g = statistics.mean(tps_g) if tps_g else 0.0
        f = statistics.mean(tps_free) if tps_free else 0.0
        cost = f"{(1 - g / f) * 100:+.1f}%" if g and f else "n/a"
        lines.append(f"| {name} | {json_ok}/{n} | {pyd_ok}/{n} | {full_ok}/{n} | {truncated} | {g:.1f} | {f:.1f} | {cost} |")
        lines += ["", "<details><summary>campioni " + name + "</summary>", ""]
        lines += [f"- `{s}`" for s in samples[:6]]
        lines += ["", "</details>", ""]
        if pyd_ok != n or full_ok < n * 0.9:   # forma al 100%; contenuto pieno >=90%
            all_valid = False
    lines += [
        "",
        f"**Esito: {'100% valido — D3 confermata su questo stack' if all_valid else 'VALIDITA'' NON TOTALE — attivare la matrice di fallback F0.3'}**",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report: {out_path}")
    return 0 if all_valid else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", type=Path, default=Path("bench/results/f0_constrained_decoding.md"))
    ns = ap.parse_args()
    return run(ns.url.rstrip("/"), ns.n, ns.out)


if __name__ == "__main__":
    sys.exit(main())
