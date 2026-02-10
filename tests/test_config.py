"""Unit tests for statusline config."""

import tempfile
from pathlib import Path

from statusline.config import (
    Config,
    ContextConfig,
    EventsConfig,
    ModelConfig,
    RowLayout,
    generate_default_config_toml,
    load_config,
    normalize_enabled,
)


class TestModuleConfig:
    """Tests for typed module configs."""

    def test_model_config_basic(self):
        """ModelConfig can be created with required fields."""
        config = ModelConfig(
            type="model",
            color="cyan",
            format="test format",
            theme="nerd",
        )
        assert config.type == "model"
        assert config.color == "cyan"
        assert config.format == "test format"

    def test_theme_override_applied(self):
        """Theme overrides are applied via model_validator."""
        config = ModelConfig(
            type="model",
            color="cyan",
            format="base format",
            label="base label",
            theme="nerd",
            themes={"nerd": {"label": "nerd label", "color": "blue"}},
        )
        # Theme override should be applied
        assert config.label == "nerd label"
        assert config.color == "blue"
        # Non-overridden field keeps base value
        assert config.format == "base format"

    def test_expand_defaults_to_false(self):
        config = ModelConfig(
            type="model", color="cyan", format="test", theme="nerd"
        )
        assert config.expand is False

    def test_expand_set_to_true(self):
        config = ModelConfig(
            type="model", color="cyan", format="test", theme="nerd", expand=True
        )
        assert config.expand is True


class TestConfig:
    def test_default_values(self):
        config = Config()
        assert config.theme == "nerd"
        assert config.color is True
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
        assert config.enabled == ["model", "cost"]

    def test_get_module_config(self):
        config = Config(
            modules={
                "model": ModelConfig(
                    type="model", color="red", format="test", theme="ascii"
                ),
            }
        )
        module_config = config.get_module_config("model")
        assert module_config is not None
        assert isinstance(module_config, ModelConfig)
        assert module_config.color == "red"
        assert module_config.theme == "ascii"

    def test_get_module_config_missing(self):
        config = Config()
        module_config = config.get_module_config("unknown")
        assert module_config is None

    def test_theme_override_in_config(self):
        """Theme overrides are applied when config is created."""
        config = Config(
            theme="nerd",
            modules={
                "model": ModelConfig(
                    type="model",
                    color="cyan",
                    format="base",
                    label="base label",
                    theme="nerd",
                    themes={
                        "nerd": {"label": "nerd icon"},
                        "ascii": {"label": "Model:"},
                    },
                ),
            },
        )
        module_config = config.get_module_config("model")
        assert module_config is not None
        assert isinstance(module_config, ModelConfig)
        # Theme override applied
        assert module_config.label == "nerd icon"

    def test_per_module_theme_override(self):
        """Per-module theme setting overrides global theme."""
        config = Config(
            theme="nerd",
            modules={
                "model": ModelConfig(
                    type="model",
                    color="cyan",
                    format="base",
                    label="base",
                    theme="ascii",  # Override global theme
                    themes={
                        "nerd": {"label": "nerd icon"},
                        "ascii": {"label": "Model:"},
                    },
                ),
            },
        )
        module_config = config.get_module_config("model")
        assert module_config is not None
        assert isinstance(module_config, ModelConfig)
        # ASCII theme override applied
        assert module_config.label == "Model:"

    def test_get_module_type(self):
        """get_module_type returns the type field."""
        config = Config(
            modules={
                "model": ModelConfig(
                    type="model", color="red", format="test", theme="nerd"
                ),
            }
        )
        assert config.get_module_type("model") == "model"

    def test_get_module_type_with_alias(self):
        """Aliases use type field from config."""
        config = Config(
            modules={
                "ctx_percent": ContextConfig(
                    type="context", color="yellow", format="test", theme="nerd"
                ),
            }
        )
        assert config.get_module_type("ctx_percent") == "context"

    def test_get_module_type_unknown_alias(self):
        """Unknown alias returns itself as type."""
        config = Config()
        assert config.get_module_type("unknown") == "unknown"


class TestLoadConfig:
    def test_loads_defaults(self):
        # Load with non-existent user config - should use defaults
        config = load_config(Path("/nonexistent/path/config.toml"))
        assert config.theme == "nerd"
        assert config.color is True
        # Check that defaults.toml was loaded
        assert "model" in config.modules
        model_config = config.get_module_config("model")
        assert model_config is not None
        assert isinstance(model_config, ModelConfig)
        # Theme-resolved values are on the config directly
        assert model_config.format != ""
        assert model_config.label != ""  # Nerd theme has icon label

    def test_user_config_overrides_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
theme = "ascii"
color = false
""")
            f.flush()
            config = load_config(Path(f.name))
            assert config.theme == "ascii"
            assert config.color is False
            # Defaults should still be loaded for module configs
            assert "model" in config.modules

    def test_invalid_toml_raises_error(self):
        from statusline.errors import StatuslineError

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("this is not valid toml [[[")
            f.flush()
            try:
                load_config(Path(f.name))
                assert False, "Expected StatuslineError"
            except StatuslineError:
                pass  # Expected


class TestNormalizeEnabled:
    def test_flat_list(self):
        """Simple list → 1 row, left-only."""
        layout = normalize_enabled(["a", "b", "c"])
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["a", "b", "c"]
        assert layout.rows[0].right == []

    def test_dict_left_right(self):
        """Dict with left/right → 1 row with both sides."""
        layout = normalize_enabled({"left": ["a", "b"], "right": ["c"]})
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == ["c"]

    def test_dict_left_only(self):
        """Dict with only left → 1 row, left-only."""
        layout = normalize_enabled({"left": ["a", "b"]})
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == []

    def test_dict_right_only(self):
        """Dict with only right → 1 row, right-only."""
        layout = normalize_enabled({"right": ["c"]})
        assert len(layout.rows) == 1
        assert layout.rows[0].left == []
        assert layout.rows[0].right == ["c"]

    def test_numeric_keys_list_values(self):
        """Dict with numeric keys and list values → multi-row, left-only."""
        layout = normalize_enabled({"0": ["a", "b"], "1": ["c"]})
        assert len(layout.rows) == 2
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == []
        assert layout.rows[1].left == ["c"]
        assert layout.rows[1].right == []

    def test_numeric_keys_dict_values(self):
        """Dict with numeric keys and dict values → multi-row with alignment."""
        layout = normalize_enabled({
            "0": {"left": ["a"], "right": ["b"]},
            "1": {"left": ["c"], "right": ["d"]},
        })
        assert len(layout.rows) == 2
        assert layout.rows[0] == RowLayout(left=["a"], right=["b"])
        assert layout.rows[1] == RowLayout(left=["c"], right=["d"])

    def test_numeric_keys_sorted(self):
        """Numeric keys are sorted numerically."""
        layout = normalize_enabled({"2": ["c"], "0": ["a"], "1": ["b"]})
        assert len(layout.rows) == 3
        assert layout.rows[0].left == ["a"]
        assert layout.rows[1].left == ["b"]
        assert layout.rows[2].left == ["c"]

    def test_empty_list(self):
        """Empty list → 1 row with empty left."""
        layout = normalize_enabled([])
        assert len(layout.rows) == 1
        assert layout.rows[0].left == []

    def test_mixed_numeric_list_and_dict(self):
        """Mix of list and dict values under numeric keys."""
        layout = normalize_enabled({
            "0": ["a", "b"],
            "1": {"left": ["c"], "right": ["d"]},
        })
        assert len(layout.rows) == 2
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == []
        assert layout.rows[1].left == ["c"]
        assert layout.rows[1].right == ["d"]


class TestConfigLayout:
    def test_layout_from_list(self):
        """Config.layout normalizes a list enabled field."""
        config = Config(enabled=["model", "workspace"])
        layout = config.layout
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["model", "workspace"]

    def test_layout_from_dict(self):
        """Config.layout normalizes a dict enabled field."""
        config = Config(enabled={"left": ["model"], "right": ["context"]})
        layout = config.layout
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["model"]
        assert layout.rows[0].right == ["context"]

    def test_width_default_none(self):
        config = Config()
        assert config.width is None

    def test_width_override(self):
        config = Config(width=120)
        assert config.width == 120


class TestGenerateDefaultConfigToml:
    def test_generates_valid_toml(self):
        toml_content = generate_default_config_toml()
        assert "theme = " in toml_content
        assert "color = " in toml_content
        assert "enabled = " in toml_content
        assert "separator = " in toml_content

    def test_includes_layout_examples(self):
        toml_content = generate_default_config_toml()
        assert "enabled.left" in toml_content
        assert "enabled.right" in toml_content
