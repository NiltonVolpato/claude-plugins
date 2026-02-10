"""Context bar module - displays context usage as an expandable progress bar."""

from __future__ import annotations

from rich.table import Table

from statusline.config import ContextBarConfig, ModuleConfigUnion
from statusline.input import ContextWindowInfo, InputModel
from statusline.modules import Module, register
from statusline.modules.bar import ExpandableBar
from statusline.templates import render_template

PROGRESS_BAR_PLACEHOLDER = "\x00PROGRESS_BAR\x00"


@register
class ContextBarModule(Module):
    """Context window usage as a progress bar."""

    name = "context_bar"
    __inputs__ = [ContextWindowInfo]

    def render(
        self,
        inputs: dict[str, InputModel],
        config: ModuleConfigUnion,
        **kwargs,
    ):
        expand = kwargs.get("expand", False)
        context = inputs.get("context")
        if context is None:
            return ""

        # Type narrow to ContextBarConfig
        if not isinstance(config, ContextBarConfig):
            return ""

        # Build context manually - we need bar as a dict for Jinja2's ** unpacking
        fmt = config.format
        bar_dict = config.bar.model_dump()
        ctx: dict = {key: val for key, val in inputs.items()}
        ctx["theme"] = {"format": fmt, "bar": bar_dict}

        # progress_bar() callable — accepts overrides, returns placeholder
        overrides: dict = {}

        def progress_bar_fn(**kwargs):
            overrides.update(kwargs)
            return PROGRESS_BAR_PLACEHOLDER

        ctx["progress_bar"] = progress_bar_fn
        rendered = render_template(fmt, ctx)

        if PROGRESS_BAR_PLACEHOLDER not in rendered:
            return rendered  # No progress_bar() call, return as plain string

        before, after = rendered.split(PROGRESS_BAR_PLACEHOLDER, 1)
        merged_opts = {**bar_dict, **overrides}
        bar = ExpandableBar(context.used_percentage, merged_opts, expand=expand)

        # Compose grid: [before?] [bar (ratio=1)] [after?]
        grid = Table.grid(expand=expand)
        parts = []
        if before:
            grid.add_column()
            parts.append(before)
        grid.add_column(ratio=1)
        parts.append(bar)
        if after:
            grid.add_column()
            parts.append(after)
        grid.add_row(*parts)
        return grid
