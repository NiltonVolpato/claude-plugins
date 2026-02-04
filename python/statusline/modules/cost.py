"""Cost module - displays the session cost."""

from __future__ import annotations

from statusline.config import ThemeVars
from statusline.input import CostInfo, InputModel
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class CostModule(Module):
    """Display the session cost."""

    name = "cost"
    __inputs__ = [CostInfo]

    def render(self, inputs: dict[str, InputModel], theme_vars: ThemeVars) -> str:
        """Render the session cost in USD."""
        fmt, context = self.build_context(inputs, theme_vars)
        return render_template(fmt, context)
