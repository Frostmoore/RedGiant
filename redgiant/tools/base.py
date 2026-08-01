"""Tool layer, fondamenta (piano F1.4, §A7): Scope, ToolSpec, ToolResult.

I tool sono le mani del sistema e la fonte delle EVIDENZE (D10): ogni risultato
porta fatti osservabili. La sicurezza (Scope) sta qui e non a valle: il primo
Worker che scrive fuori scope non deve poter esistere nemmeno in sviluppo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel


class ScopeError(Exception): ...


class Scope:
    """Sandbox dei path: tutto relativo a root, symlink che escono = negati."""

    def __init__(self, root: Path, writable_globs: list[str]) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ScopeError(f"scope root does not exist: {root}")
        self.writable_globs = list(writable_globs)

    def check_read(self, p: str) -> Path:
        cand = (self.root / p) if not Path(p).is_absolute() else Path(p)
        real = cand.resolve()
        if not real.is_relative_to(self.root):
            raise ScopeError(f"path escapes scope: {p}")
        return real

    def check_write(self, p: str) -> Path:
        real = self.check_read(p)
        rel = real.relative_to(self.root).as_posix()
        # fnmatch su path posix (py3.12-compatibile); '**/*.py' e' trattato come
        # 'ovunque': fnmatch non conosce '**', quindi si matcha anche il basename
        if not any(fnmatch(rel, g) or fnmatch(Path(rel).name, Path(g).name)
                   for g in self.writable_globs):
            raise ScopeError(f"path not in writable scope: {rel} (globs={self.writable_globs})")
        return real


@dataclass
class ToolResult:
    ok: bool
    data: dict
    evidence: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: Literal["low", "medium", "high"]
    reversible: bool
    requires_approval: bool
    timeout_s: float
    input_model: type[BaseModel]
    handler: Callable[..., ToolResult]
