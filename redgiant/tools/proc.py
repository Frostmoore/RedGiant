"""run_tests / git_status / git_diff (piano §A7).

run_tests esegue SOLO comandi registrati per cmd_id nella whitelist del task —
mai stringhe libere dal modello — e l'eseguibile deve appartenere a
security.shell_whitelist. Evidenza: exit code + tail dell'output (e' li' che
pytest riassume).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from pydantic import BaseModel, ConfigDict

from redgiant.tools.base import Scope, ToolResult

_TAIL = 50


class RunTestsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cmd_id: str


class GitStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitDiffArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = "HEAD"


def _run(argv: list[str], cwd, timeout: float) -> tuple[int, str]:
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")
    out = (proc.stdout + "\n" + proc.stderr).strip()
    tail = "\n".join(out.splitlines()[-_TAIL:])
    return proc.returncode, tail


def run_tests(scope: Scope, test_commands: dict[str, list[str]],
              shell_whitelist: tuple[str, ...], cmd_id: str,
              timeout_s: float = 300.0) -> ToolResult:
    argv = test_commands.get(cmd_id)
    if argv is None:
        return ToolResult(ok=False, data={"known": sorted(test_commands)},
                          error="unknown_cmd_id")
    exe = argv[0]
    if exe not in shell_whitelist:
        return ToolResult(ok=False, data={}, error=f"executable_not_whitelisted:{exe}")
    # Trappola disinnescata (F1.11): senza venv attivo la PATH del subprocess non
    # contiene pytest/python del venv. python/pytest si risolvono SEMPRE
    # sull'interprete che esegue Red Giant: l'ambiente dei tool == quello dell'harness.
    if exe == "pytest":
        argv = [sys.executable, "-m", "pytest", *argv[1:]]
    elif exe == "python":
        argv = [sys.executable, *argv[1:]]
    elif shutil.which(exe) is None:
        return ToolResult(ok=False, data={}, error=f"executable_not_found:{exe}")
    try:
        code, tail = _run(argv, scope.root, timeout_s)
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, data={}, error="timeout",
                          evidence=[f"run_tests {cmd_id}: TIMEOUT after {timeout_s}s"])
    except FileNotFoundError:
        return ToolResult(ok=False, data={}, error=f"executable_not_found:{exe}")
    return ToolResult(ok=(code == 0),
                      data={"exit_code": code, "output_tail": tail},
                      evidence=[f"run_tests {cmd_id}: exit={code}"],
                      error=None if code == 0 else "tests_failed")


def git_status(scope: Scope) -> ToolResult:
    code, tail = _run(["git", "status", "--porcelain"], scope.root, 30.0)
    if code != 0:
        return ToolResult(ok=False, data={"detail": tail}, error="git_error")
    return ToolResult(ok=True, data={"status": tail[:4000]},
                      evidence=[f"git status: {len(tail.splitlines())} changed paths"])


def git_diff(scope: Scope, ref: str = "HEAD") -> ToolResult:
    code, tail = _run(["git", "diff", ref], scope.root, 30.0)
    if code != 0:
        return ToolResult(ok=False, data={"detail": tail}, error="git_error")
    lines = tail.splitlines()[:400]
    return ToolResult(ok=True, data={"diff": "\n".join(lines),
                                     "truncated": len(tail.splitlines()) > 400},
                      evidence=[f"git diff {ref}: {len(lines)} lines shown"])
