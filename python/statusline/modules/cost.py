"""Cost module - displays the session cost."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class CostModule(Module):
    """Display the session cost."""

    name = "cost"

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the session cost in USD."""
        fmt = theme_vars.get("format", "{cost}")
        usd = input.cost.total_cost_usd
        if usd < 0.01:
            cost = f"${usd:.4f}"
        else:
            cost = f"${usd:.2f}"
        values = {**asdict(input.cost), "cost": cost, **theme_vars}
        return fmt.format(**values)
