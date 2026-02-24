---
name: plan-approve
description: Approve a draft plan and optionally begin implementation.
argument-hint: "[slug]"
disable-model-invocation: true
---

# Approve Plan

Approve the draft plan and optionally begin implementation.

## Steps

1. Run the approve command. The slug is optional — if not provided by the user, the CLI reads it from `current-draft.json` (written by `plan create`). If you know the slug from the planning session, pass it explicitly:

```bash
python3 $SKILL_DIR/../plan/scripts/plan.py approve $ARGUMENTS
```

2. Ask the user: **"Start implementing now, or save it for a fresh session?"**

3. If the user wants to start now:
   - Run: `python3 $SKILL_DIR/../plan/scripts/plan.py start`
   - Read the plan and appendix files
   - Begin working through the checkboxes in order
   - Check off each `- [ ]` item as you complete it (change to `- [x]`)

4. If the user wants to defer:
   - Confirm: "Plan approved and saved. A new session will pick it up automatically."
