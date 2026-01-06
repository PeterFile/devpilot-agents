# Multi-Agent Orchestration Workflow Simulation

This document simulates a complete workflow of the multi-agent orchestration system, demonstrating how Codex orchestrates kiro-cli and Gemini workers to implement a feature from a Kiro spec.

## Scenario: Implementing User Authentication Feature

We'll simulate implementing a user authentication feature with login UI.

---

## Phase 1: Spec Phase (Kiro IDE)

### Step 1.1: User Creates Spec in Kiro

User interacts with Kiro IDE to create the spec files:

```
.kiro/specs/user-auth/
├── requirements.md    # EARS-pattern requirements
├── design.md          # Architecture and correctness properties
└── tasks.md           # Implementation checklist
```

**tasks.md content:**
```markdown
# Implementation Plan: User Authentication

## Tasks

- [ ] 1. Set up authentication module structure
  - Create src/auth/ directory
  - Define interfaces and types
  - _Requirements: 1.1, 1.2_

- [ ] 2. Implement JWT token service
  - [ ] 2.1 Create token generation
  - [ ] 2.2 Create token validation
  - _Requirements: 1.3, 1.4_
  - _Dependencies: 1_

- [ ] 3. Create login UI
  - [ ] 3.1 Build login form component
  - [ ] 3.2 Add form validation
  - _Requirements: 2.1, 2.2_

- [ ] 4. Integration and testing
  - Wire auth service to login UI
  - _Requirements: 3.1_
  - _Dependencies: 2, 3_
```

---

## Phase 2: Execution Phase (Codex + codeagent-wrapper)

### Step 2.1: Initialize Orchestration

User triggers execution by invoking Codex with the spec path:

```bash
codex "Initialize orchestration from .kiro/specs/user-auth/"
```

**Orchestrator Actions:**

1. **Validate Spec Directory**
```python
# scripts/init_orchestration.py
result = validate_spec_directory(".kiro/specs/user-auth/")
# Output: ValidationResult(valid=True, spec_path=".kiro/specs/user-auth/")
```

2. **Parse Tasks**
```python
tasks = parse_tasks(".kiro/specs/user-auth/tasks.md")
# Output:
# [
#   Task(id="1", description="Set up authentication module structure", type="code", dependencies=[]),
#   Task(id="2", description="Implement JWT token service", type="code", dependencies=["1"]),
#   Task(id="2.1", description="Create token generation", type="code", dependencies=["1"]),
#   Task(id="2.2", description="Create token validation", type="code", dependencies=["1"]),
#   Task(id="3", description="Create login UI", type="ui", dependencies=[]),
#   Task(id="3.1", description="Build login form component", type="ui", dependencies=[]),
#   Task(id="3.2", description="Add form validation", type="ui", dependencies=[]),
#   Task(id="4", description="Integration and testing", type="code", dependencies=["2", "3"])
# ]
```

3. **Initialize AGENT_STATE.json**
```json
{
  "spec_path": ".kiro/specs/user-auth/",
  "session_name": "user-auth-orch",
  "tasks": [
    {"task_id": "1", "status": "not_started", "owner_agent": "kiro-cli", "criticality": "standard"},
    {"task_id": "2", "status": "not_started", "owner_agent": "kiro-cli", "criticality": "standard", "dependencies": ["1"]},
    {"task_id": "2.1", "status": "not_started", "owner_agent": "kiro-cli", "criticality": "standard", "dependencies": ["1"]},
    {"task_id": "2.2", "status": "not_started", "owner_agent": "kiro-cli", "criticality": "standard", "dependencies": ["1"]},
    {"task_id": "3", "status": "not_started", "owner_agent": "gemini", "criticality": "standard"},
    {"task_id": "3.1", "status": "not_started", "owner_agent": "gemini", "criticality": "standard"},
    {"task_id": "3.2", "status": "not_started", "owner_agent": "gemini", "criticality": "standard"},
    {"task_id": "4", "status": "not_started", "owner_agent": "kiro-cli", "criticality": "complex", "dependencies": ["2", "3"]}
  ],
  "review_findings": [],
  "final_reports": [],
  "blocked_items": [],
  "pending_decisions": [],
  "deferred_fixes": [],
  "window_mapping": {}
}
```

4. **Initialize PROJECT_PULSE.md**
```markdown
# 🔮 PROJECT PULSE — user-auth

## Mental Model
Authentication system with JWT tokens and React login UI.

## Narrative Delta
- [2026-01-07] Orchestration initialized with 8 tasks

## Risks & Debt
- No blockers identified

## Semantic Anchors
- Spec: .kiro/specs/user-auth/
```

---

### Step 2.2: Dispatch Implementation Batch (Round 1)

**Orchestrator identifies ready tasks:**
```python
ready_tasks = get_ready_tasks(state)
# Output: [Task("1"), Task("3"), Task("3.1"), Task("3.2")]
# Tasks 2, 2.1, 2.2, 4 are blocked (have unmet dependencies)
```

**Orchestrator invokes codeagent-wrapper:**
```bash
codeagent-wrapper --parallel \
  --tmux-session user-auth-orch \
  --state-file ./AGENT_STATE.json \
  <<'EOF'
---TASK---
id: 1
backend: kiro-cli
workdir: .
---CONTENT---
Task: Set up authentication module structure

Task ID: 1
Type: code

Reference Documents:
- Requirements: .kiro/specs/user-auth/requirements.md
- Design: .kiro/specs/user-auth/design.md

Instructions:
1. Create src/auth/ directory
2. Define interfaces and types for authentication

---TASK---
id: 3
backend: gemini
workdir: .
---CONTENT---
Task: Create login UI

Task ID: 3
Type: ui

Reference Documents:
- Requirements: .kiro/specs/user-auth/requirements.md
- Design: .kiro/specs/user-auth/design.md

---TASK---
id: 3.1
backend: gemini
workdir: .
---CONTENT---
Task: Build login form component

Task ID: 3.1
Type: ui

---TASK---
id: 3.2
backend: gemini
workdir: .
---CONTENT---
Task: Add form validation

Task ID: 3.2
Type: ui
EOF
```

**codeagent-wrapper Actions:**

1. **Create/Reuse Tmux Session**
```
tmux session: user-auth-orch
```

2. **Create Windows for Independent Tasks**
```
Window 1: task-1 (kiro-cli pane)
Window 2: task-3 (gemini pane)
Window 3: task-3.1 (gemini pane)
Window 4: task-3.2 (gemini pane)
```

3. **Execute Tasks in Parallel**
```
[task-1] kiro-cli: Creating src/auth/ directory...
[task-3] gemini: Creating LoginPage component...
[task-3.1] gemini: Building LoginForm component...
[task-3.2] gemini: Adding form validation...
```

4. **Real-time State Updates**
```json
// AGENT_STATE.json updated as each task completes
{
  "tasks": [
    {"task_id": "1", "status": "pending_review", "files_changed": ["src/auth/types.ts", "src/auth/index.ts"]},
    {"task_id": "3", "status": "pending_review", "files_changed": ["src/pages/LoginPage.tsx"]},
    {"task_id": "3.1", "status": "pending_review", "files_changed": ["src/components/LoginForm.tsx"]},
    {"task_id": "3.2", "status": "pending_review", "files_changed": ["src/components/LoginForm.tsx"]}
  ]
}
```

5. **Return Execution Report**
```json
{
  "batch_id": "batch-001",
  "tasks_completed": 4,
  "tasks_failed": 0,
  "results": [
    {"task_id": "1", "status": "pending_review", "exit_code": 0},
    {"task_id": "3", "status": "pending_review", "exit_code": 0},
    {"task_id": "3.1", "status": "pending_review", "exit_code": 0},
    {"task_id": "3.2", "status": "pending_review", "exit_code": 0}
  ]
}
```

---

### Step 2.3: Dispatch Review Batch (Round 1)

**Orchestrator identifies tasks needing review:**
```python
pending_review = get_tasks_pending_review(state)
# Output: ["1", "3", "3.1", "3.2"]
```

**Orchestrator invokes codeagent-wrapper for reviews:**
```bash
codeagent-wrapper --parallel \
  --tmux-session user-auth-orch \
  --state-file ./AGENT_STATE.json \
  <<'EOF'
---TASK---
id: review-1
backend: codex
workdir: .
dependencies: 1
---CONTENT---
Review task-1: Audit authentication module structure
Files changed: src/auth/types.ts, src/auth/index.ts
Produce Review_Finding with severity assessment.

---TASK---
id: review-3
backend: codex
workdir: .
dependencies: 3
---CONTENT---
Review task-3: Audit LoginPage component
Files changed: src/pages/LoginPage.tsx
Produce Review_Finding with severity assessment.

---TASK---
id: review-3.1
backend: codex
workdir: .
dependencies: 3.1
---CONTENT---
Review task-3.1: Audit LoginForm component
Files changed: src/components/LoginForm.tsx
Produce Review_Finding with severity assessment.

---TASK---
id: review-3.2
backend: codex
workdir: .
dependencies: 3.2
---CONTENT---
Review task-3.2: Audit form validation
Files changed: src/components/LoginForm.tsx
Produce Review_Finding with severity assessment.
EOF
```

**codeagent-wrapper Actions:**

1. **Create Review Panes in Task Windows**
```
Window task-1: Add review pane (codex)
Window task-3: Add review pane (codex)
Window task-3.1: Add review pane (codex)
Window task-3.2: Add review pane (codex)
```

2. **Execute Reviews in Parallel**
```
[review-1] codex: Reviewing auth module structure... PASSED (severity: none)
[review-3] codex: Reviewing LoginPage... PASSED (severity: minor)
[review-3.1] codex: Reviewing LoginForm... PASSED (severity: none)
[review-3.2] codex: Reviewing validation... PASSED (severity: none)
```

3. **Write Review Findings**
```json
{
  "review_findings": [
    {"task_id": "1", "reviewer": "codex-1", "severity": "none", "summary": "Auth module structure is well organized"},
    {"task_id": "3", "reviewer": "codex-1", "severity": "minor", "summary": "Consider adding loading state"},
    {"task_id": "3.1", "reviewer": "codex-1", "severity": "none", "summary": "LoginForm implementation is correct"},
    {"task_id": "3.2", "reviewer": "codex-1", "severity": "none", "summary": "Form validation is comprehensive"}
  ]
}
```

**Orchestrator consolidates reviews:**
```python
for task_id in ["1", "3", "3.1", "3.2"]:
    consolidate_reviews(task_id)
    # Updates task status to "completed"
```

---

### Step 2.4: Dispatch Implementation Batch (Round 2)

**Orchestrator identifies newly ready tasks:**
```python
ready_tasks = get_ready_tasks(state)
# Output: [Task("2"), Task("2.1"), Task("2.2")]
# Task 4 still blocked (waiting for task 2 and 3 to complete)
```

**Orchestrator invokes codeagent-wrapper:**
```bash
codeagent-wrapper --parallel \
  --tmux-session user-auth-orch \
  --state-file ./AGENT_STATE.json \
  <<'EOF'
---TASK---
id: 2
backend: kiro-cli
workdir: .
dependencies: 1
---CONTENT---
Task: Implement JWT token service

Task ID: 2
Type: code

---TASK---
id: 2.1
backend: kiro-cli
workdir: .
dependencies: 1
---CONTENT---
Task: Create token generation

Task ID: 2.1
Type: code

---TASK---
id: 2.2
backend: kiro-cli
workdir: .
dependencies: 1
---CONTENT---
Task: Create token validation

Task ID: 2.2
Type: code
EOF
```

**codeagent-wrapper Actions:**

1. **Create Panes in Dependency Window (task-1)**
```
Window task-1: Add pane for task-2 (kiro-cli)
Window task-1: Add pane for task-2.1 (kiro-cli)
Window task-1: Add pane for task-2.2 (kiro-cli)
```

2. **Execute Tasks**
```
[task-2] kiro-cli: Implementing JWT service...
[task-2.1] kiro-cli: Creating token generation...
[task-2.2] kiro-cli: Creating token validation...
```

3. **Return Execution Report**
```json
{
  "batch_id": "batch-002",
  "tasks_completed": 3,
  "results": [
    {"task_id": "2", "status": "pending_review", "exit_code": 0},
    {"task_id": "2.1", "status": "pending_review", "exit_code": 0},
    {"task_id": "2.2", "status": "pending_review", "exit_code": 0}
  ]
}
```

---

### Step 2.5: Dispatch Review Batch (Round 2)

Similar to Round 1, reviews are dispatched and consolidated.

After completion:
```json
{
  "tasks": [
    {"task_id": "2", "status": "completed"},
    {"task_id": "2.1", "status": "completed"},
    {"task_id": "2.2", "status": "completed"}
  ]
}
```

---

### Step 2.6: Dispatch Implementation Batch (Round 3 - Final)

**Orchestrator identifies ready tasks:**
```python
ready_tasks = get_ready_tasks(state)
# Output: [Task("4")]
# All dependencies (2, 3) are now completed
```

**Orchestrator invokes codeagent-wrapper:**
```bash
codeagent-wrapper --parallel \
  --tmux-session user-auth-orch \
  --state-file ./AGENT_STATE.json \
  <<'EOF'
---TASK---
id: 4
backend: kiro-cli
workdir: .
dependencies: 2,3
---CONTENT---
Task: Integration and testing

Task ID: 4
Type: code
Criticality: complex

Instructions:
Wire auth service to login UI
EOF
```

**codeagent-wrapper Actions:**

1. **Create Window for Task 4** (independent of specific dependency window due to multiple deps)
```
Window task-4: kiro-cli pane
```

2. **Execute Task**
```
[task-4] kiro-cli: Wiring auth service to login UI...
[task-4] kiro-cli: Running integration tests...
```

---

### Step 2.7: Dispatch Review Batch (Round 3 - Final)

Task 4 has criticality "complex", so multiple reviewers are spawned:

```bash
codeagent-wrapper --parallel \
  --tmux-session user-auth-orch \
  --state-file ./AGENT_STATE.json \
  <<'EOF'
---TASK---
id: review-4-1
backend: codex
workdir: .
dependencies: 4
---CONTENT---
Review task-4 (Reviewer 1): Audit integration implementation
Focus: Code correctness and error handling

---TASK---
id: review-4-2
backend: codex
workdir: .
dependencies: 4
---CONTENT---
Review task-4 (Reviewer 2): Audit integration implementation
Focus: Security and edge cases
EOF
```

**Multiple Review Panes Created:**
```
Window task-4: Add review pane 1 (codex)
Window task-4: Add review pane 2 (codex)
```

**Review Findings Consolidated:**
```json
{
  "final_reports": [
    {
      "task_id": "4",
      "overall_severity": "minor",
      "summary": "Integration is correct. Minor suggestion: add retry logic for token refresh.",
      "finding_count": 2
    }
  ]
}
```

---

### Step 2.8: Sync PULSE and Complete

**Orchestrator syncs state to PULSE:**
```python
sync_pulse()
```

**Final PROJECT_PULSE.md:**
```markdown
# 🔮 PROJECT PULSE — user-auth

## Mental Model
Authentication system with JWT tokens and React login UI.
- Auth module: src/auth/
- Login UI: src/pages/LoginPage.tsx, src/components/LoginForm.tsx

## Narrative Delta
- [2026-01-07 10:00] Orchestration initialized with 8 tasks
- [2026-01-07 10:15] ✅ Task 1 completed: Auth module structure
- [2026-01-07 10:15] ✅ Task 3 completed: Login UI
- [2026-01-07 10:15] ✅ Task 3.1 completed: LoginForm component
- [2026-01-07 10:15] ✅ Task 3.2 completed: Form validation
- [2026-01-07 10:30] ✅ Task 2 completed: JWT token service
- [2026-01-07 10:30] ✅ Task 2.1 completed: Token generation
- [2026-01-07 10:30] ✅ Task 2.2 completed: Token validation
- [2026-01-07 10:45] ✅ Task 4 completed: Integration and testing
- [2026-01-07 10:45] 🎉 All tasks completed!

## Risks & Debt
- Minor: Consider adding retry logic for token refresh (from review-4)

## Semantic Anchors
- Auth types: src/auth/types.ts
- JWT service: src/auth/jwt.ts
- Login page: src/pages/LoginPage.tsx
- Login form: src/components/LoginForm.tsx
```

**Final AGENT_STATE.json:**
```json
{
  "spec_path": ".kiro/specs/user-auth/",
  "session_name": "user-auth-orch",
  "tasks": [
    {"task_id": "1", "status": "completed", "owner_agent": "kiro-cli"},
    {"task_id": "2", "status": "completed", "owner_agent": "kiro-cli"},
    {"task_id": "2.1", "status": "completed", "owner_agent": "kiro-cli"},
    {"task_id": "2.2", "status": "completed", "owner_agent": "kiro-cli"},
    {"task_id": "3", "status": "completed", "owner_agent": "gemini"},
    {"task_id": "3.1", "status": "completed", "owner_agent": "gemini"},
    {"task_id": "3.2", "status": "completed", "owner_agent": "gemini"},
    {"task_id": "4", "status": "completed", "owner_agent": "kiro-cli"}
  ],
  "review_findings": [...],
  "final_reports": [...],
  "blocked_items": [],
  "pending_decisions": [],
  "deferred_fixes": [
    {"task_id": "4", "description": "Add retry logic for token refresh", "severity": "minor"}
  ],
  "window_mapping": {
    "1": "task-1",
    "2": "task-1",
    "2.1": "task-1",
    "2.2": "task-1",
    "3": "task-3",
    "3.1": "task-3.1",
    "3.2": "task-3.2",
    "4": "task-4"
  }
}
```

---

## Tmux Session Layout (Final State)

```
┌─────────────────────────────────────────────────────────────────┐
│ tmux session: user-auth-orch                                    │
├─────────────────────────────────────────────────────────────────┤
│ Window 0: main                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Status Pane: watch AGENT_STATE.json                         │ │
│ │ All 8 tasks completed ✅                                    │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Window 1: task-1                                                │
│ ┌───────────────────┬───────────────────┬─────────────────────┐ │
│ │ Pane 0: kiro-cli  │ Pane 1: kiro-cli  │ Pane 2: kiro-cli    │ │
│ │ task-1 ✅         │ task-2 ✅         │ task-2.1 ✅         │ │
│ ├───────────────────┼───────────────────┼─────────────────────┤ │
│ │ Pane 3: kiro-cli  │ Pane 4: codex     │                     │ │
│ │ task-2.2 ✅       │ review-1 ✅       │                     │ │
│ └───────────────────┴───────────────────┴─────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Window 2: task-3                                                │
│ ┌─────────────────────────────┬───────────────────────────────┐ │
│ │ Pane 0: gemini              │ Pane 1: codex                 │ │
│ │ task-3 ✅                   │ review-3 ✅                   │ │
│ └─────────────────────────────┴───────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Window 3: task-3.1                                              │
│ ┌─────────────────────────────┬───────────────────────────────┐ │
│ │ Pane 0: gemini              │ Pane 1: codex                 │ │
│ │ task-3.1 ✅                 │ review-3.1 ✅                 │ │
│ └─────────────────────────────┴───────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Window 4: task-3.2                                              │
│ ┌─────────────────────────────┬───────────────────────────────┐ │
│ │ Pane 0: gemini              │ Pane 1: codex                 │ │
│ │ task-3.2 ✅                 │ review-3.2 ✅                 │ │
│ └─────────────────────────────┴───────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Window 5: task-4                                                │
│ ┌─────────────────────────────┬───────────────────────────────┐ │
│ │ Pane 0: kiro-cli            │ Pane 1: codex                 │ │
│ │ task-4 ✅                   │ review-4-1 ✅                 │ │
│ ├─────────────────────────────┼───────────────────────────────┤ │
│ │ Pane 2: codex               │                               │ │
│ │ review-4-2 ✅               │                               │ │
│ └─────────────────────────────┴───────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary

This simulation demonstrates the complete multi-agent orchestration workflow:

1. **Spec Phase**: User creates requirements, design, and tasks in Kiro IDE
2. **Initialization**: Codex parses spec and initializes state files
3. **Batch Dispatch**: Tasks are dispatched in batches respecting dependencies
4. **Parallel Execution**: Independent tasks run concurrently in separate tmux windows
5. **Dependent Tasks**: Tasks with dependencies run in panes within dependency's window
6. **Review Phase**: Completed tasks are reviewed by Codex instances
7. **Multi-Reviewer**: Complex/security-sensitive tasks get multiple reviewers
8. **State Sync**: AGENT_STATE.json and PROJECT_PULSE.md stay synchronized
9. **Completion**: All tasks complete with full audit trail

The tmux session persists after completion, allowing users to review task history and agent outputs.
