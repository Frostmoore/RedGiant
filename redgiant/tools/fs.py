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


class EditFileArgs(_Args):
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False


class WriteFileArgs(_Args):
    path: str
    content: str


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


def edit_file(scope: Scope, path: str, old_string: str, new_string: str,
              replace_all: bool = False) -> ToolResult:
    """Sostituzione esatta di stringa (F1.11): il formato di editing piu' robusto
    per un modello piccolo. old_string deve occorrere esattamente una volta
    (salvo replace_all): l'unicita' e' la garanzia che l'edit finisce dove deve."""
    try:
        real = scope.check_write(path)
    except Exception as e:
        return ToolResult(ok=False, data={}, error=f"scope:{e}")
    if not real.is_file():
        return ToolResult(ok=False, data={}, error="not_found")
    text = real.read_text(encoding="utf-8", errors="replace")
    # F1.11: i modelli copiano SEMPRE i prefissi 'N<TAB>' di read_file, regola o
    # non regola. L'ambiente si adatta: prefissi normalizzati via da entrambe.
    strip = __import__("re").compile(r"^\d+\t", __import__("re").MULTILINE)
    old_string = strip.sub("", old_string)
    new_string = strip.sub("", new_string)
    n = text.count(old_string)
    if n == 0:
        return ToolResult(ok=False, data={"hint": "copy old_string EXACTLY from the file, "
                                                  "without the N<TAB> line-number prefix"},
                          error="not_found_in_file")
    if n > 1 and not replace_all:
        return ToolResult(ok=False, data={"occurrences": n,
                                          "hint": "add surrounding lines to make it unique, "
                                                  "or set replace_all=true"},
                          error="not_unique")
    new_text = text.replace(old_string, new_string)
    fd, tmp = tempfile.mkstemp(dir=real.parent, suffix=".rgedit")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_text)
        os.replace(tmp, real)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return ToolResult(ok=True, data={"replaced": n if replace_all else 1},
                      evidence=[f"edited {path}: replaced {n if replace_all else 1} occurrence(s)"])


def write_file(scope: Scope, path: str, content: str) -> ToolResult:
    """Crea (o sovrascrive) un file di testo con contenuto completo (F1.11):
    il primitivo di creazione piu' robusto per un modello piccolo — edit_file
    non crea file nuovi e i diff puri-additivi sono fragili."""
    try:
        real = scope.check_write(path)
    except Exception as e:
        return ToolResult(ok=False, data={}, error=f"scope:{e}")
    existed = real.is_file()
    real.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=real.parent, suffix=".rgwrite")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        os.replace(tmp, real)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    verb = "overwrote" if existed else "created"
    return ToolResult(ok=True, data={"created": not existed},
                      evidence=[f"{verb} {path} ({len(content.splitlines())} lines)"])


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
