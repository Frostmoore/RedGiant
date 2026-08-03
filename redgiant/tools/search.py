"""search_code via ripgrep (piano §A7) — niente shell: lista argv, mai stringhe.

Trappola disinnescata (F1.4): il nostro entry point CLI si chiama `rg` come
ripgrep; nel venv attivo `rg` risolverebbe al NOSTRO stub. La risoluzione del
binario salta quindi le directory Scripts/bin di ambienti virtuali.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from redgiant.tools.base import Scope, ToolResult


class SearchCodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern: str
    glob: str | None = None
    max_results: int = 50


def _smart_case(pattern: str) -> bool:
    """Smart-case (convenzione rg/vim): pattern tutto minuscolo => ricerca
    insensibile. Ladder L7: il modello cercava 'service mensa' e la riga era
    'Service **mensa**' — zero risultati per una maiuscola."""
    return pattern.islower() or not any(c.isupper() for c in pattern)


def _no_match_hint(pattern: str) -> str:
    """Un fallimento di ricerca deve essere ATTUABILE (F2): il modello che
    riceve 'zero risultati' e nient'altro ripete la stessa query all'infinito
    (misurato: 5 volte identiche sulla ladder)."""
    words = [w for w in pattern.replace("|", " ").split() if w]
    if len(words) > 1:
        return (f"no matches: the pattern has {len(words)} words and matches "
                f"them ADJACENT. Search ONE distinctive word instead, e.g. "
                f"'{max(words, key=len)}'")
    return ("no matches: try a shorter or more distinctive substring, or a "
            "different spelling (search is smart-case: an all-lowercase "
            "pattern matches any case)")


def resolve_ripgrep(configured: str) -> str:
    """Risolve il binario ripgrep evitando l'omonimo entry point nel venv."""
    p = Path(configured)
    if p.is_absolute() and p.is_file():
        return str(p)
    venv_dirs = {str(Path(sys.prefix) / "Scripts"), str(Path(sys.prefix) / "bin")}
    path_entries = [d for d in os.environ.get("PATH", "").split(os.pathsep)
                    if d and d not in venv_dirs]
    found = shutil.which(configured, path=os.pathsep.join(path_entries))
    if not found:
        raise FileNotFoundError(
            f"ripgrep ('{configured}') not found on PATH outside the venv; "
            f"set paths.ripgrep to an absolute path in config")
    return found


def search_python(scope: Scope, pattern: str, glob: str | None = None,
                  max_results: int = 50) -> ToolResult:
    """Fallback puro Python quando ripgrep non e' installato (trappola F1.11:
    sul PC di sviluppo ripgrep puo' mancare). Piu' lento ma identico nel contratto."""
    import re as _re
    from fnmatch import fnmatch as _fn
    try:
        rx = _re.compile(pattern,
                         _re.IGNORECASE if _smart_case(pattern) else 0)
    except _re.error as e:
        return ToolResult(ok=False, data={"detail": str(e)}, error="bad_pattern")
    matches = []
    for p in sorted(scope.root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(scope.root).as_posix()
        if glob and not (_fn(rel, glob) or _fn(p.name, glob)):
            continue
        raw = p.read_bytes()
        if b"\x00" in raw[:4096]:
            continue
        for i, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            if rx.search(line):
                matches.append({"path": rel, "line": i, "text": line[:300]})
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break
    data = {"matches": matches, "truncated": len(matches) >= max_results}
    if not matches:
        data["hint"] = _no_match_hint(pattern)
    return ToolResult(ok=True, data=data,
                      evidence=[f"python-search '{pattern}' -> {len(matches)} matches"])


def search_code(scope: Scope, rg_bin: str, pattern: str, glob: str | None = None,
                max_results: int = 50) -> ToolResult:
    argv = [rg_bin, "--json", "-e", pattern]
    if _smart_case(pattern):
        argv.insert(1, "-i")
    if glob:
        argv += ["--glob", glob]
    argv.append(str(scope.root))
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, data={}, error="timeout")
    if proc.returncode == 2:  # 0=match, 1=no match, 2=errore (es. regex invalida)
        return ToolResult(ok=False, data={"detail": proc.stderr[:400]}, error="bad_pattern")

    matches = []
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "match":
            continue
        d = obj["data"]
        try:
            rel = Path(d["path"]["text"]).resolve().relative_to(scope.root).as_posix()
        except ValueError:
            rel = d["path"]["text"]
        matches.append({"path": rel,
                        "line": d["line_number"],
                        "text": d["lines"]["text"].rstrip("\n")[:300]})
        if len(matches) >= max_results:
            break
    data = {"matches": matches, "truncated": len(matches) >= max_results}
    if not matches:
        data["hint"] = _no_match_hint(pattern)
    return ToolResult(ok=True, data=data,
                      evidence=[f"ripgrep '{pattern}' -> {len(matches)} matches"])
