"""Unit tests for statusline modules."""

import pytest

from statusline.input import (
    ContextWindowInfo,
    CostInfo,
    ModelInfo,
    StatuslineInput,
    WorkspaceInfo,
)
from statusline.modules import get_all_modules, get_module


def make_input(**kwargs) -> StatuslineInput:
    """Create a StatuslineInput with custom values."""
    defaults = {
        "model": ModelInfo(id="test-model", display_name="Test Model"),
        "workspace": WorkspaceInfo(
            current_dir="/home/user/my-project",
            project_dir="/home/user/my-project",
        ),
        "cost": CostInfo(total_cost_usd=0.0123),
        "context_window": ContextWindowInfo(used_percentage=42.5),
        "version": "1.2.3",
        "cwd": "/home/user/my-project",
    }
    defaults.update(kwargs)
    return StatuslineInput(**defaults)


# Common theme vars for testing
NO_LABEL = {}
WITH_LABEL = {"label": "Test:"}


class TestModelModule:
    def test_render_display_name(self):
        module = get_module("model")
        input_data = make_input()
        result = module.render(input_data, NO_LABEL, "cyan")
        assert "Test Model" in result
        assert "[cyan]" in result

    def test_render_empty_display_name(self):
        module = get_module("model")
        input_data = make_input(model=ModelInfo(id="x", display_name=""))
        result = module.render(input_data, NO_LABEL, "cyan")
        assert "Unknown" in result

    def test_render_with_label(self):
        module = get_module("model")
        input_data = make_input()
        result = module.render(input_data, {"label": ""}, "cyan")
        assert "" in result
        assert "Test Model" in result


class TestWorkspaceModule:
    def test_render_current_dir(self):
        module = get_module("workspace")
        input_data = make_input()
        result = module.render(input_data, NO_LABEL, "blue")
        assert "my-project" in result

    def test_render_empty_workspace_falls_back_to_cwd(self):
        module = get_module("workspace")
        input_data = make_input(
            workspace=WorkspaceInfo(current_dir="", project_dir=""),
            cwd="/fallback/path",
        )
        result = module.render(input_data, NO_LABEL, "blue")
        assert "path" in result

    def test_render_empty_both_returns_tilde(self):
        module = get_module("workspace")
        input_data = make_input(
            workspace=WorkspaceInfo(current_dir="", project_dir=""),
            cwd="",
        )
        result = module.render(input_data, NO_LABEL, "blue")
        assert "~" in result


class TestCostModule:
    def test_render_cost_cents(self):
        module = get_module("cost")
        input_data = make_input(cost=CostInfo(total_cost_usd=0.05))
        result = module.render(input_data, NO_LABEL, "green")
        assert "$0.05" in result

    def test_render_cost_dollars(self):
        module = get_module("cost")
        input_data = make_input(cost=CostInfo(total_cost_usd=1.23))
        result = module.render(input_data, NO_LABEL, "green")
        assert "$1.23" in result

    def test_render_cost_small(self):
        module = get_module("cost")
        input_data = make_input(cost=CostInfo(total_cost_usd=0.0012))
        result = module.render(input_data, NO_LABEL, "green")
        assert "$0.0012" in result


class TestContextModule:
    def test_render_percentage(self):
        module = get_module("context")
        input_data = make_input(
            context_window=ContextWindowInfo(used_percentage=42.5)
        )
        result = module.render(input_data, NO_LABEL, "yellow")
        assert "42%" in result

    def test_render_zero_percentage(self):
        module = get_module("context")
        input_data = make_input(
            context_window=ContextWindowInfo(used_percentage=0.0)
        )
        result = module.render(input_data, NO_LABEL, "yellow")
        assert "0%" in result


class TestVersionModule:
    def test_render_version(self):
        module = get_module("version")
        input_data = make_input(version="2.0.76")
        result = module.render(input_data, NO_LABEL, "dim")
        assert "v2.0.76" in result

    def test_render_empty_version(self):
        module = get_module("version")
        input_data = make_input(version="")
        result = module.render(input_data, NO_LABEL, "dim")
        assert "v?" in result


class TestModuleRegistry:
    def test_get_all_modules(self):
        modules = get_all_modules()
        assert "model" in modules
        assert "workspace" in modules
        assert "cost" in modules
        assert "context" in modules
        assert "version" in modules

    def test_get_unknown_module_returns_none(self):
        module = get_module("nonexistent")
        assert module is None
