"""Unit tests for statusline config."""

import tempfile
from pathlib import Path

import pytest

from statusline.config import (
    Config,
    ModuleConfig,
    generate_default_config_toml,
    load_config,
)


class TestModuleConfig:
    def test_default_values(self):
        config = ModuleConfig()
        assert config.color == ""
        assert config.theme is None
        assert config.themes == {}

    def test_custom_values(self):
        config = ModuleConfig(
            color="red",
            theme="ascii",
            themes={"nerd": {"label": ""}},
        )
        assert config.color == "red"
        assert config.theme == "ascii"
        assert config.themes["nerd"]["label"] == ""


class TestConfig:
    def test_default_values(self):
        config = Config()
        assert config.theme == "nerd"
        assert config.color is True
        assert config.modules == ["model", "workspace"]
        assert config.enabled == ["model", "workspace"]
        assert config.separator == " | "

    def test_custom_values(self):
        config = Config(
            theme="ascii",
            color=False,
            enabled=["model", "cost"],
            separator=" :: ",
        )
        assert config.theme == "ascii"
        assert config.color is False
        assert config.modules == ["model", "cost"]

    def test_get_module_config(self):
        config = Config(
            module_configs={
                "model": ModuleConfig(color="red", theme="ascii"),
            }
        )
        module_config = config.get_module_config("model")
        assert module_config.color == "red"
        assert module_config.theme == "ascii"

    def test_get_module_config_missing(self):
        config = Config()
        module_config = config.get_module_config("unknown")
        assert module_config.color == ""
        assert module_config.theme is None

    def test_get_theme_vars(self):
        config = Config(
            theme="nerd",
            module_configs={
                "model": ModuleConfig(
                    themes={
                        "nerd": {"label": ""},
                        "ascii": {"label": "Model:"},
                    }
                ),
            }
        )
        theme_vars = config.get_theme_vars("model")
        assert theme_vars == {"label": ""}

    def test_get_theme_vars_with_module_override(self):
        config = Config(
            theme="nerd",
            module_configs={
                "model": ModuleConfig(
                    theme="ascii",  # Override global theme
                    themes={
                        "nerd": {"label": ""},
                        "ascii": {"label": "Model:"},
                    }
                ),
            }
        )
        theme_vars = config.get_theme_vars("model")
        assert theme_vars == {"label": "Model:"}


class TestLoadConfig:
    def test_loads_defaults(self):
        # Load with non-existent user config - should use defaults
        config = load_config(Path("/nonexistent/path/config.toml"))
        assert config.theme == "nerd"
        assert config.color is True
        # Check that defaults.toml was loaded
        assert "model" in config.module_configs
        theme_vars = config.get_theme_vars("model")
        assert theme_vars.get("label") == ""

    def test_user_config_overrides_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('''
theme = "ascii"
color = false
''')
            f.flush()
            config = load_config(Path(f.name))
            assert config.theme == "ascii"
            assert config.color is False
            # Defaults should still be loaded for module configs
            assert "model" in config.module_configs

    def test_invalid_toml_uses_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("this is not valid toml [[[")
            f.flush()
            config = load_config(Path(f.name))
            # Should return default config on parse error
            assert config.theme == "nerd"


class TestGenerateDefaultConfigToml:
    def test_generates_valid_toml(self):
        toml_content = generate_default_config_toml()
        assert "theme = " in toml_content
        assert "color = " in toml_content
        assert "enabled = " in toml_content
        assert "separator = " in toml_content
