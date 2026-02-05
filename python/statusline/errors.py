"""Error handling for statusline."""

from __future__ import annotations

from rich.console import Console


class StatuslineError(Exception):
    """Wrapper indicating the error was already reported to the user."""

    pass


def report_error(context: str, exc: Exception) -> None:
    """Print a friendly error message to stdout and raise StatuslineError."""
    console = Console()
    console.print(
        f"[red]statusline: {context}: {exc}\n"
        f"  Run 'statusline preview' to see the full traceback.[/red]",
    )
    raise StatuslineError(str(exc)) from exc
