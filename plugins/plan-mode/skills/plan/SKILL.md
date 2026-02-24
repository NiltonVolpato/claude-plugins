---
name: plan
description: Create an implementation plan. Use this instead of EnterPlanMode — when you would normally enter plan mode, invoke this skill instead.
argument-hint: <description of what to implement>
---

# Plan Mode

You are creating an implementation plan. Follow these rules strictly:

## Rules

1. **No EnterPlanMode** — Write the plan files directly. Do not use Claude Code's built-in plan mode.
2. **No AskUserQuestion** — Brainstorm step by step. The user will interject when they see something wrong. Think out loud as you explore.
3. **Read-only exploration** — Only edit the plan and appendix files. Do not modify any project code.
4. **Checkboxes** — Every implementation task must be a `- [ ]` checkbox item in the plan.
5. **Appendix** — Codebase findings (file paths, API notes, patterns with file:line references) go in the appendix, keeping the plan scannable.
6. **Self-contained** — The plan + appendix must have enough context that a completely fresh session can implement without re-exploring the codebase.

## Workflow

### 1. Create the draft

Run the plan CLI to create draft files:

```bash
python3 $SKILL_DIR/scripts/plan.py create <slug> --prompt="<user's original request>" --agent=<your-agent-name>
```

- The slug should be a short, descriptive, kebab-case identifier derived from the user's request (e.g., `add-authentication`, `fix-login-bug`, `refactor-database`).
- `--prompt` captures the user's original request for the log.
- `--agent` identifies you as an AI agent in the log. Pass your agent name (e.g., `--agent=claude`). Omit this flag only if a human is running the command directly.

### 2. Explore the codebase

Use Glob, Grep, Read, and Explore agents to understand:
- Existing architecture and patterns
- Files that will need changes
- APIs, types, and interfaces involved
- Test patterns and conventions

### 3. Fill in the appendix

As you discover things, immediately write them to the appendix file:
- File paths with line references (e.g., `src/auth.py:42`)
- Existing patterns to follow
- API signatures and type definitions
- Configuration and environment details

### 4. Fill in the plan

Write the implementation plan:
- **Context**: Why this change is needed, what problem it solves
- **Implementation Steps**: Ordered `- [ ]` checkboxes, specific enough for a fresh session
- **Verification**: How to verify correctness (tests, manual checks)

### 5. Build incrementally

Update the plan and appendix after each discovery. Don't wait until the end to write everything — build the documents as you go.

### 6. Present to the user

When the plan is complete, summarize it for the user. They will either:
- Run `/plan-mode:plan-approve` to approve it
- Give feedback for you to incorporate
