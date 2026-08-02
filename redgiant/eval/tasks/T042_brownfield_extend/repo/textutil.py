"""Utility di testo condivise dai comandi."""


def truncate(text: str, width: int = 40) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."
