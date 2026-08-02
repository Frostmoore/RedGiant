"""Command: add — crea una nota."""

from registry import register
from storage import add_note

NAME = "add"
HELP = "add <title> <body>: create a note"


def run(notes: list, args: list) -> dict:
    return add_note(notes, args[0], args[1])


register(NAME, HELP, run)
