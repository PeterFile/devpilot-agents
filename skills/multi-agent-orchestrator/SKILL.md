---
name: multi-agent-orchestrator
description: |
  Orchestrate multi-agent workflows with kiro-cli and Gemini workers.
  
  **Trigger Conditions:**
  - WHEN starting execution from a Kiro spec directory
  - WHEN dispatching tasks to worker agents
  - WHEN handling task completion and review
  - WHEN synchronizing state to PULSE document
  
  **Use Cases:**
  - Multi-agent code implementation with kiro-cli and Gemini
  - Tmux-based task visualization and monitoring
  - Structured review workflows with Codex reviewers
  - Dual-document state management (AGENT_STATE.json + PROJECT_PULSE.md)
license: MIT
---

# Multi-Agent Orchestrator

## Overview

Coordinates kiro-cli (code) and Gemini (UI) agents within a tmux environment, with Codex as the central orchestrator.

**Architecture:**
- **Spec Phase**: User creates requirements.md, design.md, tasks.md in Kiro IDE
- **Execution Phase**: Codex orchestrates workers via codeagent-wrapper

## Usage

Invoke this skill through natural language or helper scripts:

### Natural Language Commands
- "Start orchestration from spec at /path/to/specs"
- "Dispatch task-001 to the appropriate worker"
- "Show orchestration status"
- "Spawn review for task-001"
- "Sync state to PULSE document"

### Helper Scripts
```bash
# Initialize orchestration (from repo root)
python skills/multi-agent-orchestrator/scripts/init_orchestration.py /path/to/specs --session orchestration

# Dispatch ready tasks
python skills/multi-agent-orchestrator/scripts/dispatch_batch.py AGENT_STATE.json

# Spawn reviews
python skills/multi-agent-orchestrator/scripts/dispatch_reviews.py AGENT_STATE.json

# Sync to PULSE
python skills/multi-agent-orchestrator/scripts/sync_pulse.py AGENT_STATE.json PROJECT_PULSE.md

# Check status
cat AGENT_STATE.json | jq '.tasks[] | {task_id, status}'
```

## Workflow

1. **Initialize**: Parse tasks.md, create AGENT_STATE.json and PROJECT_PULSE.md
2. **Dispatch**: Collect ready tasks, invoke codeagent-wrapper --parallel
3. **Execute**: Workers run in tmux panes, results written to state file
4. **Review**: Spawn Codex reviewers for completed tasks
5. **Consolidate**: Merge review findings into final reports
6. **Sync**: Update PROJECT_PULSE.md with current state

## Agent Assignment

| Task Type | Agent | Backend |
|-----------|-------|---------|
| Code | kiro-cli | `--backend kiro-cli` |
| UI | Gemini | `--backend gemini` |
| Review | Codex | `--backend codex` |

## Task State Machine

```
not_started → in_progress → pending_review → under_review → final_review → completed
     ↓              ↓
  blocked ←────────┘
```

## Resources

**Always run scripts with `--help` first** to see usage before reading source code.

### scripts/

- `init_orchestration.py` - Initialize orchestration from spec directory
  ```bash
  python skills/multi-agent-orchestrator/scripts/init_orchestration.py <spec_path> [--session <name>]
  ```

- `dispatch_batch.py` - Dispatch ready tasks to workers
  ```bash
  python skills/multi-agent-orchestrator/scripts/dispatch_batch.py <state_file> [--dry-run]
  ```

- `dispatch_reviews.py` - Dispatch review tasks for completed work
  ```bash
  python skills/multi-agent-orchestrator/scripts/dispatch_reviews.py <state_file> [--dry-run]
  ```

- `spec_parser.py` - Parse tasks.md to extract task definitions
  ```bash
  python skills/multi-agent-orchestrator/scripts/spec_parser.py <spec_directory>
  ```

### references/

- `agent-state-schema.json` - JSON Schema for AGENT_STATE.json validation
- `task-state-machine.md` - Task state transition documentation

### references/prompts/

Prompt templates for common orchestration commands:

- `dispatch-task.md` - Dispatch a task to the appropriate worker agent
  - Parameters: task_id (required), force (optional)
  - See template for step-by-step dispatch instructions

- `spawn-review.md` - Spawn a Review Codex instance for completed tasks
  - Parameters: task_id (required), criticality (optional)
  - See template for review spawn workflow

- `sync-pulse.md` - Synchronize AGENT_STATE.json to PROJECT_PULSE.md
  - Parameters: state_file (optional), pulse_file (optional)
  - See template for PULSE update steps

- `check-status.md` - Check and report current orchestration status
  - Parameters: state_file (optional), format (optional), task_id (optional)
  - See template for status reporting formats

## Integration with codeagent-wrapper

The orchestrator invokes codeagent-wrapper with tmux support:

```bash
codeagent-wrapper --parallel \
  --tmux-session orchestration \
  --state-file /path/to/AGENT_STATE.json \
  <<'EOF'
---TASK---
id: task-001
backend: kiro-cli
workdir: .
---CONTENT---
Implement user authentication...
EOF
```

## Criticality Levels

| Level | Review Count |
|-------|--------------|
| standard | 1 reviewer |
| complex | 2+ reviewers |
| security-sensitive | 2+ reviewers with security focus |

