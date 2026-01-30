"""Unit tests for statusline renderer."""

from pathlib import Path

from statusline.config import Config, load_config
from statusline.input import (
    ModelInfo,
    StatuslineInput,
    WorkspaceInfo,
)
from statusline.renderer import render_statusline


def make_input(
    model: ModelInfo | None = None,
    workspace: WorkspaceInfo | None = None,
    version: str = "1.2.3",
) -> StatuslineInput:
    """Create a StatuslineInput with custom values."""
    return StatuslineInput(
        model=model or ModelInfo(id="test-model", display_name="Test Model"),
        workspace=workspace
        or WorkspaceInfo(
            current_dir="/home/user/my-project",
            project_dir="/home/user/my-project",
        ),
        version=version,
    )


def make_config(**kwargs: object) -> Config:
    """Create a Config using defaults and overriding with kwargs.

    Uses /dev/null as config path to avoid loading user config for hermeticity.
    """
    config = load_config(Path("/dev/null"))
    # Override with kwargs
    for key, value in kwargs.items():
        setattr(config, key, value)
    return config


class TestRenderer:
    def test_render_single_module(self):
        input_data = make_input()
        config = make_config(enabled=["model"], theme="minimal", color=False)
        result = render_statusline(input_data, config)
        assert result == "Test Model"

    def test_render_multiple_modules(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"], theme="minimal", color=False
        )
        result = render_statusline(input_data, config)
        assert result == "Test Model | my-project"

    def test_render_custom_separator(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="minimal",
            color=False,
            separator=" :: ",
        )
        result = render_statusline(input_data, config)
        assert result == "Test Model :: my-project"

    def test_render_empty_modules(self):
        input_data = make_input()
        config = make_config(enabled=[], color=False)
        result = render_statusline(input_data, config)
        assert result == ""

    def test_render_unknown_module_skipped(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "nonexistent", "workspace"],
            theme="minimal",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert result == "Test Model | my-project"

    def test_render_all_modules(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace", "cost", "context", "version"],
            theme="minimal",
            color=False,
        )
        result = render_statusline(input_data, config)
        # Should contain all module outputs
        assert "Test Model" in result
        assert "my-project" in result
        assert "v1.2.3" in result


class TestRendererWithThemes:
    def test_render_with_ascii_theme(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="ascii",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert "Model:" in result
        assert "Directory:" in result
        assert "Test Model" in result
        assert "my-project" in result

    def test_render_with_emoji_theme(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="emoji",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert "🤖" in result
        assert "📁" in result

    def test_render_with_nerd_theme(self):
        input_data = make_input()
        config = make_config(
            enabled=["model"],
            theme="nerd",
            color=False,
        )
        result = render_statusline(input_data, config)
        # Nerd font icon for model
        assert "" in result
        assert "Test Model" in result

    def test_render_with_color(self):
        input_data = make_input()
        config = make_config(
            enabled=["model"],
            theme="minimal",
            color=True,
        )
        result = render_statusline(input_data, config)
        # Should contain ANSI codes
        assert "\x1b[" in result
        assert "Test Model" in result
