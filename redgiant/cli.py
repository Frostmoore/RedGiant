"""CLI di Red Giant.

Stub F0.1: espone solo versione e aiuto. I sottocomandi reali
(run | status | eval | bench) arrivano in F1.9 come da piano.
"""

from __future__ import annotations

import argparse

from redgiant import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rg",
        description=(
            "Red Giant — agentic system for tiny local models. "
            "Subcommands (run, status, eval, bench) arrive in phase F1."
        ),
    )
    parser.add_argument("--version", action="version", version=f"redgiant {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
