"""Status line renderer."""

from __future__ import annotations

from statusline.config import Config
from statusline.input import StatuslineInput
from statusline.modules import get_module
from statusline.style import render_to_ansi


def render_statusline(input: StatuslineInput, config: Config) -> str:
    """Render the status line from the given configuration.

    Args:
        input: The parsed input from Claude Code.
        config: Configuration with modules, theme, colors, etc.

    Returns:
        The rendered status line string with ANSI codes (or plain text if color disabled).
    """
    parts: list[str] = []

    for module_name in config.modules:
        module = get_module(module_name)
        if module is None:
            continue

        # Get theme variables and color for this module
        theme_vars = config.get_theme_vars(module_name)
        color = config.get_module_color(module_name)

        # Module renders with Rich markup
        rendered = module.render(input, theme_vars, color)
        if rendered:
            parts.append(rendered)

    joined = config.separator.join(parts)

    # Convert Rich markup to ANSI (or strip if color disabled)
    return render_to_ansi(joined, config.color)
