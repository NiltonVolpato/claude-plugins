# Statusline Event Logging Plugin

This plugin logs Claude Code activity events to enable the statusline's `events` module.

## Requirements

- [uv](https://docs.astral.sh/uv/) must be installed for the hooks to work

## What it does

Captures tool usage, prompts, and agent lifecycle events to display a visual activity stream in the statusline.

## Events captured

- `PostToolUse` - After tool calls complete
- `PostToolUseFailure` - After tool calls fail (including interrupts)
- `UserPromptSubmit` - When user submits a prompt
- `Stop` - When agent finishes responding
- `SubagentStart` / `SubagentStop` - Subagent lifecycle

## Installation

Install via Claude Code:

```
/plugin install statusline@nv-claude-plugins
```

Or for development:

```bash
statusline install --local
```

## Migration from shell hook

If you previously used the shell hook (`~/.claude/hooks/statusline-events.sh`):

1. Open `~/.claude/settings.json` and remove hook entries that reference `statusline-events.sh`:
   ```json
   "hooks": {
     "PostToolUse": [{"hooks": [{"command": "~/.claude/hooks/statusline-events.sh", ...}]}],
     "Stop": [{"hooks": [{"command": "~/.claude/hooks/statusline-events.sh", ...}]}],
     ...
   }
   ```
2. Delete `~/.claude/hooks/statusline-events.sh`
3. Install this plugin: `/plugin install statusline@nv-claude-plugins`
4. Restart Claude Code
5. Your existing event database will continue to work (schema is compatible)
