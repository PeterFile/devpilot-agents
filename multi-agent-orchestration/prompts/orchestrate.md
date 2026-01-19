---
description: Start multi-agent orchestration from a Kiro spec
argument-hint: SPEC_PATH=<path/to/spec>
---

# Multi-Agent Orchestration

Spec: $SPEC_PATH

## One-Command Mode (MANDATORY)

Run the entire orchestration in a single blocking command:

```bash
python multi-agent-orchestration/skill/scripts/orchestration_loop.py --spec $SPEC_PATH --workdir . --mode deterministic --backend codex --assign-backend codex
```

Exit codes: `0` complete, `1` halted/incomplete, `2` `pending_decisions` (human input required).  
Optional: `--mode llm` for Ralph-style per-iteration orchestrator.

Wait for the command to finish. If it halts due to `pending_decisions`, report them. Otherwise, summarize results.
