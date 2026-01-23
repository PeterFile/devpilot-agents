---
description: Manually synchronize the current project state to PROJECT_PULSE.md. Use when you want to update the project's mental model after manual changes or for a status check.
allowed-tools: Bash(*), Read, Write
---

# Sync Project Pulse

Synchronizing state from `AGENT_STATE.json` to `PROJECT_PULSE.md`...

## Execution

!`python e:/claude/coding-agent-flow/skills/multi-agent-orchestration/scripts/sync_pulse.py AGENT_STATE.json PROJECT_PULSE.md`

## Outcome

- Updated **Mental Model** in `PROJECT_PULSE.md`
- Synchronized **Task Status** and **Progress**
- Refreshed **Context** for all participating agents
