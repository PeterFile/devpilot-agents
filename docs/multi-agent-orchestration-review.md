# Multi-Agent Orchestration - Review Findings

## Issue: Parent-Subtask Execution Model Incorrect

### Discovery Date
2026-01-07

### Severity
**High** - Core execution logic is incorrect

### Current (Incorrect) Implementation

The current implementation treats parent tasks and subtasks as **independent executable units**:

```python
# Current behavior in dispatch_batch.py / get_ready_tasks()
# Task 2, 2.1, 2.2 are all dispatched as separate tasks
ready_tasks = [task_1, task_2, task_2_1]  # WRONG: task_2 should not be dispatched
```

**Current Execution Flow (Wrong):**
```
Batch 1: Task 1, Task 2, Task 2.1  ← Task 2 incorrectly dispatched as standalone
Batch 2: Task 2.2
```

### Expected (Correct) Behavior

Parent tasks are **container/epic tasks** that represent the aggregation of their subtasks:

```
Task 2: "Implement authentication service" (Container - NOT executable)
    │
    ├── Task 2.1: "Create auth module"      ← Executable leaf task
    │
    └── Task 2.2: "Add password hashing"    ← Executable leaf task
            └── Depends on 2.1
```

**Rules:**
1. **Only leaf tasks are dispatched** - Tasks with subtasks are containers
2. **Parent completion = All subtasks completed** - Aggregated status
3. **Dependencies on parent = Dependencies on all subtasks** - Task 3 depends on Task 2 means Task 3 waits for 2.1 AND 2.2

**Correct Execution Flow:**
```
Batch 1: Task 1, Task 2.1           ← Only leaf tasks
Batch 2: Task 2.2                   ← After 2.1 completes
         Task 2 auto-completes      ← When 2.1 AND 2.2 done
Batch 3: Task 3                     ← After Task 2 (container) completes
```

### Affected Files

| File | Issue |
|------|-------|
| `skills/multi-agent-orchestrator/scripts/dispatch_batch.py` | Dispatches parent tasks as executable |
| `skills/multi-agent-orchestrator/scripts/spec_parser.py` | `get_ready_tasks()` doesn't filter out parent tasks |
| `skills/multi-agent-orchestrator/scripts/init_orchestration.py` | Missing parent status aggregation logic |
| `skills/multi-agent-orchestrator/scripts/test_e2e_orchestration.py` | Tests don't validate parent-subtask behavior |

### Required Changes

#### 1. Update `get_ready_tasks()` in spec_parser.py

```python
def get_ready_tasks(tasks: List[Task], completed_ids: Set[str]) -> List[Task]:
    """Get leaf tasks ready to execute (all dependencies satisfied)."""
    ready = []
    for task in tasks:
        # Skip parent tasks (they have subtasks)
        if task.subtasks:  # NEW: Filter out container tasks
            continue
        if task.task_id in completed_ids or task.status == TaskStatus.COMPLETED:
            continue
        if all(dep in completed_ids for dep in task.dependencies):
            ready.append(task)
    return ready
```

#### 2. Add parent status aggregation in init_orchestration.py

```python
def update_parent_status(state: dict) -> None:
    """Update parent task status based on subtask completion."""
    task_map = {t["task_id"]: t for t in state["tasks"]}
    
    for task in state["tasks"]:
        if task.get("subtasks"):
            subtask_statuses = [task_map[sid]["status"] for sid in task["subtasks"]]
            
            if all(s == "completed" for s in subtask_statuses):
                task["status"] = "completed"
            elif any(s == "in_progress" for s in subtask_statuses):
                task["status"] = "in_progress"
            elif any(s == "blocked" for s in subtask_statuses):
                task["status"] = "blocked"
```

#### 3. Update dependency resolution

When Task 3 depends on Task 2 (a parent), it should resolve to:
- Task 3 depends on [2.1, 2.2] (all subtasks of Task 2)

```python
def resolve_dependencies(task: Task, task_map: dict) -> List[str]:
    """Resolve dependencies, expanding parent tasks to their subtasks."""
    resolved = []
    for dep_id in task.dependencies:
        dep_task = task_map.get(dep_id)
        if dep_task and dep_task.subtasks:
            # Expand parent to all subtasks
            resolved.extend(dep_task.subtasks)
        else:
            resolved.append(dep_id)
    return resolved
```

### Test Cases to Add

```python
def test_parent_tasks_not_dispatched():
    """Parent tasks with subtasks should not be dispatched."""
    tasks = parse_tasks("""
    - [ ] 2. Parent task
      - [ ] 2.1 Subtask A
      - [ ] 2.2 Subtask B
    """)
    ready = get_ready_tasks(tasks, set())
    ready_ids = [t.task_id for t in ready]
    
    assert "2" not in ready_ids, "Parent task should not be dispatched"
    assert "2.1" in ready_ids, "Leaf subtask should be dispatched"

def test_parent_completes_when_all_subtasks_complete():
    """Parent task status should aggregate from subtasks."""
    state = {
        "tasks": [
            {"task_id": "2", "subtasks": ["2.1", "2.2"], "status": "not_started"},
            {"task_id": "2.1", "subtasks": [], "status": "completed"},
            {"task_id": "2.2", "subtasks": [], "status": "completed"},
        ]
    }
    update_parent_status(state)
    
    assert state["tasks"][0]["status"] == "completed"

def test_dependency_on_parent_waits_for_all_subtasks():
    """Task depending on parent should wait for all subtasks."""
    tasks = parse_tasks("""
    - [ ] 2. Parent task
      - [ ] 2.1 Subtask A
      - [ ] 2.2 Subtask B
    - [ ] 3. Depends on parent
      - Dependencies: 2
    """)
    
    # Only 2.1 completed
    ready = get_ready_tasks(tasks, {"2.1"})
    ready_ids = [t.task_id for t in ready]
    
    assert "3" not in ready_ids, "Task 3 should wait for all subtasks of Task 2"
    
    # Both 2.1 and 2.2 completed
    ready = get_ready_tasks(tasks, {"2.1", "2.2"})
    ready_ids = [t.task_id for t in ready]
    
    assert "3" in ready_ids, "Task 3 should be ready when all subtasks complete"
```

### Priority

**P0** - This is a fundamental logic error that affects the entire orchestration flow.

### Action Items

- [ ] Update `get_ready_tasks()` to filter out parent tasks
- [ ] Add `update_parent_status()` function
- [ ] Update dependency resolution to expand parent dependencies
- [ ] Add unit tests for parent-subtask behavior
- [ ] Update e2e tests to validate correct execution order
- [ ] Update workflow simulation document with correct behavior


---

## Issue: Parallel Task File Conflict Risk

### Discovery Date
2026-01-07

### Severity
**High** - Data loss / corruption risk

### Problem Description

When tasks are dispatched in parallel without explicit dependency declarations, they may attempt to modify the same file simultaneously, causing:

1. **Overwrite conflicts** - Later write overwrites earlier changes
2. **File lock errors** - OS-level file locking failures
3. **Merge conflicts** - Inconsistent file state
4. **Silent data loss** - Changes from one task lost without warning

### Example Scenario

```
Task 2: "Implement JWT authentication"
    → Modifies: src/auth/jwt.ts, src/auth/index.ts

Task 3: "Add token refresh logic"  
    → Modifies: src/auth/jwt.ts, src/auth/refresh.ts
                ^^^^^^^^^^^^^^^^
                CONFLICT: Same file!
```

**Current Behavior (Dangerous):**
```
Batch 1: Task 2, Task 3  ← Parallel execution
         │        │
         │        └── Writes to src/auth/jwt.ts (version B)
         └── Writes to src/auth/jwt.ts (version A)
         
Result: Version A or B survives, other changes LOST
```

### Root Cause

1. **No file-level dependency tracking** - System only tracks task-level dependencies
2. **Optimistic parallelism** - Assumes independent tasks don't share files
3. **No conflict detection** - No pre-flight check for file overlap
4. **No file locking** - No mechanism to prevent concurrent writes

### Proposed Solutions

#### Option A: Conservative Serial Execution (Simple)

Default to serial execution unless tasks are explicitly marked as parallelizable:

```python
def get_parallel_safe_batches(ready_tasks: List[Task]) -> List[List[Task]]:
    """Split ready tasks into serial batches unless explicitly parallel-safe."""
    batches = []
    for task in ready_tasks:
        if task.metadata.get("parallel_safe", False):
            # Can be batched with other parallel-safe tasks
            if batches and all(t.metadata.get("parallel_safe") for t in batches[-1]):
                batches[-1].append(task)
            else:
                batches.append([task])
        else:
            # Serial execution - own batch
            batches.append([task])
    return batches
```

**Task markup:**
```markdown
- [ ] 2. Implement JWT authentication
  - _parallel_safe: true_
  - _touches: src/auth/jwt.ts, src/auth/index.ts_
```

#### Option B: File-Level Lock Detection (Recommended)

Add file manifest to task definitions and detect conflicts at dispatch time:

```python
@dataclass
class TaskFileManifest:
    task_id: str
    reads: List[str]    # Files task may read
    writes: List[str]   # Files task may write
    
def detect_file_conflicts(tasks: List[Task]) -> List[FileConflict]:
    """Detect file write conflicts between parallel tasks."""
    conflicts = []
    
    for i, task_a in enumerate(tasks):
        for task_b in tasks[i+1:]:
            # Check write-write conflicts
            shared_writes = set(task_a.writes) & set(task_b.writes)
            if shared_writes:
                conflicts.append(FileConflict(
                    task_a=task_a.task_id,
                    task_b=task_b.task_id,
                    files=list(shared_writes),
                    type="write-write"
                ))
            
            # Check read-write conflicts (optional, stricter)
            read_write = set(task_a.reads) & set(task_b.writes)
            write_read = set(task_a.writes) & set(task_b.reads)
            if read_write or write_read:
                conflicts.append(FileConflict(
                    task_a=task_a.task_id,
                    task_b=task_b.task_id,
                    files=list(read_write | write_read),
                    type="read-write"
                ))
    
    return conflicts

def dispatch_with_conflict_check(ready_tasks: List[Task]) -> List[List[Task]]:
    """Dispatch tasks, serializing those with file conflicts."""
    conflicts = detect_file_conflicts(ready_tasks)
    
    if not conflicts:
        return [ready_tasks]  # All parallel
    
    # Build conflict graph and partition into non-conflicting batches
    return partition_by_conflicts(ready_tasks, conflicts)
```

#### Option C: Runtime File Locking (Complex)

Implement file-level locking in codeagent-wrapper:

```go
// file_lock.go
type FileLockManager struct {
    locks map[string]*sync.RWMutex
    mu    sync.Mutex
}

func (flm *FileLockManager) AcquireWrite(path string) func() {
    flm.mu.Lock()
    if flm.locks[path] == nil {
        flm.locks[path] = &sync.RWMutex{}
    }
    lock := flm.locks[path]
    flm.mu.Unlock()
    
    lock.Lock()
    return lock.Unlock
}

// In executor.go
func (e *Executor) RunTask(task TaskSpec) error {
    // Acquire locks for all files task will modify
    for _, file := range task.Writes {
        release := e.fileLocks.AcquireWrite(file)
        defer release()
    }
    
    return e.backend.Execute(task)
}
```

### Recommended Approach

**Hybrid: Option A + Option B**

1. **Default to serial** for tasks without file manifests
2. **Allow parallel** when file manifests prove no conflicts
3. **Warn on potential conflicts** detected at dispatch time

```python
def smart_dispatch(ready_tasks: List[Task]) -> List[List[Task]]:
    """Dispatch with smart conflict detection."""
    
    # Tasks with file manifests - check for conflicts
    manifest_tasks = [t for t in ready_tasks if t.file_manifest]
    no_manifest_tasks = [t for t in ready_tasks if not t.file_manifest]
    
    # Partition manifest tasks by conflicts
    manifest_batches = partition_by_conflicts(manifest_tasks)
    
    # No-manifest tasks run serially (conservative)
    serial_batches = [[t] for t in no_manifest_tasks]
    
    return manifest_batches + serial_batches
```

### Task Definition Enhancement

Add file manifest to task parsing:

```markdown
- [ ] 2. Implement JWT authentication
  - Implement token generation and validation
  - _Requirements: 2.1, 2.2_
  - _writes: src/auth/jwt.ts, src/auth/index.ts_
  - _reads: src/config/auth.ts_
```

```python
@dataclass
class Task:
    task_id: str
    description: str
    # ... existing fields ...
    writes: List[str] = field(default_factory=list)  # NEW
    reads: List[str] = field(default_factory=list)   # NEW
```

### Affected Files

| File | Change Required |
|------|-----------------|
| `spec_parser.py` | Parse `_writes:` and `_reads:` from task details |
| `dispatch_batch.py` | Add conflict detection before parallel dispatch |
| `init_orchestration.py` | Validate file manifests at initialization |
| `codeagent-wrapper/executor.go` | Optional: Add runtime file locking |

### Test Cases

```python
def test_file_conflict_detection():
    """Detect write-write conflicts between tasks."""
    task_a = Task(task_id="2", writes=["src/auth/jwt.ts"])
    task_b = Task(task_id="3", writes=["src/auth/jwt.ts"])
    
    conflicts = detect_file_conflicts([task_a, task_b])
    
    assert len(conflicts) == 1
    assert conflicts[0].files == ["src/auth/jwt.ts"]

def test_no_conflict_different_files():
    """No conflict when tasks write different files."""
    task_a = Task(task_id="2", writes=["src/auth/jwt.ts"])
    task_b = Task(task_id="3", writes=["src/auth/refresh.ts"])
    
    conflicts = detect_file_conflicts([task_a, task_b])
    
    assert len(conflicts) == 0

def test_serial_fallback_no_manifest():
    """Tasks without file manifest should run serially."""
    task_a = Task(task_id="2", writes=[])  # No manifest
    task_b = Task(task_id="3", writes=[])  # No manifest
    
    batches = smart_dispatch([task_a, task_b])
    
    assert len(batches) == 2  # Serial, not parallel
```

### Priority

**P1** - Important for production safety, but workaround exists (manual dependency declaration)

### Action Items

- [ ] Add `writes` and `reads` fields to Task dataclass
- [ ] Update spec_parser.py to parse file manifests
- [ ] Implement `detect_file_conflicts()` function
- [ ] Update dispatch_batch.py with conflict-aware batching
- [ ] Add warning logs when conflicts detected
- [ ] Document file manifest syntax in spec format guide
- [ ] Add integration tests for conflict scenarios


---

## Issue: Missing Fix Loop for Failed Reviews

### Discovery Date
2026-01-07

### Severity
**Critical** - Core workflow gap, leads to error accumulation

### Problem Description

When a task's review result is `critical` or `major`, the current system lacks a proper fix loop mechanism. Without this:

1. **Error Accumulation** - Agents build on broken foundations
2. **Cascading Failures** - Dependent tasks inherit upstream bugs
3. **Wasted Effort** - Later tasks may need complete rework
4. **No Recovery Path** - System doesn't know how to self-correct

### Current (Missing) Behavior

```
Task 1 completes → Review finds CRITICAL issue → ??? (no defined behavior)
                                                  ↓
                                            Task 2 starts anyway (WRONG!)
```

### Required: Fix Loop Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FIX LOOP WORKFLOW                               │
└─────────────────────────────────────────────────────────────────────────┘

Task 1 completes
      │
      ▼
┌─────────────┐
│   Review    │
└──────┬──────┘
       │
       ▼
   ┌───────────────┐
   │ Severity?     │
   └───────┬───────┘
           │
     ┌─────┴─────┬──────────────┐
     ▼           ▼              ▼
  [none/minor]  [major]     [critical]
     │           │              │
     ▼           └──────┬───────┘
  Task 2              ▼
  starts        ┌─────────────┐
                │ BLOCK Task 2│
                │ Enter Fix   │
                │ Loop        │
                └──────┬──────┘
                       │
           ┌───────────┴───────────┐
           ▼                       │
    ┌─────────────┐                │
    │ Attempt #N  │                │
    │ (N ≤ 3)     │                │
    └──────┬──────┘                │
           │                       │
           ▼                       │
    ┌─────────────┐                │
    │ Inject      │                │
    │ Feedback    │                │
    └──────┬──────┘                │
           │                       │
           ▼                       │
    ┌─────────────┐                │
    │ Re-dispatch │◄───────────────┤
    │ Fix Task    │                │
    └──────┬──────┘                │
           │                       │
           ▼                       │
    ┌─────────────┐                │
    │ Re-review   │                │
    └──────┬──────┘                │
           │                       │
     ┌─────┴─────┐                 │
     ▼           ▼                 │
  [pass]    [fail + N<3]───────────┘
     │           
     │      [fail + N=2]
     │           │
     │           ▼
     │    ┌─────────────┐
     │    │ ESCALATE    │
     │    │ Switch to   │
     │    │ Codex Agent │
     │    └──────┬──────┘
     │           │
     │     [fail + N=3]
     │           │
     │           ▼
     │    ┌─────────────┐
     │    │ HUMAN       │
     │    │ FALLBACK    │
     │    │ Suspend +   │
     │    │ Notify      │
     │    └─────────────┘
     │
     ▼
  Task 2 starts
```

### Fix Loop Components

#### 1. Block Dependent Tasks

When review severity is `critical` or `major`:

```python
def should_block_dependents(review_severity: str) -> bool:
    """Determine if dependent tasks should be blocked."""
    return review_severity in ["critical", "major"]

def block_dependent_tasks(state: Dict, task_id: str, reason: str) -> None:
    """Block all tasks that depend on the failed task."""
    for task in state["tasks"]:
        if task_id in task.get("dependencies", []):
            task["status"] = "blocked"
            task["blocked_reason"] = reason
            task["blocked_by"] = task_id
    
    # Add to blocked_items for visibility
    state["blocked_items"].append({
        "task_id": task_id,
        "blocking_reason": reason,
        "dependent_tasks": get_dependent_task_ids(state, task_id),
        "created_at": datetime.utcnow().isoformat() + "Z"
    })
```

#### 2. Feedback Injection

Write specific review findings to state for the fixing agent:

```python
@dataclass
class FixRequest:
    task_id: str
    attempt_number: int
    review_findings: List[Dict]
    original_output: str
    fix_instructions: str

def inject_feedback(state: Dict, task_id: str, findings: List[Dict]) -> FixRequest:
    """Create fix request with review feedback."""
    task = get_task(state, task_id)
    
    # Build specific fix instructions from findings
    instructions = []
    for finding in findings:
        if finding["severity"] in ["critical", "major"]:
            instructions.append(f"- [{finding['severity'].upper()}] {finding['summary']}")
            if finding.get("details"):
                instructions.append(f"  Details: {finding['details']}")
    
    return FixRequest(
        task_id=task_id,
        attempt_number=task.get("fix_attempts", 0) + 1,
        review_findings=findings,
        original_output=task.get("output", ""),
        fix_instructions="\n".join(instructions)
    )
```

#### 3. Re-dispatch with Fix Context

```python
def dispatch_fix_task(
    state: Dict,
    fix_request: FixRequest,
    use_escalation_agent: bool = False
) -> None:
    """Dispatch task for fixing with review context."""
    task = get_task(state, fix_request.task_id)
    
    # Determine which agent to use
    if use_escalation_agent:
        backend = "codex"  # Escalate to Codex
    else:
        backend = task.get("owner_agent", "kiro-cli")
    
    # Build fix prompt
    fix_prompt = f"""
## FIX REQUEST - Attempt {fix_request.attempt_number}/3

### Original Task
{task['description']}

### Review Findings (MUST FIX)
{fix_request.fix_instructions}

### Previous Output
{fix_request.original_output}

### Instructions
1. Review the findings above carefully
2. Fix ALL critical and major issues
3. Ensure the fix doesn't break existing functionality
4. Run tests to verify the fix
"""
    
    # Update task state
    task["status"] = "in_progress"
    task["fix_attempts"] = fix_request.attempt_number
    task["current_fix_prompt"] = fix_prompt
    
    # Dispatch
    dispatch_single_task(state, task, backend, fix_prompt)
```

#### 4. Retry Budget (Max 3 Attempts)

```python
MAX_FIX_ATTEMPTS = 3
ESCALATION_THRESHOLD = 2  # Switch agent after 2 failed attempts

def handle_review_result(state: Dict, task_id: str, severity: str) -> FixLoopAction:
    """Determine next action based on review result and attempt count."""
    task = get_task(state, task_id)
    attempts = task.get("fix_attempts", 0)
    
    if severity in ["none", "minor"]:
        return FixLoopAction.PASS  # Continue to next task
    
    if attempts >= MAX_FIX_ATTEMPTS:
        return FixLoopAction.HUMAN_FALLBACK
    
    if attempts >= ESCALATION_THRESHOLD:
        return FixLoopAction.ESCALATE_AND_RETRY
    
    return FixLoopAction.RETRY

class FixLoopAction(Enum):
    PASS = "pass"
    RETRY = "retry"
    ESCALATE_AND_RETRY = "escalate_and_retry"
    HUMAN_FALLBACK = "human_fallback"
```

#### 5. Escalation (Switch Agent)

After 2 failed attempts, switch to a different agent (Codex):

```python
def escalate_task(state: Dict, task_id: str) -> None:
    """Escalate task to Codex agent after repeated failures."""
    task = get_task(state, task_id)
    
    # Record escalation
    task["escalated"] = True
    task["escalated_at"] = datetime.utcnow().isoformat() + "Z"
    task["original_agent"] = task.get("owner_agent")
    task["owner_agent"] = "codex"  # Switch to Codex
    
    # Add escalation note
    state["pending_decisions"].append({
        "id": f"escalation-{task_id}",
        "task_id": task_id,
        "context": f"Task {task_id} failed review {task.get('fix_attempts')} times. Escalating to Codex.",
        "options": ["Continue with Codex", "Request human review"],
        "created_at": datetime.utcnow().isoformat() + "Z"
    })
```

#### 6. Human Fallback

After 3 failed attempts, suspend and notify:

```python
def trigger_human_fallback(state: Dict, task_id: str) -> None:
    """Suspend task and request human intervention."""
    task = get_task(state, task_id)
    
    # Suspend task
    task["status"] = "blocked"
    task["blocked_reason"] = "human_intervention_required"
    task["suspended_at"] = datetime.utcnow().isoformat() + "Z"
    
    # Create high-priority pending decision
    state["pending_decisions"].append({
        "id": f"human-fallback-{task_id}",
        "task_id": task_id,
        "priority": "critical",
        "context": f"""
HUMAN INTERVENTION REQUIRED

Task: {task_id} - {task['description']}
Fix Attempts: {task.get('fix_attempts', 0)}/{MAX_FIX_ATTEMPTS}
Last Review Severity: {task.get('last_review_severity')}

Review History:
{format_review_history(state, task_id)}

Action Required:
1. Review the code and findings manually
2. Either fix the issue or adjust requirements
3. Resume orchestration when ready
""",
        "options": [
            "I've fixed it manually - resume",
            "Skip this task - continue without it",
            "Abort orchestration"
        ],
        "created_at": datetime.utcnow().isoformat() + "Z"
    })
    
    # Block all dependent tasks
    block_dependent_tasks(state, task_id, "Upstream task requires human intervention")
    
    # Sync to PULSE for visibility
    sync_pulse(state)
```

### Data Model Updates

#### Task Schema Extension

```json
{
  "task_id": "1",
  "status": "in_progress",
  "fix_attempts": 2,
  "max_fix_attempts": 3,
  "escalated": true,
  "escalated_at": "2026-01-07T10:30:00Z",
  "original_agent": "kiro-cli",
  "owner_agent": "codex",
  "last_review_severity": "major",
  "blocked_reason": null,
  "blocked_by": null,
  "review_history": [
    {
      "attempt": 1,
      "severity": "critical",
      "findings": ["Missing type safety"],
      "reviewed_at": "2026-01-07T10:00:00Z"
    },
    {
      "attempt": 2,
      "severity": "major",
      "findings": ["Incomplete error handling"],
      "reviewed_at": "2026-01-07T10:20:00Z"
    }
  ]
}
```

### Complete Fix Loop State Machine

```
                                    ┌──────────────────┐
                                    │   not_started    │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                              ┌────►│   in_progress    │◄────┐
                              │     └────────┬─────────┘     │
                              │              │               │
                              │              ▼               │
                              │     ┌──────────────────┐     │
                              │     │  pending_review  │     │
                              │     └────────┬─────────┘     │
                              │              │               │
                              │              ▼               │
                              │     ┌──────────────────┐     │
                              │     │   under_review   │     │
                              │     └────────┬─────────┘     │
                              │              │               │
                              │    ┌─────────┴─────────┐     │
                              │    ▼                   ▼     │
                              │ [none/minor]    [major/critical]
                              │    │                   │     │
                              │    ▼                   ▼     │
                              │ ┌────────┐    ┌─────────────┐│
                              │ │ final  │    │ fix_required││
                              │ │ review │    └──────┬──────┘│
                              │ └───┬────┘           │       │
                              │     │          ┌─────┴─────┐ │
                              │     │          ▼           ▼ │
                              │     │    [attempts<3] [attempts≥3]
                              │     │          │           │
                              │     │          │           ▼
                              │     │          │    ┌─────────────┐
                              │     │          │    │   blocked   │
                              │     │          │    │  (human)    │
                              │     │          │    └─────────────┘
                              │     │          │
                              │     │    [attempts<2]──────┘
                              │     │          │
                              │     │    [attempts≥2]
                              │     │          │
                              │     │          ▼
                              │     │    ┌─────────────┐
                              │     │    │  escalated  │
                              │     │    │ (to codex)  │
                              │     │    └──────┬──────┘
                              │     │           │
                              │     │           └──────────────┘
                              │     │
                              │     ▼
                              │ ┌──────────────────┐
                              │ │    completed     │
                              │ └──────────────────┘
                              │
                              └─── (retry dispatch)
```

### Example Scenario

```
Timeline:
─────────────────────────────────────────────────────────────────────────

T0: Task 1 "Set up project structure" dispatched to kiro-cli
    Status: in_progress

T1: Task 1 completes, enters review
    Status: pending_review → under_review

T2: Review finds CRITICAL: "Interface definitions missing type safety"
    Status: fix_required
    Action: Block Task 2, inject feedback, re-dispatch

T3: Fix Attempt #1 - kiro-cli receives fix prompt with findings
    Status: in_progress (fix_attempts: 1)

T4: Fix completes, re-review
    Status: under_review

T5: Review finds MAJOR: "Error handling incomplete"
    Status: fix_required
    Action: Re-dispatch (attempt 2)

T6: Fix Attempt #2 - kiro-cli receives updated fix prompt
    Status: in_progress (fix_attempts: 2)

T7: Fix completes, re-review
    Status: under_review

T8: Review finds MAJOR: "Still missing edge cases"
    Status: fix_required
    Action: ESCALATE to Codex (attempt 3)

T9: Fix Attempt #3 - Codex receives fix prompt
    Status: in_progress (fix_attempts: 3, escalated: true)

T10: Fix completes, re-review
     Status: under_review

T11a: [SUCCESS] Review passes (none/minor)
      Status: final_review → completed
      Action: Unblock Task 2, dispatch Task 2

T11b: [FAILURE] Review still finds issues
      Status: blocked (human_intervention_required)
      Action: Notify human, suspend orchestration for this branch
```

### Affected Files

| File | Change Required |
|------|-----------------|
| `dispatch_batch.py` | Add fix loop logic, retry handling |
| `dispatch_reviews.py` | Add severity-based blocking |
| `consolidate_reviews.py` | Trigger fix loop on critical/major |
| `init_orchestration.py` | Add fix_attempts, escalated fields |
| `spec_parser.py` | Add new task status: `fix_required` |
| `sync_pulse.py` | Report fix loop status in PULSE |

### Test Cases

```python
def test_critical_review_blocks_dependents():
    """Critical review should block dependent tasks."""
    state = create_state_with_tasks(["1", "2"], dependencies={"2": ["1"]})
    
    handle_review_result(state, "1", severity="critical")
    
    task2 = get_task(state, "2")
    assert task2["status"] == "blocked"
    assert task2["blocked_by"] == "1"

def test_retry_budget_enforced():
    """Task should go to human fallback after 3 attempts."""
    state = create_state_with_task("1", fix_attempts=3)
    
    action = handle_review_result(state, "1", severity="major")
    
    assert action == FixLoopAction.HUMAN_FALLBACK

def test_escalation_after_two_attempts():
    """Task should escalate to Codex after 2 failed attempts."""
    state = create_state_with_task("1", fix_attempts=2)
    
    action = handle_review_result(state, "1", severity="major")
    
    assert action == FixLoopAction.ESCALATE_AND_RETRY

def test_fix_prompt_includes_findings():
    """Fix prompt should include specific review findings."""
    findings = [{"severity": "critical", "summary": "Missing type safety"}]
    
    fix_request = inject_feedback(state, "1", findings)
    
    assert "Missing type safety" in fix_request.fix_instructions
    assert "[CRITICAL]" in fix_request.fix_instructions

def test_minor_review_does_not_block():
    """Minor review issues should not block dependent tasks."""
    state = create_state_with_tasks(["1", "2"], dependencies={"2": ["1"]})
    
    handle_review_result(state, "1", severity="minor")
    
    task2 = get_task(state, "2")
    assert task2["status"] != "blocked"
```

### Priority

**P0** - Critical workflow gap that leads to error accumulation

### Action Items

- [ ] Add `fix_required` status to TaskStatus enum
- [ ] Implement `should_block_dependents()` function
- [ ] Implement `inject_feedback()` for fix context
- [ ] Add retry budget tracking (fix_attempts field)
- [ ] Implement escalation logic (switch to Codex after 2 failures)
- [ ] Implement human fallback (suspend after 3 failures)
- [ ] Update state machine diagram in design.md
- [ ] Add fix loop tests
- [ ] Update PULSE sync to show fix loop status
