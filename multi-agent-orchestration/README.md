# Multi-Agent Orchestration System

Coordinates Codex (code + review) and Gemini (UI) agents for parallel task execution with structured review workflows.

## Structure

```
multi-agent-orchestration/
├── skill/                  # Skill definition and scripts
│   ├── SKILL.md
│   ├── scripts/            # Python orchestration scripts
│   └── references/         # Schema and prompts
├── prompts/                # Codex custom prompts
│   └── orchestrate.md      # /prompts:orchestrate command
├── commands/               # Claude Code commands
│   └── orchestrate.md      # /orchestrate command
└── docs/                   # Documentation
│   ├── usage.md
│   ├── workflow-simulation.md
│   └── review.md
```

## Quick Start

### Using Codex CLI/IDE (Recommended)

```bash
# Install the prompt
cp multi-agent-orchestration/prompts/orchestrate.md ~/.codex/prompts/

# Invoke in Codex
/prompts:orchestrate SPEC_PATH=.kiro/specs/my-feature
```

### Using Claude Code

```bash
# Install via config.json
python install.py --module orchestration

# Invoke in Claude Code
/orchestrate .kiro/specs/my-feature
```

### Manual Workflow

```bash
# Step 1: Initialize (scaffold)
python skills/multi-agent-orchestration/scripts/init_orchestration.py /path/to/spec --session my-feature --mode codex
# Outputs TASKS_PARSED.json, AGENT_STATE.json (scaffold), PROJECT_PULSE.md (template)
# Note: outputs default to <spec_path>/..; to write into CWD, add: --output .

# Step 2: AI Decision (required)
# Populate AGENT_STATE.json with owner_agent/target_window/criticality
# Update PROJECT_PULSE.md with Mental Model

# Step 3: Dispatch tasks
python skills/multi-agent-orchestration/scripts/dispatch_batch.py <state_file>

# Step 4: Dispatch reviews
python skills/multi-agent-orchestration/scripts/dispatch_reviews.py <state_file>

# Step 5: Consolidate reviews (final reports / fix loop)
python skills/multi-agent-orchestration/scripts/consolidate_reviews.py <state_file>

# Step 6: Sync status
python skills/multi-agent-orchestration/scripts/sync_pulse.py <state_file> <pulse_file>
```

### One-Command Loop Runner (Default)

```bash
python skills/multi-agent-orchestration/scripts/orchestration_loop.py --spec /path/to/spec --workdir . --assign-backend codex
```

### Deterministic Loop Runner

```bash
python skills/multi-agent-orchestration/scripts/orchestration_loop.py --spec /path/to/spec --workdir . --mode deterministic --assign-backend codex
```

Exit codes:
- `0`: all dispatch units completed
- `1`: halted/incomplete/max iterations/no progress
- `2`: `pending_decisions` present (human input required)

## Prerequisites

- Python 3.x + pytest/hypothesis
- Go 1.21+ (for codeagent-wrapper)
- tmux (Linux/macOS)
- AI backends: opencode (orchestrator, default), codex/gemini (workers)

## Related

- Go state management code remains in `codeagent-wrapper/internal/wrapper/` (state.go, state_validation.go, report.go)
- See `docs/workflow-simulation.md` for complete workflow walkthrough
