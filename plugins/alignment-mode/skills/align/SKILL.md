---
name: align
description: Enter alignment mode. Blocks write tools until you and the user agree on the plan.
disable-model-invocation: true
---

!`${CLAUDE_PLUGIN_ROOT}/scripts/align.py activate ${CLAUDE_PLUGIN_DATA} ${CLAUDE_SESSION_ID}`

# Alignment Mode Active

Write and execute tools are now **blocked**. You can only use read-only tools (Read, Grep, Glob, WebFetch, WebSearch, agents).

## Why this mode exists

Language is ambiguous. There are multiple ways to implement any task, and users
often have preferences or context they haven't fully communicated. This mode
ensures you and the user are aligned on **what** and **how** before any code
gets written.

## Your workflow

1. Wait for the user's next message describing what they want
2. Research the codebase as needed using read-only tools
3. Present your response:
   - **Understanding:** What you believe the user wants
   - **Plan:** How you'd accomplish it (high-level, with key code snippets)
   - **Obstacles:** Design limitations or conflicts worth discussing (skip routine issues)
   - **Affected files:** What would be modified
4. The user will iterate or approve

## Approval

When the user types **LGTM** (or runs `/lgtm`), all tools are unlocked and you
should execute the approved plan.

When you finish and stop, alignment mode reactivates automatically — write tools
are blocked again until the next approval.

## Rules

- Do NOT ask "should I proceed?" — wait for the user's LGTM
- Do NOT try to circumvent tool restrictions
- If you hit a blocker during execution, explain it and stop
- Keep plans concise — prefer short code examples over verbose explanations
