"""Unit tests for statusline modules."""

from statusline.input import (
    ContextWindowInfo,
    CostInfo,
    ModelInfo,
    VersionInfo,
    WorkspaceInfo,
)
from statusline.modules import get_all_modules, get_module


class TestModelModule:
    def test_render_display_name(self):
        module = get_module("model")
        inputs = {"model": ModelInfo(id="test-model", display_name="Test Model")}
        result = module.render(inputs, {"format": "{{ display_name }}"})
        assert result == "Test Model"

    def test_render_empty_display_name(self):
        module = get_module("model")
        inputs = {"model": ModelInfo(id="x", display_name="")}
        result = module.render(inputs, {"format": "{{ display_name }}"})
        assert result == ""

    def test_render_with_label(self):
        module = get_module("model")
        inputs = {"model": ModelInfo(id="test-model", display_name="Test Model")}
        result = module.render(
            inputs, {"format": "[cyan]{{ label }}{{ display_name }}[/cyan]", "label": " "}
        )
        assert "" in result
        assert "Test Model" in result


class TestWorkspaceModule:
    def test_render_current_dir(self):
        module = get_module("workspace")
        inputs = {
            "workspace": WorkspaceInfo(
                current_dir="/home/user/my-project", project_dir="/home/user/my-project"
            )
        }
        result = module.render(inputs, {"format": "{{ current_dir | basename }}"})
        assert result == "my-project"

    def test_render_empty_workspace_falls_back_to_cwd(self):
        module = get_module("workspace")
        # Provider handles the fallback, so we test with the fallback already applied
        inputs = {
            "workspace": WorkspaceInfo(current_dir="/fallback/path", project_dir="/fallback/path")
        }
        result = module.render(inputs, {"format": "{{ current_dir | basename }}"})
        assert result == "path"

    def test_render_empty_both_returns_tilde(self):
        module = get_module("workspace")
        inputs = {"workspace": WorkspaceInfo(current_dir="", project_dir="")}
        result = module.render(inputs, {"format": "{{ current_dir | basename }}"})
        assert result == "~"


class TestCostModule:
    def test_render_cost_cents(self):
        module = get_module("cost")
        inputs = {"cost": CostInfo(total_cost_usd=0.05)}
        result = module.render(inputs, {"format": "{{ total_cost_usd | format_cost }}"})
        assert result == "$0.05"

    def test_render_cost_dollars(self):
        module = get_module("cost")
        inputs = {"cost": CostInfo(total_cost_usd=1.23)}
        result = module.render(inputs, {"format": "{{ total_cost_usd | format_cost }}"})
        assert result == "$1.23"

    def test_render_cost_small(self):
        module = get_module("cost")
        inputs = {"cost": CostInfo(total_cost_usd=0.0012)}
        result = module.render(inputs, {"format": "{{ total_cost_usd | format_cost }}"})
        assert result == "$0.0012"


class TestContextModule:
    def test_render_percentage(self):
        module = get_module("context")
        inputs = {"contextwindow": ContextWindowInfo(used_percentage=42.5)}
        result = module.render(inputs, {"format": "{{ used_percentage | format_percent }}"})
        assert result == "42%"

    def test_render_zero_percentage(self):
        module = get_module("context")
        inputs = {"contextwindow": ContextWindowInfo(used_percentage=0.0)}
        result = module.render(inputs, {"format": "{{ used_percentage | format_percent }}"})
        assert result == "0%"


class TestVersionModule:
    def test_render_version(self):
        module = get_module("version")
        inputs = {"version": VersionInfo(version="2.0.76")}
        result = module.render(inputs, {"format": "v{{ version }}"})
        assert result == "v2.0.76"

    def test_render_empty_version(self):
        module = get_module("version")
        # Provider handles the fallback to "?"
        inputs = {"version": VersionInfo(version="?")}
        result = module.render(inputs, {"format": "v{{ version }}"})
        assert result == "v?"


class TestModuleRegistry:
    def test_get_all_modules(self):
        modules = get_all_modules()
        assert "model" in modules
        assert "workspace" in modules
        assert "cost" in modules
        assert "context" in modules
        assert "version" in modules
        assert "git" in modules

    def test_get_unknown_module_returns_none(self):
        module = get_module("nonexistent")
        assert module is None
