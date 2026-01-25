"""Context module - displays context window usage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class ContextModule(Module):
    """Display the context window usage percentage."""

    name = "context"

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the context window usage percentage."""
        fmt = theme_vars.get("format", "{{ used_percentage | format_percent }}")
        context = {**input.context_window.model_dump(), **theme_vars}
        return render_template(fmt, context)
