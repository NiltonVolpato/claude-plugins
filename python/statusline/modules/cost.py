"""Cost module - displays the session cost."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.config import ThemeVars
from statusline.input import CostInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class CostModule(Module):
    """Display the session cost."""

    name = "cost"
    __inputs__ = [CostInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: ThemeVars) -> str:
        """Render the session cost in USD."""
        cost_info = inputs.get("cost")
        if not cost_info:
            return ""

        fmt = theme_vars.get("format", "{{ total_cost_usd | format_cost }}")
        context = {**cost_info.model_dump(), **theme_vars}
        return render_template(fmt, context)
