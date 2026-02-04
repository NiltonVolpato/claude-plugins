"""Status line renderer."""

from __future__ import annotations

from rich.table import Table

from statusline.config import Config
from statusline.input import StatuslineInput
from statusline.modules import get_module
from statusline.providers import InputResolver
from statusline.style import get_terminal_width, render_to_ansi


def render_module_list(
    aliases: list[str], resolver: InputResolver, config: Config
) -> str:
    """Render a list of module aliases into a Rich markup string.

    Returns joined Rich markup (not yet ANSI-converted).
    """
    parts: list[str] = []

    for alias in aliases:
        module_type = config.get_module_type(alias)
        module = get_module(module_type)
        if module is None:
            continue

        inputs = resolver.resolve_for_module(module.__inputs__)
        theme_vars = config.get_theme_vars(alias)

        rendered = module.render(inputs, theme_vars)
        if rendered:
            parts.append(rendered)

    return config.separator.join(parts)


def render_statusline(input: StatuslineInput, config: Config) -> str:
    """Render the status line from the given configuration.

    Args:
        input: The parsed input from Claude Code.
        config: Configuration with modules, theme, colors, etc.

    Returns:
        The rendered status line string with ANSI codes (or plain text if color disabled).
    """
    resolver = InputResolver(input)
    layout = config.layout
    has_right = any(row.right for row in layout.rows)

    if not has_right:
        # Simple path: all left-only rows, join with \n
        lines = []
        for row in layout.rows:
            markup = render_module_list(row.left, resolver, config)
            if markup:
                lines.append(markup)
        joined = "\n".join(lines)
        return render_to_ansi(joined, config.color)

    # Grid path: left/right alignment
    width = get_terminal_width(config.width)
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    for row in layout.rows:
        left = render_module_list(row.left, resolver, config)
        right = render_module_list(row.right, resolver, config)
        grid.add_row(left, right)
    return render_to_ansi(grid, config.color, width=width)
