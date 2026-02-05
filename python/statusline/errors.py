"""Error handling for statusline."""

from __future__ import annotations

from typing import NoReturn

from rich.console import Console


class StatuslineError(Exception):
    """Wrapper indicating the error was already reported to the user."""

    pass


def report_error(context: str, exc: Exception) -> NoReturn:
    """Print a friendly error message to stdout and raise StatuslineError."""
    from statusline.style import render_to_ansi

    message = render_to_ansi(
        f"[red]statusline: {context}: {exc}\n"
        f"Run 'statusline preview' to see the full traceback.[/red]",
        use_color=True,
    )
    print(message)
    raise StatuslineError(str(exc)) from exc
