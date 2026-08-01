"""Tool filesystem: read_file, list_files, write_patch (piano §A7)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from redgiant.tools.base import Scope, ToolResult

_MAX_LINES = 400


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadFileArgs(_Args):
    path: str
    start_line: int = 1
    end_line: int | None = None


class ListFilesArgs(_Args):
    glob: str
    max_results: int = 200


class WritePatchArgs(_Args):
    path: str
    unified_diff: str


def read_file(scope: Scope, path: str, start_line: int = 1,
              end_line: int | None = None) -> ToolResult:
    try:
        real = scope.check_read(path)
    except Exception as e:
        return ToolResult(ok=False, data={}, error=f"scope:{e}")
    if not real.is_file():
        return ToolResult(ok=False, data={}, error="not_found")
    raw = real.read_bytes()
    if b"\x00" in raw[:4096]:
        return ToolResult(ok=False, data={}, error="binary_file")
    lines = raw.decode("utf-8", errors="replace").splitlines()
    total = len(lines)
    lo = max(1, start_line)
    hi = min(end_line or total, total, lo + _MAX_LINES - 1)
    body = "\n".join(f"{i}\t{lines[i - 1]}" for i in range(lo, hi + 1))
    truncated = hi < (end_line or total)
    return ToolResult(
        ok=True,
        data={"content": body, "truncated": truncated, "total_lines": total},
        evidence=[f"read {path}:{lo}-{hi} ({hi - lo + 1} lines of {total})"])


def list_files(scope: Scope, glob: str, max_results: int = 200) -> ToolResult:
    try:
        hits = sorted(p.relative_to(scope.root).as_posix()
                      for p in scope.root.glob(glob) if p.is_file())
    except (ValueError, NotImplementedError) as e:
        return ToolResult(ok=False, data={}, error=f"bad_glob:{e}")
    truncated = len(hits) > max_results
    return ToolResult(ok=True,
                      data={"paths": hits[:max_results], "truncated": truncated,
                            "total": len(hits)},
                      evidence=[f"listed {min(len(hits), max_results)}/{len(hits)} files for '{glob}'"])


def write_patch(scope: Scope, path: str, unified_diff: str) -> ToolResult:
    """Applica un diff unificato. Parser nostro (D19: identico su Windows e Linux).

    Hunk applicati con contesto esatto alla posizione dell'header, poi con
    ricerca tollerante nell'intero file. Scrittura atomica tmp+replace.
    """
    try:
        real = scope.check_write(path)
    except Exception as e:
        return ToolResult(ok=False, data={}, error=f"scope:{e}")

    hunks = _parse_hunks(unified_diff)
    if not hunks:
        return ToolResult(ok=False, data={}, error="no_hunks_in_diff")

    if real.is_file():
        lines = real.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = []

    applied, rejected = 0, []
    for hunk in hunks:
        new_lines = _apply_hunk(lines, hunk)
        if new_lines is None:
            rejected.append({"header": hunk["header"],
                             "expected": [l for tag, l in hunk["ops"] if tag in " -"][:5]})
        else:
            lines = new_lines
            applied += 1

    if applied == 0:
        return ToolResult(ok=False, data={"applied": 0, "rejected": rejected},
                          error="all_hunks_rejected")

    fd, tmp = tempfile.mkstemp(dir=real.parent, suffix=".rgpatch")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        os.replace(tmp, real)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    adds = sum(1 for h in hunks for tag, _ in h["ops"] if tag == "+")
    dels = sum(1 for h in hunks for tag, _ in h["ops"] if tag == "-")
    return ToolResult(
        ok=True,
        data={"applied": applied, "rejected": rejected},
        evidence=[f"patched {path}: {applied}/{len(hunks)} hunks, +{adds}/-{dels} lines"])


def _parse_hunks(diff: str) -> list[dict]:
    hunks: list[dict] = []
    cur: dict | None = None
    for raw in diff.splitlines():
        if raw.startswith("@@"):
            try:
                old_start = int(raw.split("-")[1].split(",")[0].split(" ")[0])
            except (IndexError, ValueError):
                old_start = 1
            cur = {"header": raw, "old_start": old_start, "ops": []}
            hunks.append(cur)
        elif cur is not None and raw[:1] in (" ", "-", "+"):
            cur["ops"].append((raw[0], raw[1:]))
        elif cur is not None and raw == "":
            cur["ops"].append((" ", ""))
    # Trappola F1.11: i modelli piccoli chiudono spesso i hunk con una riga "-"
    # vuota spuria (cancellazione di una riga vuota inesistente) che fa fallire
    # il match dell'intero hunk. Le code vuote non-additive sono cosmetiche: via.
    for h in hunks:
        while h["ops"] and h["ops"][-1][0] in (" ", "-") and _norm(h["ops"][-1][1]) == "":
            h["ops"].pop()
    return hunks


_LINENO_PREFIX = __import__("re").compile(r"^\s*\d+[\t:] ?")


def _norm(line: str) -> str:
    """Matching tollerante (trappola F1.11): read_file mostra 'N<TAB>contenuto' e i
    modelli piccoli copiano il prefisso numerico nel contesto del diff; il confronto
    lo ignora, insieme al whitespace di coda."""
    return _LINENO_PREFIX.sub("", line).rstrip()


def _apply_hunk(lines: list[str], hunk: dict) -> list[str] | None:
    pattern = [_norm(l) for tag, l in hunk["ops"] if tag in " -"]
    replacement_ops = [(tag, _LINENO_PREFIX.sub("", text)) for tag, text in hunk["ops"]]

    def try_at(pos: int) -> list[str] | None:
        if [_norm(l) for l in lines[pos:pos + len(pattern)]] != pattern:
            return None
        out = lines[:pos]
        i = pos
        for tag, text in replacement_ops:
            if tag == " ":
                out.append(lines[i]); i += 1
            elif tag == "-":
                i += 1
            else:
                out.append(text)
        out.extend(lines[i:])
        return out

    if not pattern:  # solo aggiunte (es. file nuovo): inserisci alla posizione dell'header
        pos = min(max(hunk["old_start"] - 1, 0), len(lines))
        return lines[:pos] + [t for tag, t in replacement_ops if tag == "+"] + lines[pos:]

    guess = max(hunk["old_start"] - 1, 0)
    for pos in [guess] + list(range(len(lines))):
        if pos + len(pattern) <= len(lines):
            res = try_at(pos)
            if res is not None:
                return res
    return None
