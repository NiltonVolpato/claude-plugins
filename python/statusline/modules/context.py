"""Context module - displays context window usage."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class ContextModule(Module):
    """Display the context window usage percentage."""

    name = "context"

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the context window usage percentage."""
        fmt = theme_vars.get("format", "{percent}")
        percent = f"{input.context_window.used_percentage:.0f}%"
        values = {**asdict(input.context_window), "percent": percent, **theme_vars}
        return fmt.format(**values)
