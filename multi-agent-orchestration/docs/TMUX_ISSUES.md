# Tmux Integration Issues

This document summarizes the issues discovered during testing of the multi-agent orchestration system's tmux integration.

## Issue 1: Excessive Window Creation

**Severity:** Medium  
**Status:** Open  
**Component:** `codeagent-wrapper/tmux.go`, `codeagent-wrapper/tmux_execution.go`

### Description

When dispatching tasks, the system creates too many tmux windows with no clear organization pattern. Each independent task (without dependencies) creates a new window, leading to dozens of windows that are difficult to navigate.

### Root Cause

Current logic in `SetupTaskPanes()` and `prepareTarget()`:
- Tasks without dependencies → Create new window
- Tasks with dependencies → Create pane in dependency's window

With many independent tasks (e.g., 20+ UI tasks), this creates 20+ windows.

### Expected Behavior

Windows should be organized logically, for example:
- Group by agent type (`kiro-cli`, `gemini`, `codex-review`)
- Or limit maximum windows and reuse existing ones

### Suggested Fix

**Chosen Solution: Limit to 9 windows, orchestrator decides allocation**

The orchestrator (Codex) will decide which window each task goes to. The system enforces a maximum of 9 task windows (plus the main window = 10 total).

```go
const MaxTaskWindows = 9

// Task config includes target window assignment from orchestrator
type TaskSpec struct {
    ID           string
    Task         string
    Backend      string
    WorkDir      string
    Dependencies []string
    TargetWindow string  // NEW: Orchestrator specifies which window (1-9)
}

// TmuxManager tracks existing windows
type TmuxManager struct {
    config       TmuxConfig
    windowCount  int
    windowNames  map[string]bool  // Track created windows
    mu           sync.Mutex
}

func (tm *TmuxManager) GetOrCreateWindow(windowName string) (string, error) {
    tm.mu.Lock()
    defer tm.mu.Unlock()
    
    // If window exists, return it
    if tm.windowNames[windowName] {
        return windowName, nil
    }
    
    // Check limit
    if tm.windowCount >= MaxTaskWindows {
        return "", fmt.Errorf("max window limit (%d) reached", MaxTaskWindows)
    }
    
    // Create new window
    if _, err := tm.CreateWindow(windowName); err != nil {
        return "", err
    }
    
    tm.windowNames[windowName] = true
    tm.windowCount++
    return windowName, nil
}
```

**Orchestrator responsibility:**
- Analyze task dependencies and types
- Assign `target_window` (1-9) to each task in dispatch config
- Group related tasks into same window
- Balance load across windows

**Example dispatch config:**
```json
{
  "tasks": [
    {"id": "1.1", "target_window": "ui-setup", ...},
    {"id": "1.2", "target_window": "ui-setup", ...},
    {"id": "2.1", "target_window": "backend-api", ...},
    {"id": "3.1", "target_window": "backend-api", ...}
  ]
}
```

### References

- `codeagent-wrapper/tmux.go:140-170` - `SetupTaskPanes()`
- `codeagent-wrapper/tmux_execution.go:42-75` - `prepareTarget()`
- Requirements: 5.2, 5.3, 5.4

---

## Issue 2: Session Creation Race Condition

**Severity:** High  
**Status:** Open  
**Component:** `codeagent-wrapper/tmux.go`, `codeagent-wrapper/tmux_execution.go`

### Description

Tmux session creation fails intermittently with error:
```
ERROR: tmux new-session -d -s orchestration -n main failed: error connecting to /tmp/tmux-1000/default (Operation not permitted)
```

However, the session is eventually created successfully, and windows appear. This indicates a timing/race condition.

### Root Cause

1. `EnsureSession()` is called once in `main.go`
2. It returns immediately after `tmux new-session -d` command
3. Multiple goroutines then call `CreateWindow()` concurrently
4. Some `CreateWindow()` calls fail because the session isn't fully ready

**Timeline:**
```
T0: EnsureSession() calls `tmux new-session -d -s orchestration`
T1: tmux server starts creating session (async)
T2: EnsureSession() returns (session may not be fully ready)
T3: Multiple goroutines call CreateWindow() simultaneously
T4: Some CreateWindow() fail - session not ready
T5: Session becomes ready
T6: Later CreateWindow() calls succeed
```

### Why WSL Makes It Worse

- Tmux server startup is slower in WSL
- File system operations (`/tmp/tmux-1000/default` socket) have latency
- Cross-filesystem communication between Windows and Linux adds delay

### Suggested Fix

**Option 1: Add wait-for-ready loop after session creation**

```go
func (tm *TmuxManager) EnsureSession() error {
    if tm.SessionExists() {
        return nil
    }
    
    if _, err := tmuxCommandFn("new-session", "-d", "-s", tm.config.SessionName, "-n", tm.config.MainWindow); err != nil {
        return err
    }
    
    // Wait for session to be fully ready
    for i := 0; i < 20; i++ {
        if tm.SessionExists() {
            // Additional delay for socket stability
            time.Sleep(50 * time.Millisecond)
            return nil
        }
        time.Sleep(100 * time.Millisecond)
    }
    return fmt.Errorf("session %s not ready after creation", tm.config.SessionName)
}
```

**Option 2: Add retry logic to CreateWindow**

```go
func (tm *TmuxManager) CreateWindow(taskID string) (string, error) {
    var lastErr error
    for attempt := 0; attempt < 3; attempt++ {
        output, err := tmuxCommandFn("new-window", "-t", tm.config.SessionName, "-n", taskID, "-P", "-F", "#{window_id}")
        if err == nil {
            return strings.TrimSpace(output), nil
        }
        lastErr = err
        time.Sleep(time.Duration(100*(attempt+1)) * time.Millisecond)
    }
    return "", lastErr
}
```

**Option 3: Serialize window creation (recommended for stability)**

```go
// Add mutex to TmuxManager
type TmuxManager struct {
    config TmuxConfig
    mu     sync.Mutex  // Serialize tmux operations
}

func (tm *TmuxManager) CreateWindow(taskID string) (string, error) {
    tm.mu.Lock()
    defer tm.mu.Unlock()
    // ... existing logic ...
}
```

### References

- `codeagent-wrapper/tmux.go:58-77` - `EnsureSession()`
- `codeagent-wrapper/tmux.go:80-97` - `CreateWindow()`
- `codeagent-wrapper/main.go:315-330` - Parallel execution setup

---

## Issue 3: Only One Task Executed Despite Multiple Ready

**Severity:** High  
**Status:** Open  
**Component:** `multi-agent-orchestration/skill/scripts/dispatch_batch.py`

### Description

When dispatching tasks, only one task (e.g., task `1.2`) gets executed while other ready tasks remain in `not_started` status. Multiple tmux windows are created but most are empty.

### Root Cause

Combination of factors:

1. **File conflict detection** partitions tasks into serial batches:
   ```
   File conflict detected between 4.3 and 10.3: dashboard/frontend/src/App.tsx
   Tasks will be serialized.
   ```

2. **First batch fails** due to tmux race condition (Issue 2)

3. **Subsequent batches don't execute** because the dispatch function returns early on failure

4. **Partial state update** - some tasks marked `in_progress` but never completed

### Suggested Fix

1. Fix Issue 2 (tmux race condition) first
2. Consider continuing with remaining batches even if one fails
3. Add rollback logic for failed batch tasks

```python
def dispatch_batch(state_file: str, ...) -> DispatchResult:
    # ... existing code ...
    
    for batch_idx, batch in enumerate(batches):
        try:
            report = invoke_codeagent_wrapper(configs, session_name, state_file, dry_run)
            # ... process results ...
        except Exception as e:
            logger.error(f"Batch {batch_idx} failed: {e}")
            # Rollback tasks in this batch to not_started
            rollback_batch_tasks(state, batch)
            # Continue with next batch instead of returning
            continue
```

### References

- `multi-agent-orchestration/skill/scripts/dispatch_batch.py:580-700` - `dispatch_batch()`
- `multi-agent-orchestration/skill/scripts/dispatch_batch.py:100-180` - `partition_by_conflicts()`

---

## Testing Recommendations

### Manual Testing Steps

1. **Test session creation in isolation:**
   ```bash
   tmux kill-server
   tmux new-session -d -s test-session
   tmux has-session -t test-session && echo "OK"
   ```

2. **Test rapid window creation:**
   ```bash
   tmux new-session -d -s rapid-test
   for i in {1..10}; do tmux new-window -t rapid-test -n "win-$i" & done
   wait
   tmux list-windows -t rapid-test
   ```

3. **Test in WSL specifically:**
   - Restart WSL: `wsl --shutdown` then reopen
   - Check `/tmp/tmux-*` permissions
   - Monitor with `strace tmux new-session -d -s test 2>&1 | head -50`

### Unit Test Additions

```go
func TestEnsureSessionWaitsForReady(t *testing.T) {
    // Test that EnsureSession blocks until session is actually ready
}

func TestConcurrentWindowCreation(t *testing.T) {
    // Test creating 20 windows concurrently doesn't cause failures
}

func TestWindowCreationRetry(t *testing.T) {
    // Test that transient failures are retried
}
```

---

## Priority Order

1. **Issue 2** (Race Condition) - Blocks reliable execution
2. **Issue 3** (Single Task Execution) - Depends on Issue 2
3. **Issue 1** (Excessive Windows) - UX improvement, lower priority

---

## Related Requirements

| Requirement | Description | Affected |
|-------------|-------------|----------|
| 5.1 | Create tmux session with main window | Issue 2 |
| 5.2 | Create new window for independent tasks | Issue 1 |
| 5.3 | Create pane in dependency's window | Issue 1 |
| 5.4 | Name windows with task identifier | Issue 1 |
| 9.1 | Dispatch via codeagent-wrapper | Issue 3 |
| 12.2 | Support --tmux-session flag | Issue 2 |
| 12.5 | Create window for each independent task | Issue 1, 2 |
