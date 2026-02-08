"""Integration tests for statusline CLI."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_statusline(
    *args: str, stdin: str | None = None, config: str | None = None
) -> subprocess.CompletedProcess:
    """Run the statusline CLI with the given arguments.

    Args:
        *args: CLI arguments
        stdin: Input to pass via stdin
        use_user_config: If False (default), uses --config=/dev/null for hermeticity
    """
    # Global --config must come before the subcommand
    if config is not None:
        cmd = [sys.executable, "-m", "statusline", f"--config={config}", *args]
        print(cmd)
    else:
        cmd = [sys.executable, "-m", "statusline", "--config=/dev/null", *args]
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
        result = run_statusline(
            "preview", "--modules=model,version", "--theme=minimal", "--no-color"
        )
        assert result.returncode == 0
        assert "Opus 4.5" in result.stdout
        assert "v2.0.76" in result.stdout
        assert "my-project" not in result.stdout

    def test_preview_custom_separator(self):
        result = run_statusline(
            "preview", "--separator= :: ", "--theme=minimal", "--no-color"
        )
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
        input_json = json.dumps(
            {
                "model": {"id": "test", "display_name": "Test Model"},
                "workspace": {
                    "current_dir": "/path/to/test-project",
                    "project_dir": "/path/to/test-project",
                },
            }
        )
        result = run_statusline(
            "render", "--theme=minimal", "--no-color", stdin=input_json
        )
        assert result.returncode == 0
        assert "Test Model" in result.stdout
        assert "test-project" in result.stdout

    def test_render_empty_stdin(self):
        result = run_statusline("render", "--theme=minimal", "--no-color", stdin="{}")
        assert result.returncode == 0

    def test_render_with_ascii_theme(self):
        input_json = json.dumps(
            {
                "model": {"id": "test", "display_name": "Test Model"},
                "workspace": {
                    "current_dir": "/path/to/test-project",
                    "project_dir": "/path/to/test-project",
                },
            }
        )
        result = run_statusline(
            "render", "--theme=ascii", "--no-color", stdin=input_json
        )
        assert result.returncode == 0
        assert "Model:" in result.stdout
        assert "Directory:" in result.stdout


class TestCLIModules:
    def test_modules_shorthand(self):
        """Test `modules` as alias for `module ls`."""
        result = run_statusline("modules")
        assert result.returncode == 0
        assert "model" in result.stdout
        assert "context_bar" in result.stdout

    def test_module_ls(self):
        """Test `module ls` lists types and aliases."""
        result = run_statusline("module", "ls")
        assert result.returncode == 0
        # Module types
        assert "model" in result.stdout
        assert "workspace" in result.stdout
        assert "context" in result.stdout
        # Alias from defaults.toml
        assert "context_bar" in result.stdout

    def test_module_info(self):
        result = run_statusline("module", "info", "model")
        assert result.returncode == 0
        assert "display_name" in result.stdout
        assert "Opus 4.5" in result.stdout

    def test_module_info_alias(self):
        result = run_statusline("module", "info", "context_bar")
        assert result.returncode == 0
        assert "context_bar" in result.stdout
        assert "context" in result.stdout


class TestCLIConfig:
    def test_config_no_file(self):
        result = run_statusline("config")
        assert result.returncode == 0
        # Should mention config file location
        assert "statusline.toml" in result.stdout

    def test_invalid_toml_shows_friendly_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("this is not valid toml [[[")
            f.flush()
            result = run_statusline("preview", config=f.name)
            Path(f.name).unlink()
        assert result.returncode == 1
        assert "statusline:" in result.stdout
        assert "parsing config file" in result.stdout
        assert "Run 'statusline preview'" in result.stdout


class TestCLIEvents:
    def test_preview_events(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""\
[modules.events]
spacing = 2
limit = 200
brackets = true
expand = true
left = "["
right = "]"

# Tool icons (nerd font icons with trailing NBSP for proper width)
[modules.events.themes.fallback.tool_icons]
Bash = "[bright_black]$[/]"
Edit = "[yellow]E[/]"
Write = "[green]W[/]"
Read = "[cyan]R[/]"
Glob = "[blue]G[/]"
Grep = "[blue]?[/]"
Task = "[magenta]T[/]"
WebFetch = "[cyan]@[/]"
WebSearch = "[cyan]@[/]"

# Bash command-specific icons
[modules.events.themes.fallback.bash_icons]
git = "[#f05032]g[/]"
pytest = "[yellow]p[/]"

# Event icons
[modules.events.themes.fallback.event_icons]
# PostToolUse and PostToolUseFailure are None (use tool_icons)
SubagentStart = "[bold blue]<[/]"   # cod-run-all (play arrow)
SubagentStop = "[bold blue]>[/]"     # fa-stop
UserPromptSubmit = "[bright_white]U[/]"  # fa-user
Stop = "[green]S[/]"                     # nf-md-check_circle (final stop)
StopUndone = "[yellow]~[/]"              # fa-undo (stop cancelled by hook)
Interrupt = "[red]X[/]"                  # interrupted/cancelled (synthetic)
""")
            f.flush()
            result = run_statusline(
                "preview",
                "--modules=events",
                "--theme=fallback",
                "--width=60",
                "--no-color",
                config=f.name,
            )
            Path(f.name).unlink()
            print(f"stdout: {result.stdout}")
            print(f"stderr: {repr(result.stderr)}")

        assert result.returncode == 0
        assert (
            result.stdout.strip()
            == "[S ]{ U }[ E▃▃  g  S ]{ U }[ ?  <  R  E▄   >  S ]{ U }[ R ]]"
        )
