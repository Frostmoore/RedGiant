"""LlamaClient: l'unico punto del sistema che parla con llama-server (piano F1.2, D2/D3).

Lezioni F0.3 cablate qui:
- guided decoding su ogni chiamata con schema (D3) + rivalidazione Pydantic
  in difesa di profondità (fallita = outcome 'invalid', MAI retry: è un bug di
  piattaforma da fermare);
- stop reason 'limit' = errore esplicito (LlmTruncated), mai output buono;
- ContextOverflow PRIMA di chiamare, col conteggio per sezione (chi diagnostica
  deve vedere subito cosa è gonfio).

Retry: SOLO su errori di trasporto (max 2, backoff 2s). Mai su timeout (su CPU
un timeout è informazione) né su invalid.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, ValidationError

from redgiant.config import LlmProfileCfg
from redgiant.llm.schema import to_llama_schema
from redgiant.prompts.assemble import PromptParts
from redgiant.state.models import LlmCallRow
from redgiant.state.store import StateStore


class LlmError(Exception): ...
class LlmTimeout(LlmError): ...
class LlmTruncated(LlmError): ...
class LlmInvalidOutput(LlmError): ...


class ContextOverflow(LlmError):
    def __init__(self, prompt_tokens: int, ctx_size: int, sections: dict[str, int]) -> None:
        self.prompt_tokens = prompt_tokens
        self.ctx_size = ctx_size
        self.sections = sections
        detail = ", ".join(f"{k}={v}" for k, v in sections.items())
        super().__init__(
            f"prompt of {prompt_tokens} tokens exceeds budget (ctx_size={ctx_size}); "
            f"per-section: {detail}")


@dataclass
class LlmResult:
    text: str
    parsed: BaseModel | None
    prompt_tokens: int
    cached_tokens: int
    gen_tokens: int
    prefill_ms: float
    gen_ms: float
    raw_timings: dict
    # TH0: il pensiero e' usa-e-getta (TH-D2) — il testo si logga per l'analisi,
    # MAI ri-iniettato in altri contesti dal chiamante
    thinking_tokens: int = 0
    thinking_ms: float = 0.0
    thinking_text: str = ""


class LlamaClient:
    def __init__(self, cfg: LlmProfileCfg, store: StateStore | None = None) -> None:
        self.cfg = cfg
        self.store = store
        self._http = httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout_s)

    # ── API ──────────────────────────────────────────────────────────────────

    def complete(self, parts: PromptParts, *, role: str,
                 schema: type[BaseModel] | None = None,
                 max_tokens: int, temperature: float | None = None,
                 task_id: str | None = None, subtask_id: str | None = None,
                 cache_prompt: bool = True,
                 grammar_schema: dict | None = None,
                 think: int | None = None) -> LlmResult:
        """grammar_schema (plansys, batch20): JSON Schema SPECIALIZZATO per la
        grammatica del server (es. enum dinamici sui riferimenti) — deve essere
        un SOTTOINSIEME dello schema di `schema`, che resta il validatore.

        think (TH0, plan_thinking_ab.md): budget del canale di pensiero.
        Two-call protocol (TH-D1): (1) stesso prompt + think_open, SENZA
        grammatica, stop a think_close — il troncamento a budget NON e' errore
        (e' un budget, non un contratto); (2) prompt + canale completo + la
        chiamata strutturata di sempre. `parts` non viene MAI mutato (TH-D2):
        i prompt arricchiti nascono e muoiono qui dentro."""
        prompt = parts.render()
        # F5.0 — la composizione del prompt si rileva SEMPRE, non solo quando
        # esplode. LAD.8 aveva mostrato CHE la finestra si riempie; per sapere
        # quale leva costruire serve sapere DI COSA. Costo misurato sul nostro
        # server: 0,5-6,3 ms per sezione contro step da 1-3 s (~0,5%), quindi
        # niente flag: un dato che serve solo se c'e' sempre non si mette
        # dietro un interruttore che qualcuno dimentichera' di accendere.
        sections = parts.section_tokens(self.count_tokens)
        think_text, think_tok, think_ms = "", 0, 0.0
        if think:
            if not self.cfg.think_close:
                raise LlmError("thinking markers not configured "
                               "([llm] think_open/think_close)")
            # decisione utente (TH0): il budget e' un FUSIBILE, non un
            # bersaglio — ma la risposta (max_tokens) deve avere SEMPRE il suo
            # spazio: il pensiero si clampa a cio' che il contesto concede
            n_base = self.count_tokens(prompt)
            room = self.cfg.ctx_size - n_base - max_tokens - 64
            if room <= 0:
                raise ContextOverflow(n_base + max_tokens, self.cfg.ctx_size,
                                      sections)   # gia' rilevate sopra
            think = min(think, room)
            p1 = {"prompt": prompt + self.cfg.think_open, "n_predict": think,
                  "temperature": (self.cfg.temperature if temperature is None
                                  else temperature),
                  "cache_prompt": cache_prompt, "seed": 42,
                  "stop": [self.cfg.think_close]}
            t1_start = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                r1 = self._post_with_transport_retry("/completion", p1)
            except httpx.TimeoutException as e:
                self._log(task_id, role, subtask_id, schema, t1_start, 0,
                          "timeout", sections=sections)
                raise LlmTimeout(str(e)) from e
            except httpx.HTTPError as e:
                self._log(task_id, role, subtask_id, schema, t1_start, 0,
                          "error", sections=sections)
                raise LlmError(str(e)) from e
            think_text = r1.get("content", "")
            t1 = r1.get("timings", {})
            think_tok = int(t1.get("predicted_n", 0) or 0)
            think_ms = float(t1.get("predicted_ms", 0.0) or 0.0)
            prompt = (prompt + self.cfg.think_open + think_text
                      + self.cfg.think_close + "\n")
        n_prompt = self.count_tokens(prompt)
        if n_prompt + max_tokens > self.cfg.ctx_size:
            raise ContextOverflow(n_prompt, self.cfg.ctx_size, sections)

        payload: dict = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "cache_prompt": cache_prompt,
            # Trappola F1.11: senza seed llama-server usa un seed CASUALE per
            # richiesta -> pipeline non riproducibile, eval non confrontabili.
            "seed": 42,
        }
        if grammar_schema is not None:
            payload["json_schema"] = grammar_schema
        elif schema is not None:
            payload["json_schema"] = to_llama_schema(schema)

        t_start = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            res = self._post_with_transport_retry("/completion", payload)
        except httpx.TimeoutException as e:
            self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "timeout", sections=sections)
            raise LlmTimeout(str(e)) from e
        except httpx.HTTPError as e:
            self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "error", sections=sections)
            raise LlmError(str(e)) from e

        timings = res.get("timings", {})
        # F5.2 (2026-08-04) — CORREZIONE DI CONTABILITA'. Prima qui c'era
        # `res["tokens_cached"]`, che NON e' il riuso: e' quanti token stanno
        # nella cache adesso, cioe' prompt+1 SEMPRE. Misurato sul server:
        #
        #   scenario     prompt reale   tokens_cached   timings.prompt_n
        #   freddo           721            722              721
        #   identico         721            722                1
        #   append           724            725                4
        #
        # Il numero vero e' `timings.prompt_n`: i token effettivamente
        # processati. Conseguenza del bug: `MAX(prompt - cached, 0)` in
        # `budget_used` valeva SEMPRE 0 — il budget dei task ha contato solo la
        # generazione, mai il prefill. Qui si salva il RIUSO reale, cosi' la
        # sottrazione a valle torna a significare "token davvero pagati".
        reprocessed = int(timings.get("prompt_n", n_prompt) or 0)
        cached = max(n_prompt - reprocessed, 0)
        result = LlmResult(
            text=res.get("content", ""), parsed=None,
            prompt_tokens=n_prompt, cached_tokens=cached,
            gen_tokens=int(timings.get("predicted_n", 0) or 0),
            prefill_ms=float(timings.get("prompt_ms", 0.0) or 0.0),
            gen_ms=float(timings.get("predicted_ms", 0.0) or 0.0),
            raw_timings=timings,
            thinking_tokens=think_tok, thinking_ms=think_ms,
            thinking_text=think_text)

        if res.get("stop_type") == "limit" or res.get("stopped_limit"):
            self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "error", result, sections)
            raise LlmTruncated(
                f"generation hit n_predict={max_tokens} (role={role}); "
                f"raise the role budget or shrink the ask")

        if schema is not None:
            try:
                result.parsed = schema.model_validate_json(result.text)
            except ValidationError as e:
                # Con D3 attivo non deve succedere MAI: bug di piattaforma, non si riprova.
                self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "invalid", result, sections)
                raise LlmInvalidOutput(
                    f"guided decoding produced schema-invalid output for {schema.__name__}: "
                    f"{e.errors()[:3]!r}") from e

        self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "ok", result, sections)
        return result

    def count_tokens(self, text: str) -> int:
        r = self._http.post("/tokenize", json={"content": text})
        r.raise_for_status()
        return len(r.json()["tokens"])

    def health(self) -> bool:
        try:
            return self._http.get("/props", timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def props(self) -> dict:
        r = self._http.get("/props")
        r.raise_for_status()
        return r.json()

    # ── interni ──────────────────────────────────────────────────────────────

    def _post_with_transport_retry(self, path: str, payload: dict) -> dict:
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = self._http.post(path, json=payload)
                r.raise_for_status()
                return r.json()
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
                last = e
                if attempt < 2:
                    time.sleep(2.0)
        raise last  # type: ignore[misc]

    def _log(self, task_id: str | None, role: str, subtask_id: str | None,
             schema: type[BaseModel] | None, t_start: str, n_prompt: int,
             outcome: str, result: LlmResult | None = None,
             sections: dict[str, int] | None = None) -> None:
        if self.store is None or task_id is None:
            return
        self.store.log_llm_call(task_id, LlmCallRow(
            sections=sections,
            role=role, subtask_id=subtask_id,
            schema_name=schema.__name__ if schema else None,
            t_start=t_start, prompt_tokens=n_prompt,
            cached_tokens=result.cached_tokens if result else 0,
            gen_tokens=result.gen_tokens if result else 0,
            prefill_ms=result.prefill_ms if result else 0.0,
            gen_ms=result.gen_ms if result else 0.0,
            thinking_tokens=result.thinking_tokens if result else 0,
            thinking_ms=result.thinking_ms if result else 0.0,
            outcome=outcome))  # type: ignore[arg-type]
