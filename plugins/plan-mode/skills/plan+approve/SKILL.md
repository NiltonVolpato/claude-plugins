---
name: plan+approve
description: Approve a draft plan and optionally begin implementation.
disable-model-invocation: true
---

# Approve Plan

Approve the current draft plan and optionally begin implementation.

## Steps

1. Run the approve command:

```bash
python3 $SKILL_DIR/../plan+/scripts/plan.py approve
```

2. Ask the user: **"Start implementing now, or save it for a fresh session?"**

3. If the user wants to start now:
   - Run: `python3 $SKILL_DIR/../plan+/scripts/plan.py start`
   - Read the plan and appendix files
   - Begin working through the checkboxes in order
   - Check off each item as you complete it:
     - `## [ ]` → `## [x]` for phase headings (`## [ ] Phase N of M: Title`)
     - `### [ ]` → `### [x]` for step headings
     - `- [ ]` → `- [x]` for bullet items (verification, sub-tasks)

4. If the user wants to defer:
   - Confirm: "Plan approved and saved. A new session will pick it up automatically."
