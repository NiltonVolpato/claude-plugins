"""Module system for statusline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


class Module(ABC):
    """Base class for statusline modules."""

    name: str = ""

    @abstractmethod
    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the module output with Rich markup.

        Args:
            input: The parsed input from Claude Code.
            theme_vars: Theme variables including 'format' and 'label'.

        Returns:
            Rich-formatted string (e.g., "[cyan] Opus 4.5[/cyan]").
        """
        ...


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


# Import modules to register them
from statusline.modules import context, cost, git, model, version, workspace

__all__ = ["Module", "register", "get_module", "get_all_modules"]
