"""Status line renderer."""

from __future__ import annotations

from statusline.config import Config
from statusline.input import StatuslineInput
from statusline.modules import get_module, get_module_class
from statusline.providers import InputResolver
from statusline.style import render_to_ansi


def render_statusline(input: StatuslineInput, config: Config) -> str:
    """Render the status line from the given configuration.

    Args:
        input: The parsed input from Claude Code.
        config: Configuration with modules, theme, colors, etc.

    Returns:
        The rendered status line string with ANSI codes (or plain text if color disabled).
    """
    # Create input resolver - computes each input type once and caches
    resolver = InputResolver(input)

    parts: list[str] = []

    for module_name in config.modules:
        module = get_module(module_name)
        if module is None:
            continue

        # Get the module class to access __inputs__
        module_cls = get_module_class(module_name)
        if module_cls is None:
            continue

        # Resolve inputs for this module (uses cache)
        inputs = resolver.resolve_for_module(module_cls.__inputs__)

        # Get theme variables (includes format string)
        theme_vars = config.get_theme_vars(module_name)

        # Module renders with Rich markup
        rendered = module.render(inputs, theme_vars)
        if rendered:
            parts.append(rendered)

    joined = config.separator.join(parts)

    # Convert Rich markup to ANSI (or strip if color disabled)
    return render_to_ansi(joined, config.color)
