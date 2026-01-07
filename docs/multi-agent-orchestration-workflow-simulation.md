# Multi-Agent Orchestration Workflow Simulation

This document simulates the complete workflow of the multi-agent orchestration system, with special focus on task hierarchy and execution states.

## Task Hierarchy Explained

### Parent-Subtask Relationship

In the task system, tasks follow a hierarchical numbering scheme:

```
Task 2          (Parent task)
├── Task 2.1    (Subtask of Task 2)
└── Task 2.2    (Subtask of Task 2)
```

**Key Points:**
- **Task 2** is a parent task (top-level)
- **Task 2.1** and **Task 2.2** are subtasks (child tasks)
- Subtasks are identified by the decimal notation (e.g., `2.1` means subtask 1 of task 2)
- The `parent_id` field links subtasks to their parent

### Relationship vs Dependencies

**Important Distinction:**

| Concept | Description | Example |
|---------|-------------|---------|
| **Parent-Subtask** | Hierarchical grouping for organization | Task 2.1 is a subtask of Task 2 |
| **Dependency** | Execution order constraint | Task 3 depends on Task 2 completing first |

Parent-subtask relationships are **organizational** - they don't automatically create execution dependencies.

## Execution State Machine

### Task Status Flow

```
                    ┌─────────────────┐
                    │   not_started   │
                    └────────┬────────┘
                             │ dispatch
                             ▼
                    ┌─────────────────┐
                    │   in_progress   │◄────────────┐
                    └────────┬────────┘             │
                             │ complete             │ fix required
                             ▼                      │
                    ┌─────────────────┐             │
                    │ pending_review  │─────────────┤
                    └────────┬────────┘             │
                             │ review start         │
                             ▼                      │
                    ┌─────────────────┐             │
                    │  under_review   │─────────────┘
                    └────────┬────────┘
                             │ all reviews pass
                             ▼
                    ┌─────────────────┐
                    │    completed    │
                    └─────────────────┘
```

### Blocked State

```
Any State ──► blocked (when dependency fails or human decision needed)
blocked ──► not_started (when unblocked)
```

## Workflow Simulation

### Sample Spec: User Authentication Feature

Let's simulate with this task structure:

```markdown
## Tasks

- [ ] 1. Set up project structure
  - Create directory structure
  - _Requirements: 1.1_

- [ ] 2. Implement authentication service
  - [ ] 2.1 Create auth module
    - Implement login/logout functions
    - _Requirements: 2.1, 2.2_
  
  - [ ] 2.2 Add password hashing
    - Use bcrypt for secure hashing
    - _Dependencies: 2.1_
    - _Requirements: 2.3_

- [ ] 3. Create login UI
  - Depends on: 2
  - _Requirements: 3.1_

- [ ] 4. Integration testing
  - Depends on: 2, 3
  - _Requirements: 4.1_
```

### Phase 1: Initialization

**Command:**
```bash
python scripts/init_orchestration.py /path/to/spec --session auth-feature
```

**AGENT_STATE.json (Initial):**
```json
{
  "spec_path": "/path/to/spec",
  "session_name": "auth-feature",
  "tasks": [
    {
      "task_id": "1",
      "description": "Set up project structure",
      "type": "code",
      "status": "not_started",
      "owner_agent": "kiro-cli",
      "dependencies": [],
      "parent_id": null,
      "subtasks": []
    },
    {
      "task_id": "2",
      "description": "Implement authentication service",
      "type": "code",
      "status": "not_started",
      "owner_agent": "kiro-cli",
      "dependencies": [],
      "parent_id": null,
      "subtasks": ["2.1", "2.2"]
    },
    {
      "task_id": "2.1",
      "description": "Create auth module",
      "type": "code",
      "status": "not_started",
      "owner_agent": "kiro-cli",
      "dependencies": [],
      "parent_id": "2",
      "subtasks": []
    },
    {
      "task_id": "2.2",
      "description": "Add password hashing",
      "type": "code",
      "status": "not_started",
      "owner_agent": "kiro-cli",
      "dependencies": ["2.1"],
      "parent_id": "2",
      "subtasks": []
    },
    {
      "task_id": "3",
      "description": "Create login UI",
      "type": "ui",
      "status": "not_started",
      "owner_agent": "gemini",
      "dependencies": ["2"],
      "parent_id": null,
      "subtasks": []
    },
    {
      "task_id": "4",
      "description": "Integration testing",
      "type": "code",
      "status": "not_started",
      "owner_agent": "kiro-cli",
      "dependencies": ["2", "3"],
      "parent_id": null,
      "subtasks": []
    }
  ],
  "review_findings": [],
  "final_reports": [],
  "blocked_items": [],
  "pending_decisions": [],
  "deferred_fixes": [],
  "window_mapping": {}
}
```

### Phase 2: First Batch Dispatch

**Ready Tasks Analysis:**
```
Task 1:   ✅ Ready (no dependencies)
Task 2:   ✅ Ready (no dependencies) 
Task 2.1: ✅ Ready (no dependencies)
Task 2.2: ❌ Not ready (depends on 2.1)
Task 3:   ❌ Not ready (depends on 2)
Task 4:   ❌ Not ready (depends on 2, 3)
```

**Dispatch Command:**
```bash
codeagent-wrapper --parallel \
  --tmux-session auth-feature \
  --state-file /path/to/AGENT_STATE.json \
  <<'EOF'
---TASK---
id: 1
backend: kiro-cli
workdir: .
---CONTENT---
Task: Set up project structure

Task ID: 1
Type: code

Reference Documents:
- Requirements: /path/to/spec/requirements.md
- Design: /path/to/spec/design.md

---TASK---
id: 2
backend: kiro-cli
workdir: .
---CONTENT---
Task: Implement authentication service

Task ID: 2
Type: code

Reference Documents:
- Requirements: /path/to/spec/requirements.md
- Design: /path/to/spec/design.md

---TASK---
id: 2.1
backend: kiro-cli
workdir: .
---CONTENT---
Task: Create auth module

Task ID: 2.1
Type: code

Reference Documents:
- Requirements: /path/to/spec/requirements.md
- Design: /path/to/spec/design.md
EOF
```

**Tmux Session Layout (Batch 1):**
```
┌─────────────────────────────────────────────────────────────┐
│ tmux session: auth-feature                                  │
├─────────────────────────────────────────────────────────────┤
│ Window 0: main                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Status: Watching AGENT_STATE.json                       │ │
│ │ Tasks in progress: 1, 2, 2.1                            │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Window 1: task-1 (Independent)                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ kiro-cli: Set up project structure                      │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Window 2: task-2 (Independent)                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ kiro-cli: Implement authentication service              │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Window 3: task-2.1 (Independent - subtask runs separately)  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ kiro-cli: Create auth module                            │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**State After Batch 1 Completes:**
```json
{
  "tasks": [
    {"task_id": "1", "status": "pending_review", ...},
    {"task_id": "2", "status": "pending_review", ...},
    {"task_id": "2.1", "status": "pending_review", ...},
    {"task_id": "2.2", "status": "not_started", ...},
    {"task_id": "3", "status": "not_started", ...},
    {"task_id": "4", "status": "not_started", ...}
  ]
}
```

### Phase 3: Second Batch Dispatch

**Ready Tasks Analysis (after 2.1 completes):**
```
Task 1:   ⏳ pending_review
Task 2:   ⏳ pending_review
Task 2.1: ⏳ pending_review
Task 2.2: ✅ Ready (2.1 completed)
Task 3:   ❌ Not ready (2 not completed yet)
Task 4:   ❌ Not ready (2, 3 not completed)
```

**Dispatch Command:**
```bash
codeagent-wrapper --parallel \
  --tmux-session auth-feature \
  --state-file /path/to/AGENT_STATE.json \
  <<'EOF'
---TASK---
id: 2.2
backend: kiro-cli
workdir: .
dependencies: 2.1
---CONTENT---
Task: Add password hashing

Task ID: 2.2
Type: code
Depends on: 2.1

Reference Documents:
- Requirements: /path/to/spec/requirements.md
- Design: /path/to/spec/design.md
EOF
```

**Tmux Session Layout (Task 2.2 as Dependent):**
```
┌─────────────────────────────────────────────────────────────┐
│ Window 3: task-2.1                                          │
│ ┌───────────────────────────┬───────────────────────────┐   │
│ │ Pane 0: kiro-cli          │ Pane 1: kiro-cli          │   │
│ │ task-2.1 (completed)      │ task-2.2 (in_progress)    │   │
│ │ ✅ Create auth module     │ 🔄 Add password hashing   │   │
│ └───────────────────────────┴───────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key Insight:** Task 2.2 runs in a **pane** within Task 2.1's window because it has a dependency on 2.1. This groups related work visually.

### Phase 4: Review Dispatch

After all implementation tasks complete, reviews are dispatched:

**Tasks Pending Review:**
- Task 1, 2, 2.1, 2.2, 3, 4

**Review Dispatch (based on criticality):**
```bash
codeagent-wrapper --parallel \
  --tmux-session auth-feature \
  --state-file /path/to/AGENT_STATE.json \
  <<'EOF'
---TASK---
id: review-1
backend: codex
workdir: .
dependencies: 1
---CONTENT---
Review task 1: Set up project structure
Files changed: src/, package.json, tsconfig.json

---TASK---
id: review-2
backend: codex
workdir: .
dependencies: 2
---CONTENT---
Review task 2: Implement authentication service
Files changed: src/auth/index.ts

---TASK---
id: review-2.1
backend: codex
workdir: .
dependencies: 2.1
---CONTENT---
Review task 2.1: Create auth module
Files changed: src/auth/login.ts, src/auth/logout.ts
EOF
```

**Tmux Layout with Reviews:**
```
┌─────────────────────────────────────────────────────────────┐
│ Window 1: task-1                                            │
│ ┌───────────────────────────┬───────────────────────────┐   │
│ │ Pane 0: kiro-cli          │ Pane 1: codex             │   │
│ │ task-1 (completed)        │ review-1 (in_progress)    │   │
│ └───────────────────────────┴───────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ Window 2: task-2                                            │
│ ┌───────────────────────────┬───────────────────────────┐   │
│ │ Pane 0: kiro-cli          │ Pane 1: codex             │   │
│ │ task-2 (completed)        │ review-2 (in_progress)    │   │
│ └───────────────────────────┴───────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Task 2, 2.1, 2.2 Relationship Summary

### Organizational Hierarchy

```
Task 2: "Implement authentication service" (Parent)
    │
    ├── Task 2.1: "Create auth module" (Subtask)
    │       └── No dependencies → Runs immediately
    │
    └── Task 2.2: "Add password hashing" (Subtask)
            └── Depends on 2.1 → Waits for 2.1 to complete
```

### Execution Timeline

```
Time ──────────────────────────────────────────────────────────►

Batch 1:
┌─────────────────────────────────────────────────────────────┐
│ Task 1  ████████████████████ (parallel)                     │
│ Task 2  ████████████████████ (parallel)                     │
│ Task 2.1 ███████████████████ (parallel)                     │
└─────────────────────────────────────────────────────────────┘

Batch 2 (after 2.1 completes):
                              ┌────────────────────────────────┐
                              │ Task 2.2 ████████████████████  │
                              └────────────────────────────────┘

Batch 3 (after 2 completes):
                                            ┌──────────────────┐
                                            │ Task 3 ██████████│
                                            └──────────────────┘

Batch 4 (after 2, 3 complete):
                                                        ┌──────┐
                                                        │Task 4│
                                                        └──────┘
```

### Key Behaviors

| Aspect | Task 2 | Task 2.1 | Task 2.2 |
|--------|--------|----------|----------|
| **Type** | Parent | Subtask | Subtask |
| **parent_id** | null | "2" | "2" |
| **Dependencies** | [] | [] | ["2.1"] |
| **Runs When** | Immediately | Immediately | After 2.1 completes |
| **Window** | Own window | Own window | Pane in 2.1's window |
| **Agent** | kiro-cli | kiro-cli | kiro-cli |

### Important Notes

1. **Parent tasks can run independently of subtasks** - Task 2 doesn't wait for 2.1 or 2.2
2. **Subtask dependencies are explicit** - Task 2.2 explicitly depends on 2.1
3. **Task 3 depends on Task 2** - This means Task 3 waits for the parent task 2, not necessarily all subtasks
4. **Tmux pane placement** - Dependent tasks create panes in their dependency's window for visual grouping

## PROJECT_PULSE.md Updates

After each batch, sync_pulse.py updates the human-readable status:

```markdown
# PROJECT_PULSE.md

## Mental Model
Authentication system with modular design:
- Auth module handles login/logout
- Password hashing via bcrypt
- UI components for login form

## Narrative Delta
### Recent Completions
- ✅ Task 1: Project structure created
- ✅ Task 2: Auth service implemented
- ✅ Task 2.1: Auth module created
- 🔄 Task 2.2: Password hashing in progress

### Upcoming
- Task 3: Login UI (blocked by Task 2)
- Task 4: Integration testing (blocked by Tasks 2, 3)

## Risks & Debt
- No blocked items
- No pending decisions
```

## Conclusion

The multi-agent orchestration system provides:

1. **Hierarchical task organization** via parent-subtask relationships
2. **Explicit dependency management** for execution ordering
3. **Visual task grouping** in tmux windows/panes
4. **Parallel execution** of independent tasks
5. **Synchronous batch dispatch** for predictable orchestration
6. **Dual-document state** (JSON for machines, Markdown for humans)
