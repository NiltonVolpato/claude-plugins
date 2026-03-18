---
name: lgtm
description: Approve the current plan and unlock write tools for execution
disable-model-invocation: true
---

!`${CLAUDE_PLUGIN_ROOT}/scripts/align.py lgtm ${CLAUDE_PLUGIN_DATA} ${CLAUDE_SESSION_ID}`

The user has approved your plan. All tools are now unlocked. Proceed with executing the plan you presented.

Do not re-explain the plan. Start executing immediately.
