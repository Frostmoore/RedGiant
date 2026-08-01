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
                 cache_prompt: bool = True) -> LlmResult:
        prompt = parts.render()
        n_prompt = self.count_tokens(prompt)
        if n_prompt + max_tokens > self.cfg.ctx_size:
            raise ContextOverflow(n_prompt, self.cfg.ctx_size,
                                  parts.section_tokens(self.count_tokens))

        payload: dict = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "cache_prompt": cache_prompt,
        }
        if schema is not None:
            payload["json_schema"] = to_llama_schema(schema)

        t_start = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            res = self._post_with_transport_retry("/completion", payload)
        except httpx.TimeoutException as e:
            self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "timeout")
            raise LlmTimeout(str(e)) from e
        except httpx.HTTPError as e:
            self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "error")
            raise LlmError(str(e)) from e

        timings = res.get("timings", {})
        cached = int(res.get("tokens_cached", 0) or 0)
        result = LlmResult(
            text=res.get("content", ""), parsed=None,
            prompt_tokens=n_prompt, cached_tokens=cached,
            gen_tokens=int(timings.get("predicted_n", 0) or 0),
            prefill_ms=float(timings.get("prompt_ms", 0.0) or 0.0),
            gen_ms=float(timings.get("predicted_ms", 0.0) or 0.0),
            raw_timings=timings)

        if res.get("stop_type") == "limit" or res.get("stopped_limit"):
            self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "error", result)
            raise LlmTruncated(
                f"generation hit n_predict={max_tokens} (role={role}); "
                f"raise the role budget or shrink the ask")

        if schema is not None:
            try:
                result.parsed = schema.model_validate_json(result.text)
            except ValidationError as e:
                # Con D3 attivo non deve succedere MAI: bug di piattaforma, non si riprova.
                self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "invalid", result)
                raise LlmInvalidOutput(
                    f"guided decoding produced schema-invalid output for {schema.__name__}: "
                    f"{e.errors()[:3]!r}") from e

        self._log(task_id, role, subtask_id, schema, t_start, n_prompt, "ok", result)
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
             outcome: str, result: LlmResult | None = None) -> None:
        if self.store is None or task_id is None:
            return
        self.store.log_llm_call(task_id, LlmCallRow(
            role=role, subtask_id=subtask_id,
            schema_name=schema.__name__ if schema else None,
            t_start=t_start, prompt_tokens=n_prompt,
            cached_tokens=result.cached_tokens if result else 0,
            gen_tokens=result.gen_tokens if result else 0,
            prefill_ms=result.prefill_ms if result else 0.0,
            gen_ms=result.gen_ms if result else 0.0,
            outcome=outcome))  # type: ignore[arg-type]
