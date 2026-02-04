"""Status line renderer."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table

from statusline.config import Config
from statusline.errors import report_error
from statusline.input import StatuslineInput
from statusline.modules import get_module
from statusline.providers import InputResolver
from statusline.style import get_terminal_width, render_to_ansi


def render_items(
    aliases: list[str], resolver: InputResolver, config: Config
) -> list[tuple[RenderableType, bool]]:
    """Render modules, returning (renderable, expand) pairs.

    Skips modules that return falsy values.
    """
    items = []
    for alias in aliases:
        module_type = config.get_module_type(alias)
        module = get_module(module_type)
        if module is None:
            continue
        inputs = resolver.resolve_for_module(module.__inputs__)
        theme_vars = config.get_theme_vars(alias)
        try:
            rendered = module.render(inputs, theme_vars)
        except Exception as exc:
            report_error(f"rendering module '{alias}'", exc)
        if rendered:
            expand = config.get_module_config(alias).expand
            items.append((rendered, expand))
    return items


def render_row(
    row, resolver: InputResolver, config: Config, width: int
) -> str | None:
    """Render a single row as a grid with per-module columns."""
    left_items = render_items(row.left, resolver, config)
    right_items = render_items(row.right, resolver, config)

    if not left_items and not right_items:
        return None

    has_ratio = (
        any(exp for _, exp in left_items)
        or any(exp for _, exp in right_items)
        or bool(right_items)
    )
    grid = Table.grid(expand=has_ratio)
    cells = []

    for i, (renderable, expand) in enumerate(left_items):
        if i > 0:
            grid.add_column()
            cells.append(config.separator)
        grid.add_column(ratio=1 if expand else None)
        cells.append(renderable)

    if right_items:
        # Spacer between left and right if no left item expands
        if not any(exp for _, exp in left_items):
            grid.add_column(ratio=1)
            cells.append("")
        for i, (renderable, expand) in enumerate(right_items):
            if i > 0:
                grid.add_column()
                cells.append(config.separator)
            grid.add_column(ratio=1 if expand else None, justify="right")
            cells.append(renderable)

    grid.add_row(*cells)
    return render_to_ansi(grid, config.color, width=width)


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
    width = get_terminal_width(config.width)

    lines = []
    for row in layout.rows:
        rendered = render_row(row, resolver, config, width)
        if rendered is not None:
            lines.append(rendered)
    return "\n".join(lines)
