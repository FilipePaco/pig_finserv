"""Command-line entry point.

Commands are added incrementally as their service contracts are implemented.
"""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="Pig FinServ complaint triage and insights.")


@app.callback()
def main() -> None:
    """Run the Pig FinServ command-line application."""


@app.command()
def version() -> None:
    """Print the installed application version."""

    from pig_finserv import __version__

    typer.echo(__version__)
