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


def search_code(scope: Scope, rg_bin: str, pattern: str, glob: str | None = None,
                max_results: int = 50) -> ToolResult:
    argv = [rg_bin, "--json", "-e", pattern]
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
    return ToolResult(ok=True,
                      data={"matches": matches, "truncated": len(matches) >= max_results},
                      evidence=[f"ripgrep '{pattern}' -> {len(matches)} matches"])
