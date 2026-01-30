"""Model module - displays the model name."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.input import ModelInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class ModelModule(Module):
    """Display the model name."""

    name = "model"
    __inputs__ = [ModelInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: dict[str, str]) -> str:
        """Render the model display name."""
        model_info = inputs.get("model")
        if not model_info:
            return ""

        fmt = theme_vars.get("format", "{{ display_name }}")
        context = {**model_info.model_dump(), **theme_vars}
        return render_template(fmt, context)
