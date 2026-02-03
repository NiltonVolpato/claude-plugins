"""Styling system for statusline."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def render_to_ansi(markup: str, use_color: bool) -> str:
    """Convert Rich markup to ANSI escape codes.

    Args:
        markup: Rich markup string (e.g., "[cyan]text[/cyan]").
        use_color: Whether to include ANSI color codes.

    Returns:
        String with ANSI codes if use_color, plain text otherwise.
    """
    console = Console(
        file=StringIO(),
        force_terminal=True,
        color_system="auto" if use_color else None,
        no_color=not use_color,
    )

    with console.capture() as capture:
        console.print(markup, end="", highlight=False, soft_wrap=True)

    return capture.get()
