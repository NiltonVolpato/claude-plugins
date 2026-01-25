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

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the model display name."""
        fmt = theme_vars.get("format", "{display_name}")
        values = {**input.model.model_dump(), **theme_vars}
        return fmt.format(**values)
