"""Dispatcher: import commands registra tutto, poi si dispaccia per nome."""

import commands  # noqa: F401  (side effect: registra i comandi)
from registry import get


def dispatch(notes: list, name: str, args: list):
    return get(name)["run"](notes, args)
