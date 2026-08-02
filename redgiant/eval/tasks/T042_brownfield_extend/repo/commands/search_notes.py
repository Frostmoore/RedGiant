"""Command: search — note che contengono una parola."""

from registry import register
from storage import find_notes

NAME = "search"
HELP = "search <word>: notes containing word"


def run(notes: list, args: list) -> list:
    return find_notes(notes, args[0])


register(NAME, HELP, run)
