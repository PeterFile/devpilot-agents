# Development Commands Reference

> Skills and commands for the Multi-Agent Orchestration Framework.

## Overview

The framework uses **skills** that Claude triggers automatically based on natural language. No slash commands required — just describe what you need.

## Core Skills

### multi-agent-orchestrator

Orchestrate multi-agent workflows from a Kiro specification.

**Triggers:**

- "Start orchestration from spec at `.kiro/specs/my-feature`"
- "Run orchestration for `<feature-name>`"
- "Execute multi-agent workflow"

**What it does:**

1. Parses Kiro spec and creates `AGENT_STATE.json`
2. Dispatches tasks to Codex (code) and Gemini (UI) workers
3. Reviews and consolidates changes
4. Syncs to `PROJECT_PULSE.md`

### kiro-specs

Spec-driven development: requirements → design → tasks.

**Triggers:**

- "Create requirements for..."
- "Draft design for..."
- "Generate implementation tasks"
- Any mention of `.kiro/specs/`

### test-driven-development

Red-Green-Refactor TDD workflow.

**Triggers:**

- "Help me write tests first"
- "Use TDD for this"
- "Write failing test"

---

## Slash Commands (Optional)

If configured, these commands are available:

| Command        | Location                              | Purpose              |
| :------------- | :------------------------------------ | :------------------- |
| `/orchestrate` | `multi-agent-orchestration/commands/` | Launch orchestration |
| `/debug`       | `multi-agent-orchestration/commands/` | Root cause analysis  |
| `/sync`        | `multi-agent-orchestration/commands/` | Force pulse sync     |

---

## Script Reference

Core scripts in `skills/multi-agent-orchestration/scripts/`:

| Script                   | Purpose                         |
| :----------------------- | :------------------------------ |
| `orchestration_loop.py`  | Main automated loop runner.     |
| `init_orchestration.py`  | Parse spec and scaffold state.  |
| `dispatch_batch.py`      | Dispatch tasks to workers.      |
| `dispatch_reviews.py`    | Dispatch review tasks.          |
| `consolidate_reviews.py` | Consolidate review findings.    |
| `sync_pulse.py`          | Sync state to PROJECT_PULSE.md. |

---

## Best Practices

1. **Natural Language**: Just describe your task — skills activate automatically.
2. **Explicit Scopes**: Reference files using `@` syntax (e.g., `@src/auth.ts`).
3. **Campaign Context**: Skills maintain state in `AGENT_STATE.json` and `PROJECT_PULSE.md`.
