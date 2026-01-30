# Claude Plugins

A collection of plugins for [Claude Code](https://claude.ai/claude-code). For
now, there's only one but more will come. Check the
[master-programmer](./plugins/master-programmer) plugin out!

## Installation

Add this repository as a marketplace:

```bash
/plugin marketplace add NiltonVolpato/claude-plugins
```

Then browse and install plugins via `/plugin` or install directly:

```bash
/plugin install <plugin-name>@nv-claude-plugins
```

## Plugins

### [master-programmer](./plugins/master-programmer)

Channels ancient wisdom for modern programming dilemmas through parables and koans.

![Master Programmer Plugin Demo](./plugins/master-programmer/assets/demo.gif)


## Statusline

A customizable status line for Claude Code with modular components.

### Quickstart

1. Install [uv](https://docs.astral.sh/uv/):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install and configure:
   ```bash
   uvx --from git+https://github.com/NiltonVolpato/claude-plugins statusline install
   ```

### Preview

Test how the status line looks with sample data:
```bash
uvx --from git+https://github.com/NiltonVolpato/claude-plugins statusline preview
```

### Available Modules

| Module | Description | Example |
|--------|-------------|---------|
| `model` | Model display name | Opus 4.5 |
| `workspace` | Current directory | my-project |
| `git` | Git branch and status | main*↑2 |
| `cost` | Session cost | $0.01 |
| `context` | Context window usage | 42% |
| `version` | Claude Code version | v2.0.76 |

### Themes

The statusline supports different themes:

```bash
# Nerd Font icons (default) - requires a Nerd Font
statusline preview --theme=nerd

# ASCII labels (no special fonts needed)
statusline preview --theme=ascii
# Output: Model: Opus 4.5 | Dir: my-project

# Emoji icons
statusline preview --theme=emoji
# Output: 🤖 Opus 4.5 | 📁 my-project

# Minimal (no labels)
statusline preview --theme=minimal

# Disable colors
statusline preview --no-color
```

### Configuration

Create a config file at `~/.claude/statusline.toml`:

```bash
statusline config --init
```

Example configuration:

```toml
# Global defaults
theme = "nerd"      # nerd | ascii | emoji | minimal
color = true
enabled = ["model", "workspace"]
separator = " | "

# Per-module overrides
[modules.model]
color = "cyan"
theme = "ascii"     # Override theme for this module only

# Custom theme variables per module
[modules.model.themes.nerd]
label = ""

[modules.model.themes.ascii]
label = "Model:"
```

### Customization

```bash
statusline render --modules=model,workspace,cost --separator=" :: "
```

For more options: `statusline --help`


## License

MIT License - See [LICENSE](LICENSE) for details.
