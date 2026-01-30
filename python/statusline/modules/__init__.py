"""Module system for statusline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


class Module(ABC):
    """Base class for statusline modules."""

    name: str = ""
    __inputs__: list[type[BaseModel]] = []
    """List of Pydantic models whose fields are available as template variables."""

    @abstractmethod
    def render(self, inputs: dict[str, BaseModel], theme_vars: dict[str, str]) -> str:
        """Render the module output with Rich markup.

        Args:
            inputs: Dict mapping input names to their Pydantic model instances.
                    Keys are lowercase names without 'Info' suffix (e.g., 'git', 'model').
            theme_vars: Theme variables including 'format' and 'label'.

        Returns:
            Rich-formatted string (e.g., "[cyan] Opus 4.5[/cyan]").
        """
        ...

    @classmethod
    def get_template_vars(cls) -> dict[str, str]:
        """Get available template variables with their descriptions.

        Returns:
            Dict mapping variable names to their descriptions (from field docstrings).
        """
        result: dict[str, str] = {}
        for model_cls in cls.__inputs__:
            for field_name, field_info in model_cls.model_fields.items():
                desc = field_info.description or ""
                result[field_name] = desc
        # Always include 'label' from theme
        result["label"] = "Theme-specific label/icon prefix"
        return result


# Module registry - maps module names to module classes
_registry: dict[str, type[Module]] = {}


def register(cls: type[Module]) -> type[Module]:
    """Decorator to register a module class."""
    _registry[cls.name] = cls
    return cls


def get_module(name: str) -> Module | None:
    """Get a module instance by name."""
    cls = _registry.get(name)
    if cls is None:
        return None
    return cls()


def get_all_modules() -> list[str]:
    """Get all registered module names."""
    return list(_registry.keys())


def get_module_class(name: str) -> type[Module] | None:
    """Get a module class by name (without instantiating)."""
    return _registry.get(name)


# Import modules to register them
from statusline.modules import (  # noqa: E402, F401
    context,
    cost,
    git,
    model,
    version,
    workspace,
)

__all__ = ["Module", "register", "get_module", "get_all_modules", "get_module_class"]
