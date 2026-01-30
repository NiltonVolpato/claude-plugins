"""Cost module - displays the session cost."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.input import CostInfo
from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class CostModule(Module):
    """Display the session cost."""

    name = "cost"
    __inputs__ = [CostInfo]

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the session cost in USD."""
        fmt = theme_vars.get("format", "{{ total_cost_usd | format_cost }}")
        context = {**input.cost.model_dump(), **theme_vars}
        return render_template(fmt, context)
