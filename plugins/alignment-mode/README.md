# alignment-mode

Alignment mode for Claude Code. Blocks write/execute tools until you and the
agent agree on the plan before any code gets written.

## Why

Misunderstandings between you and the agent are common:

- **Ambiguity** — natural language can be interpreted in different ways
- **Hidden preferences** — there are multiple ways to implement something and
  you may have preferences or future plans the agent doesn't know about
- **Incomplete information** — you may unintentionally omit context, and the
  agent tries to figure it out instead of asking

Alignment mode forces a conversation before action. The agent researches,
presents its understanding and plan, and you iterate until you're both on the
same page. Only then does execution begin.

## How it works

1. Run `/align` — activates alignment mode
2. Describe what you want in your next message
3. The agent researches the codebase and presents its understanding + plan
4. Iterate: ask questions, request changes, clarify intent
5. Type `LGTM` or run `/lgtm` — unlocks all tools
6. The agent executes the approved plan
7. When the agent stops, alignment mode reactivates automatically

### State machine

```
             /align                  LGTM or /lgtm              agent stops
 inactive ───────────► planning ──────────────────────► executing ─────► planning
                          ▲                                               │
                          └───────────────────────────────────────────────┘
```

### What gets blocked

In **planning** state, only an allowlist of read-safe tools is permitted:
`Read`, `Grep`, `Glob`, `WebFetch`, `WebSearch`, `Agent`, `Skill`, `ToolSearch`,
`LSP`, `TodoRead`, `TaskGet`, `TaskList`, `TaskOutput`.

Everything else (Bash, Write, Edit, NotebookEdit, MCP tools, etc.) is blocked.

In **inactive** or **executing** state, all tools are allowed — the hooks are
no-ops.

## Skills

| Skill | Description |
|-------|-------------|
| `/align` | Activate alignment mode |
| `/lgtm` | Approve the plan and unlock write tools |

## Architecture

```
plugins/alignment-mode/
├── .claude-plugin/plugin.json    # Plugin manifest
├── hooks/hooks.json              # PreToolUse + UserPromptSubmit + Stop hooks
├── scripts/align.py              # State machine (planning ↔ executing)
└── skills/
    ├── align/SKILL.md            # /align — activates alignment mode
    └── lgtm/SKILL.md             # /lgtm — approves the plan
```

### Hooks

| Event | What it does |
|-------|-------------|
| `PreToolUse` (all tools) | Allows only allowlisted read-safe tools when state is `planning` |
| `UserPromptSubmit` | Detects bare "LGTM" text, transitions to `executing` |
| `Stop` | When agent finishes in `executing` state, returns to `planning` |

### State management

State is stored per session as a file in `${CLAUDE_PLUGIN_DATA}/sessions/<session_id>`.
File content is the state string: `planning` or `executing`. No file means `inactive`.

### LGTM detection

The `UserPromptSubmit` hook matches only an exact "lgtm" (case insensitive,
optional trailing punctuation). Longer prompts like "LGTM but fix the tests
first" do **not** trigger execution — use `/lgtm` for the explicit command.

## Testing locally

```bash
claude --plugin-dir ./plugins/alignment-mode
```

Then try:
```
/align
```
