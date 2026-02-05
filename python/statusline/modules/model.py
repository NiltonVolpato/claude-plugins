"""Model module - displays the model name."""

from __future__ import annotations

from statusline.input import ModelInfo
from statusline.modules import Module, register


@register
class ModelModule(Module):
    """Display the model name."""

    name = "model"
    __inputs__ = [ModelInfo]
