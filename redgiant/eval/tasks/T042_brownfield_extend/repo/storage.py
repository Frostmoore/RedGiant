"""Storage in-memory delle note: lista di dict {id, title, body}."""


def add_note(notes: list, title: str, body: str) -> dict:
    note = {"id": (max((n["id"] for n in notes), default=0) + 1),
            "title": title, "body": body}
    notes.append(note)
    return note


def delete_note(notes: list, note_id: int) -> bool:
    for i, n in enumerate(notes):
        if n["id"] == note_id:
            notes.pop(i)
            return True
    return False


def find_notes(notes: list, word: str) -> list:
    w = word.lower()
    return [n for n in notes
            if w in n["title"].lower() or w in n["body"].lower()]
