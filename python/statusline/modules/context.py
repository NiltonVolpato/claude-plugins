"""Context module - displays context window usage."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.config import ThemeVars
from statusline.input import ContextWindowInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class ContextModule(Module):
    """Display the context window usage percentage."""

    name = "context"
    __inputs__ = [ContextWindowInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: ThemeVars) -> str:
        """Render the context window usage percentage."""
        context_info = inputs.get("contextwindow")
        if not context_info:
            return ""

        fmt = theme_vars.get("format", "{{ used_percentage | format_percent }}")
        assert isinstance(fmt, str)
        context = {**context_info.model_dump(), **theme_vars}
        return render_template(fmt, context)
