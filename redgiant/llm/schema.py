"""Unico punto di conversione Pydantic → JSON Schema per il guided decoding (D3/D4)."""

from __future__ import annotations

from pydantic import BaseModel


def to_llama_schema(model: type[BaseModel]) -> dict:
    """JSON Schema per il campo `json_schema` di llama-server.

    model_json_schema() con $defs annidati è digerito correttamente dal
    convertitore grammaticale di llama.cpp (verificato in F0.3 su ProbePlan).
    """
    return model.model_json_schema()
