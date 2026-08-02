"""Command: delete — elimina una nota per id."""

from registry import register
from storage import delete_note

NAME = "delete"
HELP = "delete <id>: remove a note"


def run(notes: list, args: list) -> bool:
    return delete_note(notes, int(args[0]))


register(NAME, HELP, run)
