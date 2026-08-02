"""Registro dei comandi. Convenzione: ogni modulo comando si registra
all'import con register(NAME, HELP, run)."""

COMMANDS: dict[str, dict] = {}


def register(name: str, help_text: str, run) -> None:
    COMMANDS[name] = {"help": help_text, "run": run}


def get(name: str) -> dict:
    if name not in COMMANDS:
        raise KeyError(name)
    return COMMANDS[name]
