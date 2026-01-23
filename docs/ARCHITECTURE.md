# Multi-Agent Architecture: The Round Table

This document explains the collaborative architecture between agents in the orchestration system.

## Overview

The system uses a "Round Table" philosophy where agents collaborate with clear separation of concerns. King Arthur orchestrates, Gawain makes decisions, and workers (Codex/Gemini) execute tasks.

## Primary Agents

### ⚔️ King Arthur (Orchestrator)

The high-level strategist and leader. Owns the orchestration loop and ensures work aligns with project vision.

**Location:** `.opencode/agents/king-arthur.md`

**Responsibilities:**

- Planning and dependency analysis
- Task delegation to appropriate workers
- Quality assurance and final approval
- Project state synchronization

**Principles:**

- Radical simplicity (KISS)
- YAGNI (You Aren't Gonna Need It)
- Verifiable facts over assumptions

**Tooling:**

- Uses `bash` and `webfetch` to explore repo
- Drives `codeagent-wrapper` for task dispatch
- **Never** directly edits files — delegates implementation

### 🛡️ Gawain (Decision Knight)

Precision engine of the Round Table. Specializes in low-latency, high-accuracy decision making.

**Location:** `.opencode/agents/gawain.md`

**Responsibilities:**

- Mapping tasks to worker backends
- Determining file read/write sets
- Validating state transitions

**Protocol:**

- Outputs strict JSON only
- Zero-fluff, factual reasoning
- No file edits or command execution (tools disabled)

**Synergy:**
When Arthur identifies a delegation need, Gawain provides technical mapping:

- Which agent (codex/gemini/codex-review)
- Which window (tmux session)
- Criticality level (standard/complex/security-sensitive)

---

## Worker Agents

The orchestrator leverages specialized backends for execution:

| Agent        | Backend        | Specialty                                  |
| ------------ | -------------- | ------------------------------------------ |
| **Codex**    | `codex`        | Implementation, complex logic, refactoring |
| **Gemini**   | `gemini`       | UI/UX, component styling, frontend logic   |
| **Reviewer** | `codex-review` | Property testing, code audit, coverage     |

---

## Quality Gates

The Round Table enforces mandatory standards:

### 1. State Machine

Tasks progress through defined states:

```
not_started → in_progress → pending_review → under_review → completed
     ↓              ↓
  blocked ←─────────┘
```

### 2. Conflict Avoidance

- Prevents parallel tasks from having overlapping `writes`
- Tasks declare their file dependencies (`writes`/`reads`)
- Non-overlapping tasks run concurrently

### 3. Pulse Sync

After every dispatch cycle, `PROJECT_PULSE.md` is updated to reflect:

- Current task status
- Mental model of the project
- Blocking issues or decisions needed

---

## Communication Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ King Arthur  │────▶│   Gawain     │────▶│   Workers    │
│ (Orchestrate)│     │  (Decide)    │     │  (Execute)   │
└──────────────┘     └──────────────┘     └──────────────┘
       │                                         │
       └────────────── Sync ─────────────────────┘
                  (PROJECT_PULSE.md)
```

1. **Arthur** identifies tasks from spec
2. **Gawain** maps tasks to agents with file manifests
3. **Workers** execute in parallel via `codeagent-wrapper`
4. **Arthur** consolidates reviews and syncs pulse

---

_"The Round Table is not about individual prowess, but collective synchronization of intent and execution."_
