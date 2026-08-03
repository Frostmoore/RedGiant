"""Calcolatrice deterministica (F3b/ladder L5: il modello trova 5 fatti su 5
in 90 documenti e poi sbaglia l'addizione di 100 — l'aritmetica si offloada
alla macchina, F1: adatta l'ambiente, non combattere il modello).

Valutazione AST-only: numeri, + - * / // % ** unario, parentesi. Nessun nome,
nessuna chiamata, nessun attributo — non e' un eval travestito.
"""

from __future__ import annotations

import ast

from pydantic import BaseModel, ConfigDict, Field

from redgiant.tools.base import ToolResult

_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b}
_MAX_POW = 1000


class CalcArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str = Field(max_length=300)


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd,
                                                             ast.USub)):
        v = _eval(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(b) > _MAX_POW):
            raise ValueError("exponent too large")
        return _BIN[type(node.op)](a, b)
    raise ValueError(f"not allowed: {type(node).__name__}")


def calc(expression: str) -> ToolResult:
    try:
        value = _eval(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return ToolResult(ok=False, data={"expression": expression},
                          error="division_by_zero")
    except (SyntaxError, ValueError) as e:
        return ToolResult(ok=False, data={"expression": expression,
                                          "hint": "only numbers and "
                                                  "+ - * / // % ** ()"},
                          error=f"bad_expression:{e}")
    out = int(value) if isinstance(value, float) and value.is_integer() else value
    return ToolResult(ok=True, data={"expression": expression, "result": out},
                      evidence=[f"{expression} = {out}"])
