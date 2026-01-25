"""Model module - displays the model name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class ModelModule(Module):
    """Display the model name."""

    name = "model"

    def render(
        self, input: StatuslineInput, theme_vars: dict[str, str], color: str
    ) -> str:
        """Render the model display name."""
        label = theme_vars.get("label", "")
        value = input.model.display_name or "Unknown"
        space = " " if label else ""
        return f"[{color}]{label}{space}{value}[/{color}]"
