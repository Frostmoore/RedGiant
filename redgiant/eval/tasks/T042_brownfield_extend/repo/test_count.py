"""Test FORNITO (rosso finche' il comando 'count' non esiste)."""

import commands  # noqa: F401
from app import dispatch
from registry import get


def _seed():
    notes = []
    dispatch(notes, "add", ["A", "a"])
    dispatch(notes, "add", ["B", "b"])
    return notes


def test_count_registered_with_convention():
    cmd = get("count")
    assert cmd["help"].startswith("count")


def test_count_returns_number_of_notes():
    notes = _seed()
    assert dispatch(notes, "count", []) == 2
    assert dispatch([], "count", []) == 0


def test_count_module_follows_module_convention():
    from commands import count
    assert count.NAME == "count" and callable(count.run)
