"""Context module - displays context window usage."""

from __future__ import annotations

from statusline.config import ThemeVars
from statusline.input import ContextWindowInfo, InputModel
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class ContextModule(Module):
    """Display the context window usage percentage."""

    name = "context"
    __inputs__ = [ContextWindowInfo]

    def render(self, inputs: dict[str, InputModel], theme_vars: ThemeVars) -> str:
        """Render the context window usage percentage."""
        context_info = inputs.get("context")
        if not context_info:
            return ""

        fmt, context = self.build_context(inputs, theme_vars)
        if not fmt:
            return ""
        return render_template(fmt, context)
