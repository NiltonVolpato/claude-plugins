"""Integration tests for statusline CLI."""

import json
import subprocess
import sys


def run_statusline(*args: str, stdin: str | None = None, use_user_config: bool = False) -> subprocess.CompletedProcess:
    """Run the statusline CLI with the given arguments.

    Args:
        *args: CLI arguments
        stdin: Input to pass via stdin
        use_user_config: If False (default), uses --config=/dev/null for hermeticity
    """
    cmd = [sys.executable, "-m", "statusline", *args]
    # Add --config=/dev/null for hermetic tests (only for render/preview commands)
    if not use_user_config and args and args[0] in ("render", "preview"):
        cmd.append("--config=/dev/null")
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        cwd="/Users/nilton/Code/claude-plugins",
    )


class TestCLIHelp:
    def test_help(self):
        result = run_statusline("--help")
        assert result.returncode == 0
        assert "status line" in result.stdout.lower()
        assert "render" in result.stdout
        assert "preview" in result.stdout
        assert "install" in result.stdout
        assert "config" in result.stdout


class TestCLIPreview:
    def test_preview_default(self):
        result = run_statusline("preview")
        assert result.returncode == 0
        assert "Opus 4.5" in result.stdout
        # Workspace now uses actual cwd for preview
        assert "claude-plugins" in result.stdout

    def test_preview_custom_modules(self):
        result = run_statusline("preview", "--modules=model,version", "--theme=minimal", "--no-color")
        assert result.returncode == 0
        assert "Opus 4.5" in result.stdout
        assert "v2.0.76" in result.stdout
        assert "my-project" not in result.stdout

    def test_preview_custom_separator(self):
        result = run_statusline("preview", "--separator= :: ", "--theme=minimal", "--no-color")
        assert result.returncode == 0
        assert " :: " in result.stdout

    def test_preview_ascii_theme(self):
        result = run_statusline("preview", "--theme=ascii", "--no-color")
        assert result.returncode == 0
        assert "Model:" in result.stdout
        assert "Directory:" in result.stdout

    def test_preview_emoji_theme(self):
        result = run_statusline("preview", "--theme=emoji", "--no-color")
        assert result.returncode == 0
        assert "🤖" in result.stdout
        assert "📁" in result.stdout

    def test_preview_minimal_theme(self):
        result = run_statusline("preview", "--theme=minimal", "--no-color")
        assert result.returncode == 0
        assert "Opus 4.5" in result.stdout
        # Should not have label prefixes
        assert "Model:" not in result.stdout


class TestCLIRender:
    def test_render_from_stdin(self):
        input_json = json.dumps({
            "model": {"id": "test", "display_name": "Test Model"},
            "workspace": {"current_dir": "/path/to/test-project", "project_dir": "/path/to/test-project"},
        })
        result = run_statusline("render", "--theme=minimal", "--no-color", stdin=input_json)
        assert result.returncode == 0
        assert "Test Model" in result.stdout
        assert "test-project" in result.stdout

    def test_render_empty_stdin(self):
        result = run_statusline("render", "--theme=minimal", "--no-color", stdin="{}")
        assert result.returncode == 0

    def test_render_with_ascii_theme(self):
        input_json = json.dumps({
            "model": {"id": "test", "display_name": "Test Model"},
            "workspace": {"current_dir": "/path/to/test-project", "project_dir": "/path/to/test-project"},
        })
        result = run_statusline("render", "--theme=ascii", "--no-color", stdin=input_json)
        assert result.returncode == 0
        assert "Model:" in result.stdout
        assert "Directory:" in result.stdout


class TestCLIList:
    def test_list_modules(self):
        result = run_statusline("list")
        assert result.returncode == 0
        assert "model" in result.stdout
        assert "workspace" in result.stdout
        assert "cost" in result.stdout
        assert "context" in result.stdout
        assert "version" in result.stdout


class TestCLIConfig:
    def test_config_no_file(self):
        result = run_statusline("config")
        assert result.returncode == 0
        # Should mention config file location
        assert "statusline.toml" in result.stdout
