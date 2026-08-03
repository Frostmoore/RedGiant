"""HTTP minimale (F3b.1, anticipo di F7.2): GET con whitelist di domini,
timeout, size-cap e CACHE su disco per task.

Regole cablate:
- whitelist da config (`security.http_allowed_domains`, default vuota = niente
  rete): un dominio non in lista e' un errore esplicito, mai un tentativo;
- solo http(s), niente redirect fuori whitelist (il redirect si segue ma la
  destinazione viene ri-verificata);
- la CACHE e' il punto di verita': la verifica rilegge LA copia che il modello
  ha visto (determinismo D6), mai la rete due volte. Vive in
  `.rg_http_cache/` dentro la workdir, esclusa da listati e ledger.
"""

from __future__ import annotations

import hashlib

from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from redgiant.tools.base import Scope, ToolResult

_MAX_BYTES = 200_000
_TIMEOUT_S = 15.0
CACHE_DIR = ".rg_http_cache"


class HttpGetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=500)


def _host_allowed(host: str, allowed: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in allowed)


def http_get(scope: Scope, allowed_domains: tuple[str, ...],
             url: str) -> ToolResult:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return ToolResult(ok=False, data={},
                          error=f"scheme_not_allowed:{p.scheme or '(none)'}")
    host = p.hostname or ""
    if not allowed_domains or not _host_allowed(host, allowed_domains):
        return ToolResult(ok=False,
                          data={"allowed_domains": list(allowed_domains)},
                          error=f"domain_not_whitelisted:{host}")

    cache = scope.root / CACHE_DIR
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    body_file = cache / f"{key}.body"
    if body_file.is_file():
        body = body_file.read_text(encoding="utf-8", errors="replace")
        return ToolResult(ok=True,
                          data={"url": url, "body": body, "cached": True},
                          evidence=[f"GET {url} (cache) -> {len(body)} chars"])

    try:
        r = httpx.get(url, timeout=_TIMEOUT_S, follow_redirects=True)
    except httpx.HTTPError as e:
        return ToolResult(ok=False, data={"url": url},
                          error=f"http_error:{type(e).__name__}")
    final_host = r.url.host or ""
    if not _host_allowed(final_host, allowed_domains):
        return ToolResult(ok=False, data={"redirected_to": str(r.url)},
                          error=f"redirect_outside_whitelist:{final_host}")
    body = r.text[:_MAX_BYTES]
    cache.mkdir(exist_ok=True)
    body_file.write_text(body, encoding="utf-8")
    return ToolResult(
        ok=True,
        data={"url": url, "status": r.status_code, "body": body,
              "cached": False, "truncated": len(r.text) > _MAX_BYTES},
        evidence=[f"GET {url} -> {r.status_code}, {len(body)} chars"])
