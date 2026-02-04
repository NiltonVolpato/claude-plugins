"""Styling system for statusline."""

from __future__ import annotations

import os
from io import StringIO

from rich.console import Console, RenderableType

CLAUDE_CODE_PADDING = 4


def get_terminal_width(config_width: int | None = None) -> int:
    """Get usable terminal width (minus Claude Code padding).

    Priority: config > COLUMNS env > /dev/tty > 80.
    """
    if config_width is not None:
        return config_width

    columns = os.environ.get("COLUMNS")
    if columns and columns.isdigit():
        return int(columns) - CLAUDE_CODE_PADDING

    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        try:
            width = os.get_terminal_size(fd).columns
        finally:
            os.close(fd)
        return width - CLAUDE_CODE_PADDING
    except OSError:
        pass

    return 80


def render_to_ansi(
    content: RenderableType, use_color: bool, *, width: int = 200
) -> str:
    """Convert Rich renderable to ANSI escape codes.

    Args:
        content: Rich renderable (string with markup, Table, etc.).
        use_color: Whether to include ANSI color codes.
        width: Console width for layout (default 200 to avoid wrapping).

    Returns:
        String with ANSI codes if use_color, plain text otherwise.
    """
    console = Console(
        file=StringIO(),
        force_terminal=True,
        color_system="auto" if use_color else None,
        no_color=not use_color,
        width=width,
    )

    with console.capture() as capture:
        console.print(content, end="", highlight=False, soft_wrap=True)

    return capture.get().rstrip("\n")
