"""Concours Euro-Information 2026 « IA responsable » : du glouton au solveur exact."""

from .instance import Instance, load

__all__ = ["Instance", "load", "main"]


def main() -> None:
    """Point d'entrée `ia-responsable` (voir pyproject.toml)."""
    import sys

    from .cli import main as cli_main

    sys.exit(cli_main())
