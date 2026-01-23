---
description: Systematically investigate and resolve bugs using the orchestration state and systematic analysis. Use when a task fails or an unexpected error occurs.
argument-hint: "Description of the bug or error"
allowed-tools: Bash(*), Read, Write, Edit
---

# Debug & Root Cause Analysis

Investigating: $1

## Systematic Analysis

1. **Context Check**: Analyze `AGENT_STATE.json` and `PROJECT_PULSE.md` for recent changes and failures.
2. **Reproduction**: Create or run tests to reproduce the reported issue.
3. **Execution Trace**: Use `codeagent-wrapper` to trace execution if applicable.
4. **Correction**: Propose and implement a fix documented in the orchestration state.

## Strategy

!`python e:/claude/coding-agent-flow/skills/multi-agent-orchestration/scripts/fix_loop.py --task-id auto --analyze "$1"`

> [!NOTE]
> This command leverages the same logic as the automated fix loop but allows for manual, targeted debugging of specific issues.
