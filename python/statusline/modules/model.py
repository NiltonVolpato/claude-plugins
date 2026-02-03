"""Model module - displays the model name."""

from __future__ import annotations

from statusline.config import ThemeVars
from statusline.input import InputModel, ModelInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class ModelModule(Module):
    """Display the model name."""

    name = "model"
    __inputs__ = [ModelInfo]

    def render(self, inputs: dict[str, InputModel], theme_vars: ThemeVars) -> str:
        """Render the model display name."""
        fmt, context = self.build_context(inputs, theme_vars)
        if not fmt:
            return ""
        return render_template(fmt, context)
