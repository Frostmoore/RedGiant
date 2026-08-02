import pytest

import commands  # noqa: F401
from registry import COMMANDS, get


def test_known_commands_registered():
    for name in ("add", "list", "delete", "search"):
        assert name in COMMANDS
        assert COMMANDS[name]["help"].startswith(name)


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        get("ghost")
