# Requirements Document

## Introduction

This specification addresses three critical issues identified in the multi-agent orchestration system review:

1. **Parent-Subtask Execution Model** - Parent tasks are incorrectly dispatched as executable units instead of being treated as containers for their subtasks
2. **Parallel Task File Conflict** - Tasks dispatched in parallel may modify the same files, causing data loss or corruption
3. **Fix Loop for Failed Reviews** - When reviews find critical/major issues, there is no mechanism to retry fixes before proceeding

These fixes are essential for production-ready orchestration that maintains correctness and prevents cascading failures.

## Glossary

- **Parent_Task**: A task that contains subtasks; acts as a container/epic and is NOT directly executable
- **Leaf_Task**: A task with no subtasks; the only type of task that can be dispatched for execution
- **Fix_Loop**: The workflow for retrying a task after review finds critical/major issues
- **Fix_Attempt**: A single retry of a task with review feedback injected
- **Escalation**: Switching to a different agent (e.g., Codex) after repeated fix failures
- **Human_Fallback**: Suspending orchestration and requesting human intervention after max retries
- **File_Manifest**: Declaration of files a task will read or write, used for conflict detection
- **File_Conflict**: When two parallel tasks both write to the same file
- **Review_Severity**: Classification of review findings: critical, major, minor, none

## Requirements

### Requirement 1: Parent Task Container Model

**User Story:** As an orchestrator, I want parent tasks to act as containers for their subtasks, so that only leaf tasks are dispatched for execution and parent completion is derived from subtask completion.

#### Acceptance Criteria

1. WHEN get_ready_tasks() is called, THE System SHALL exclude tasks that have subtasks from the ready list
2. WHEN a task has subtasks, THE System SHALL only dispatch the leaf subtasks for execution
3. WHEN all subtasks of a parent task complete, THE System SHALL automatically mark the parent task as completed
4. WHEN any subtask of a parent task is in_progress, THE System SHALL mark the parent task as in_progress
5. WHEN any subtask of a parent task is blocked, THE System SHALL mark the parent task as blocked
6. WHEN a task depends on a parent task, THE System SHALL resolve the dependency to all subtasks of that parent
7. WHEN a task depends on a parent task, THE System SHALL wait for all subtasks to complete before becoming ready

### Requirement 2: File Conflict Detection

**User Story:** As an orchestrator, I want to detect file conflicts between parallel tasks, so that I can prevent data loss from concurrent file modifications.

#### Acceptance Criteria

1. THE Task data model SHALL support optional writes and reads fields for file manifest declaration
2. WHEN parsing tasks.md, THE Spec_Parser SHALL extract _writes: and _reads: markers from task details
3. WHEN dispatching parallel tasks, THE System SHALL detect write-write conflicts between tasks
4. IF write-write conflicts are detected, THEN THE System SHALL serialize conflicting tasks into separate batches
5. WHEN tasks have no file manifest, THE System SHALL default to serial execution for safety
6. WHEN tasks have file manifests with no conflicts, THE System SHALL allow parallel execution
7. THE System SHALL log warnings when file conflicts are detected and tasks are serialized

### Requirement 3: Fix Loop Workflow

**User Story:** As an orchestrator, I want a fix loop for failed reviews, so that tasks can be retried with feedback before blocking dependent tasks.

#### Acceptance Criteria

1. WHEN a review finds critical or major severity issues, THE System SHALL enter the fix loop
2. WHEN entering fix loop, THE System SHALL block all tasks that depend on the failed task
3. THE System SHALL support a maximum of 3 fix attempts per task
4. WHEN a fix attempt is needed, THE System SHALL inject review findings into the task prompt
5. WHEN a fix attempt completes, THE System SHALL re-dispatch review for the task
6. WHEN fix attempts reach 2 failures, THE System SHALL escalate to a different agent (Codex)
7. WHEN fix attempts reach 3 failures, THE System SHALL trigger human fallback
8. WHEN human fallback is triggered, THE System SHALL suspend the task and add a pending_decision entry
9. WHEN a fix loop succeeds (review passes), THE System SHALL unblock dependent tasks
10. THE Task data model SHALL track fix_attempts, escalated, and review_history fields

### Requirement 4: Task State Machine Extension

**User Story:** As an orchestrator, I want the task state machine to support fix loop states, so that task progress through the fix loop is trackable.

#### Acceptance Criteria

1. THE System SHALL add fix_required status to the task state machine
2. WHEN a review finds critical/major issues, THE System SHALL transition task from under_review to fix_required
3. WHEN a fix is dispatched, THE System SHALL transition task from fix_required to in_progress
4. THE System SHALL allow transition from fix_required to blocked when max retries exceeded
5. THE System SHALL validate all state transitions including new fix_required state
6. WHEN a task is in fix_required status, THE System SHALL include it in the fix loop processing

### Requirement 5: Dependency Resolution Enhancement

**User Story:** As an orchestrator, I want dependencies on parent tasks to resolve correctly, so that dependent tasks wait for all subtasks to complete.

#### Acceptance Criteria

1. WHEN resolving dependencies, THE System SHALL expand parent task IDs to their subtask IDs
2. WHEN checking if a task is ready, THE System SHALL check completion of expanded dependencies
3. WHEN a parent task has no subtasks, THE System SHALL treat it as a leaf task for dependency purposes
4. THE System SHALL handle nested subtasks (e.g., 1.1.1) correctly in dependency resolution
5. WHEN building the dependency graph, THE System SHALL include implicit parent-subtask relationships

### Requirement 6: Review Feedback Injection

**User Story:** As an orchestrator, I want review findings injected into fix prompts, so that agents have specific guidance on what to fix.

#### Acceptance Criteria

1. WHEN creating a fix prompt, THE System SHALL include all critical and major findings from the review
2. WHEN creating a fix prompt, THE System SHALL include the original task output for reference
3. WHEN creating a fix prompt, THE System SHALL clearly mark the attempt number (e.g., "Attempt 2/3")
4. THE fix prompt SHALL instruct the agent to address all listed issues
5. WHEN escalating to a different agent, THE System SHALL include the full fix history in the prompt

### Requirement 7: Fix Loop Completion Handling

**User Story:** As an orchestrator, I want fix task completion to properly update fix_attempts, so that escalation and human fallback thresholds are correctly triggered.

#### Acceptance Criteria

1. WHEN a fix task completes successfully, THE System SHALL call on_fix_task_complete to increment fix_attempts
2. WHEN a fix task completes, THE System SHALL transition the task from in_progress to pending_review
3. WHEN fix_attempts is incremented, THE System SHALL persist the updated count to AGENT_STATE
4. WHEN a fix task dispatch fails, THE System SHALL rollback the task status from in_progress to fix_required
5. WHEN a fix task dispatch fails, THE System SHALL NOT increment fix_attempts
6. THE System SHALL ensure fix_attempts accurately reflects the number of completed fix attempts

### Requirement 8: Parent Status Update Consistency

**User Story:** As an orchestrator, I want parent status updates to run after all dispatch operations, so that parent task statuses are always consistent with their subtasks.

#### Acceptance Criteria

1. WHEN dispatching only fix tasks (no new tasks), THE System SHALL still call update_parent_statuses after dispatch
2. WHEN dispatch_batch returns early due to no ready tasks, THE System SHALL still call update_parent_statuses
3. THE System SHALL call update_parent_statuses at the end of every dispatch cycle regardless of what was dispatched
4. WHEN update_parent_statuses is called, THE System SHALL persist the updated statuses to AGENT_STATE

