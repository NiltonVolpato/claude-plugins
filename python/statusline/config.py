"""Configuration system for statusline."""

from __future__ import annotations

import importlib.resources
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".claude" / "statusline.toml"


@dataclass
class ModuleConfig:
    """Configuration for a single module."""

    color: str = ""
    format: str = ""  # Default format string with Rich markup
    theme: str | None = None  # Per-module theme override
    themes: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class Config:
    """Global statusline configuration."""

    theme: str = "nerd"
    color: bool = True
    enabled: list[str] = field(default_factory=lambda: ["model", "workspace"])
    separator: str = " | "
    module_configs: dict[str, ModuleConfig] = field(default_factory=dict)

    # Alias for backward compatibility
    @property
    def modules(self) -> list[str]:
        """Alias for enabled modules."""
        return self.enabled

    def get_module_config(self, module_name: str) -> ModuleConfig:
        """Get configuration for a specific module."""
        return self.module_configs.get(module_name, ModuleConfig())

    def get_theme_vars(self, module_name: str) -> dict[str, str]:
        """Get the resolved theme variables for a module.

        Merges module-level format with theme-specific variables.
        Theme vars can override the format.
        """
        module_config = self.get_module_config(module_name)
        theme_name = module_config.theme or self.theme

        # Start with module-level format
        result: dict[str, str] = {}
        if module_config.format:
            result["format"] = module_config.format

        # Theme vars override (including format if specified)
        theme_vars = module_config.themes.get(theme_name, {})
        result.update(theme_vars)

        return result

    def get_module_color(self, module_name: str) -> str:
        """Get the color for a module."""
        return self.get_module_config(module_name).color


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _parse_module_config(data: dict[str, Any]) -> ModuleConfig:
    """Parse module configuration from TOML data."""
    themes: dict[str, dict[str, str]] = {}
    themes_data = data.get("themes", {})
    for theme_name, theme_vars in themes_data.items():
        if isinstance(theme_vars, dict):
            themes[theme_name] = {k: str(v) for k, v in theme_vars.items()}

    return ModuleConfig(
        color=data.get("color", ""),
        format=data.get("format", ""),
        theme=data.get("theme"),
        themes=themes,
    )


def _parse_config(data: dict[str, Any]) -> Config:
    """Parse configuration from TOML data."""
    # Parse global settings
    theme = data.get("theme", "nerd")
    if not isinstance(theme, str):
        theme = "nerd"

    enabled_list = data.get("enabled", ["model", "workspace"])
    if not isinstance(enabled_list, list):
        enabled_list = ["model", "workspace"]

    color = data.get("color", True)
    if not isinstance(color, bool):
        color = True

    separator = data.get("separator", " | ")
    if not isinstance(separator, str):
        separator = " | "

    # Parse per-module configs
    module_configs: dict[str, ModuleConfig] = {}
    modules_data = data.get("modules", {})
    if isinstance(modules_data, dict):
        for name, module_data in modules_data.items():
            if isinstance(module_data, dict):
                module_configs[name] = _parse_module_config(module_data)

    return Config(
        theme=theme,
        color=color,
        enabled=enabled_list,
        separator=separator,
        module_configs=module_configs,
    )


def _load_defaults() -> dict[str, Any]:
    """Load default configuration from bundled defaults.toml."""
    files = importlib.resources.files("statusline")
    defaults_path = files.joinpath("defaults.toml")
    content = defaults_path.read_text()
    return tomllib.loads(content)


def _load_user_config(path: Path | None = None) -> dict[str, Any]:
    """Load user configuration from TOML file."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return {}
    try:
        return tomllib.loads(config_path.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def load_config(path: Path | None = None) -> Config:
    """Load configuration, merging defaults with user config.

    Args:
        path: Path to user config file. Defaults to ~/.claude/statusline.toml

    Returns:
        Merged Config with user values overriding defaults.
    """
    defaults = _load_defaults()
    user = _load_user_config(path)
    merged = _deep_merge(defaults, user)
    return _parse_config(merged)


def generate_default_config_toml() -> str:
    """Generate default config file content for users to customize."""
    return '''\
# Statusline configuration
# Location: ~/.claude/statusline.toml

# Global defaults
theme = "nerd"      # nerd | ascii | emoji | minimal
color = true
enabled = ["model", "workspace"]
separator = " | "

# Per-module overrides (uncomment to customize)
# [modules.model]
# color = "cyan"
# theme = "ascii"   # Override theme for this module only
#
# [modules.model.themes.nerd]
# label = ""
#
# [modules.model.themes.custom]  # Create your own theme
# label = "MODEL:"
'''
