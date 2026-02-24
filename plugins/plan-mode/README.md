# plan-mode

Plan management plugin for Claude Code: create, approve, track, and resume implementation plans across sessions.

## Skills

- `/plan-mode:plan <description>` — Create an implementation plan with codebase exploration
- `/plan-mode:plan-approve` — Approve the current draft plan and optionally begin implementation

## CLI

The `plan.py` CLI manages plan lifecycle:

```
plan.py create <slug> [--prompt=...] [--agent=...]   Create a new draft plan
plan.py approve [--agent=...]                         Approve the current draft
plan.py start                                         Start implementing the current plan
plan.py done                                          Mark the current plan as complete
plan.py session-check                                 (Hook) Check for active plan on session start
```

### Identity tracking

Plan files include a `## Log` section that records who created and approved each plan.

- By default, the log records `user@hostname`.
- AI agents should pass `--agent=<name>` to identify themselves (e.g., `--agent=claude`).

## How it works

1. **Create**: `/plan-mode:plan` explores the codebase and writes a plan with checkboxes
2. **Approve**: `/plan-mode:plan-approve` archives the plan and sets it as current
3. **Resume**: On session start, a hook detects the active plan and prompts continuation
4. **Complete**: When all checkboxes are ticked, `plan done` clears the current plan

Plans are stored in `<project>/.claude/plans/`:
- `drafts/` — Plans being written
- `approved/` — Archived approved plans
- `current-plan.json` — Pointer to the active plan
