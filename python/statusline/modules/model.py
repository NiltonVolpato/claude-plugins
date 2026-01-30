"""Model module - displays the model name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.input import ModelInfo
from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class ModelModule(Module):
    """Display the model name."""

    name = "model"
    __inputs__ = [ModelInfo]

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the model display name."""
        fmt = theme_vars.get("format", "{{ display_name }}")
        context = {**input.model.model_dump(), **theme_vars}
        return render_template(fmt, context)
