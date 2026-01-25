"""Cost module - displays the session cost."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class CostModule(Module):
    """Display the session cost."""

    name = "cost"

    def render(
        self, input: StatuslineInput, theme_vars: dict[str, str], color: str
    ) -> str:
        """Render the session cost in USD."""
        label = theme_vars.get("label", "")
        cost = input.cost.total_cost_usd
        if cost < 0.01:
            value = f"${cost:.4f}"
        else:
            value = f"${cost:.2f}"
        space = " " if label else ""
        return f"[{color}]{label}{space}{value}[/{color}]"
