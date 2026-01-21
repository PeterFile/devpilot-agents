---
description: Start multi-agent orchestration from a Kiro spec
argument-hint: SPEC_PATH=<path/to/spec>
---

# Multi-Agent Orchestration

Spec: $SPEC_PATH

## One-Command Mode (MANDATORY)

Run the entire orchestration in a single blocking command:

```bash
python ~/.codex/skills/multi-agent-orchestrator/scripts/orchestration_loop.py --spec $SPEC_PATH --workdir . --assign-backend codex  
```

Exit codes: `0` complete, `1` halted/incomplete, `2` `pending_decisions` (human input required).
Defaults: `--mode llm --backend opencode`. If needed, set `CODEAGENT_OPENCODE_AGENT` to select an opencode agent.
Optional: `--mode deterministic` for a fixed-sequence runner.

If `codeagent-wrapper` is not found, set `CODEAGENT_WRAPPER=/path/to/codeagent-wrapper` (or add it to PATH). If tmux fails, set `CODEAGENT_NO_TMUX=1`.

Wait for the command to finish. If it halts due to `pending_decisions`, report them. Otherwise, summarize results.
