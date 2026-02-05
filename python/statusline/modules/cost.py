"""Cost module - displays the session cost."""

from __future__ import annotations

from statusline.input import CostInfo
from statusline.modules import Module, register


@register
class CostModule(Module):
    """Display the session cost."""

    name = "cost"
    __inputs__ = [CostInfo]
