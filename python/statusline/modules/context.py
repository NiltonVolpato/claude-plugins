"""Context module - displays context window usage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class ContextModule(Module):
    """Display the context window usage percentage."""

    name = "context"

    def render(
        self, input: StatuslineInput, theme_vars: dict[str, str], color: str
    ) -> str:
        """Render the context window usage percentage."""
        label = theme_vars.get("label", "")
        percentage = input.context_window.used_percentage
        value = f"{percentage:.0f}%"
        space = " " if label else ""
        return f"[{color}]{label}{space}{value}[/{color}]"
