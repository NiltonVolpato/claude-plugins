"""Context module - displays context window usage."""

from __future__ import annotations

from statusline.input import ContextWindowInfo
from statusline.modules import Module, register


@register
class ContextModule(Module):
    """Display the context window usage percentage."""

    name = "context"
    __inputs__ = [ContextWindowInfo]
