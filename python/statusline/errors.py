"""Error handling for statusline."""

from __future__ import annotations

import sys


class StatuslineError(Exception):
    """Wrapper indicating the error was already reported to the user."""

    pass


def report_error(context: str, exc: Exception) -> None:
    """Print a friendly error message to stdout and raise StatuslineError."""
    print(
        f"statusline: {context}: {exc}\n"
        f"  Run 'statusline preview' to see the full traceback.",
    )
    raise StatuslineError(str(exc)) from exc
