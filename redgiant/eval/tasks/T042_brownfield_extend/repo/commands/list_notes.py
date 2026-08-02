"""Command: list — titoli delle note (troncati)."""

from registry import register
from textutil import truncate

NAME = "list"
HELP = "list: show note titles"


def run(notes: list, args: list) -> list:
    return [f"{n['id']}: {truncate(n['title'])}" for n in notes]


register(NAME, HELP, run)
