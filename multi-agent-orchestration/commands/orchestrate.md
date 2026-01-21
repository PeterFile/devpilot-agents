---
description: Start multi-agent orchestration from a Kiro spec. Use when user says "start orchestration", "run orchestration", or "orchestrate spec".
argument-hint: <spec_path>
allowed-tools: Bash(*), Read, Write, Edit
---

# Multi-Agent Orchestration

Orchestrating spec at: $1

## One-Command Mode [MANDATORY]

!`python multi-agent-orchestration/skill/scripts/orchestration_loop.py --spec $1 --workdir . --assign-backend codex`

Exit codes: `0` complete, `1` halted/incomplete, `2` `pending_decisions` (human input required).  
Defaults: `--mode llm --backend opencode` and `CODEAGENT_OPENCODE_AGENT=gawain` (if unset).
Optional: `--mode deterministic` for a fixed-sequence runner.

Wait for the command to finish. Then report:

- Completion status (all dispatch units completed, or halted for human input)
- Key files changed
- Review findings summary
