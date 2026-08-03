"""F3b.1 — http_get: whitelist, schemi, cache-per-task, redirect."""

import httpx

from redgiant.tools.base import Scope
from redgiant.tools.web import CACHE_DIR, http_get


class _Resp:
    def __init__(self, text: str, host: str, status: int = 200):
        self.text = text
        self.status_code = status
        self.url = httpx.URL(f"http://{host}/x")


def test_empty_whitelist_means_no_network(tmp_path):
    scope = Scope(tmp_path, ["*.txt"])
    r = http_get(scope, (), "http://example.com/a")
    assert not r.ok and "domain_not_whitelisted" in r.error


def test_scheme_and_domain_rules(tmp_path):
    scope = Scope(tmp_path, ["*.txt"])
    assert "scheme_not_allowed" in http_get(
        scope, ("example.com",), "ftp://example.com/a").error
    assert "domain_not_whitelisted" in http_get(
        scope, ("example.com",), "http://evil.com/a").error
    # sottodominio del dominio in whitelist: ok; dominio-suffisso truffa: no
    assert "domain_not_whitelisted" in http_get(
        scope, ("example.com",), "http://notexample.com/a").error


def test_fetch_caches_and_rereads_same_copy(tmp_path, monkeypatch):
    scope = Scope(tmp_path, ["*.txt"])
    calls = []

    def fake_get(url, timeout, follow_redirects):
        calls.append(url)
        return _Resp("BODY-1", "127.0.0.1")

    monkeypatch.setattr(httpx, "get", fake_get)
    r1 = http_get(scope, ("127.0.0.1",), "http://127.0.0.1:9/x")
    assert r1.ok and r1.data["body"] == "BODY-1" and not r1.data["cached"]
    # seconda chiamata: LA STESSA copia dal disco, zero rete
    monkeypatch.setattr(httpx, "get",
                        lambda *a, **k: _Resp("BODY-2", "127.0.0.1"))
    r2 = http_get(scope, ("127.0.0.1",), "http://127.0.0.1:9/x")
    assert r2.ok and r2.data["body"] == "BODY-1" and r2.data["cached"]
    assert len(calls) == 1
    assert (tmp_path / CACHE_DIR).is_dir()


def test_redirect_outside_whitelist_refused(tmp_path, monkeypatch):
    scope = Scope(tmp_path, ["*.txt"])
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp("X", "evil.com"))
    r = http_get(scope, ("example.com",), "http://example.com/a")
    assert not r.ok and "redirect_outside_whitelist" in r.error
