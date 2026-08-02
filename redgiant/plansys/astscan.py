"""Estrazione firme via AST (PS1.1).

Nato in scripts/check_reference.py (F0.7); spostato qui SENZA cambiare
comportamento perche' il Ledger Builder ha bisogno delle stesse firme reali.
Lo script ora importa da questo modulo (un solo estrattore in tutto il repo:
se divergessero, atlante e ledger racconterebbero due verita' diverse).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def normalize_signature(sig: str) -> str:
    sig = sig.strip().rstrip(":")
    sig = sig.replace("'", "").replace('"', "")        # annotazioni stringa == nude
    sig = re.sub(r"\s+", " ", sig)
    sig = re.sub(r"\s*([(),:\[\]|=])\s*", r"\1", sig)  # spazi attorno alla punteggiatura
    sig = sig.replace(",", ", ").replace(":", ": ").replace("|", " | ")
    sig = re.sub(r"\(\s+", "(", sig).replace(" )", ")")
    sig = re.sub(r"\s+", " ", sig)
    sig = sig.replace("->", " -> ")
    return re.sub(r"\s+", " ", sig).strip()


def _func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return normalize_signature(f"{prefix} {node.name}({args}){ret}")


def _class_signature(node: ast.ClassDef) -> str:
    # le basi non fanno parte del contratto documentale (rumore: _Strict, BaseModel...)
    return f"class {node.name}"


def file_signatures(path: Path) -> list[str]:
    """Firme di UN file, in ordine di apparizione. AST rotto -> lista vuota
    (il chiamante decide come registrarlo; qui niente eccezioni)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                         filename=str(path))
    except SyntaxError:
        return []
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(_func_signature(node))
        elif isinstance(node, ast.ClassDef):
            out.append(_class_signature(node))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(f"{node.name}.{_func_signature(sub)}")
    return out


def extract_signatures(pkg_dir: Path) -> dict[str, list[str]]:
    """Firme reali: {nome_qualificato: [firma_normalizzata]} per tutto il pacchetto.
    Esclusi i repo-fixture dei task sintetici (eval/tasks/*/repo): sono cavie."""
    out: dict[str, list[str]] = {}
    for py in sorted(pkg_dir.rglob("*.py")):
        rel = py.relative_to(pkg_dir).as_posix()
        if rel.startswith("eval/tasks/"):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(node.name, []).append(_func_signature(node))
            elif isinstance(node, ast.ClassDef):
                out.setdefault(node.name, []).append(_class_signature(node))
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out.setdefault(f"{node.name}.{sub.name}", []).append(
                            _func_signature(sub))
    return out
