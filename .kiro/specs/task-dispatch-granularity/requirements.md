# Requirements Document

## Introduction

This feature optimizes the task dispatch granularity in the multi-agent orchestration system. Currently, the system dispatches each leaf task (subtask) to a separate agent/tmux window, which breaks context continuity. This feature changes the dispatch unit from "leaf task" to "parent task", ensuring that all subtasks of a parent task are executed sequentially by the same agent in the same window, preserving context and improving execution quality.

## Glossary

- **Orchestrator**: The central coordinator that manages task dispatch and agent assignment
- **Dispatch_Unit**: The atomic unit of work assigned to a single agent window (changed from leaf task to parent task)
- **Parent_Task**: A task that contains one or more subtasks (e.g., task "1" with subtasks "1.1", "1.2", "1.3")
- **Leaf_Task**: A task with no subtasks; the smallest executable unit
- **Standalone_Task**: A task that has no parent and no subtasks (e.g., task "1" without any "1.x" subtasks)
- **Agent_Window**: A tmux window where a single agent executes tasks
- **Context_Continuity**: The preservation of execution context (code understanding, design decisions) across related subtasks
- **Task_Group**: A parent task and all its subtasks, treated as a single dispatch unit

## Requirements

### Requirement 1: Dispatch Unit Definition

**User Story:** As an orchestrator, I want to dispatch parent tasks (not leaf tasks) to agents, so that related subtasks share the same execution context.

#### Acceptance Criteria

1. WHEN the Orchestrator identifies ready tasks, THE Orchestrator SHALL select parent tasks (tasks with subtasks) as dispatch units instead of leaf tasks
2. WHEN a task has no subtasks AND no parent, THE Orchestrator SHALL treat it as a standalone dispatch unit
3. WHEN a task is a leaf task with a parent, THE Orchestrator SHALL NOT dispatch it independently; it SHALL be executed as part of its parent task's dispatch
4. THE Orchestrator SHALL create exactly one Agent_Window per dispatch unit

### Requirement 2: Subtask Sequential Execution

**User Story:** As an agent, I want to receive all subtasks of a parent task together, so that I can execute them sequentially while maintaining context.

#### Acceptance Criteria

1. WHEN a parent task is dispatched to an agent, THE Orchestrator SHALL include all subtask descriptions and details in the dispatch payload
2. WHEN an agent receives a parent task dispatch, THE Agent SHALL execute subtasks in order (1.1 → 1.2 → 1.3)
3. WHEN an agent completes a subtask, THE Agent SHALL update the subtask status before proceeding to the next subtask
4. WHILE executing subtasks, THE Agent SHALL maintain context from previous subtasks within the same parent task

### Requirement 3: Status Tracking Granularity

**User Story:** As a user, I want to see progress at the subtask level, so that I can monitor detailed execution status.

#### Acceptance Criteria

1. THE Orchestrator SHALL track status for both parent tasks and subtasks independently
2. WHEN a subtask status changes, THE Orchestrator SHALL update AGENT_STATE.json with the new subtask status
3. WHEN all subtasks of a parent task are completed, THE Orchestrator SHALL automatically mark the parent task as completed
4. WHEN any subtask is blocked, THE Orchestrator SHALL mark the parent task as blocked
5. WHEN any subtask is in_progress, THE Orchestrator SHALL mark the parent task as in_progress

### Requirement 4: Dependency Resolution

**User Story:** As an orchestrator, I want dependencies to work correctly with the new dispatch granularity, so that task ordering is preserved.

#### Acceptance Criteria

1. WHEN a task depends on a parent task, THE Orchestrator SHALL wait for ALL subtasks of that parent to complete before dispatching the dependent task
2. WHEN a task depends on a specific subtask (e.g., depends on "1.2"), THE Orchestrator SHALL wait for that specific subtask to complete
3. WHEN calculating ready tasks, THE Orchestrator SHALL only consider parent tasks and standalone tasks as dispatchable units
4. THE Orchestrator SHALL expand parent task dependencies to include all subtasks when checking completion

### Requirement 5: Dispatch Payload Structure

**User Story:** As an agent, I want a clear payload structure that includes parent task context and all subtasks, so that I can execute the work unit effectively.

#### Acceptance Criteria

1. WHEN building a dispatch payload for a parent task, THE Orchestrator SHALL include:
   - Parent task ID and description
   - Ordered list of subtasks with their IDs, descriptions, and details
   - Reference to requirements.md and design.md
   - Any task-level metadata (criticality, file manifests)
2. WHEN building a dispatch payload for a standalone task, THE Orchestrator SHALL include the task as a single-item work unit
3. THE Orchestrator SHALL format the payload so agents can iterate through subtasks sequentially

### Requirement 6: Window Allocation Optimization

**User Story:** As a system administrator, I want fewer tmux windows created, so that resource usage is optimized.

#### Acceptance Criteria

1. THE Orchestrator SHALL create at most one Agent_Window per parent task or standalone task
2. WHEN multiple parent tasks can run in parallel (no conflicts), THE Orchestrator SHALL create separate windows for each
3. THE Orchestrator SHALL NOT create separate windows for individual subtasks
4. WHEN a parent task completes, THE Orchestrator MAY reuse the Agent_Window for subsequent tasks

### Requirement 7: Backward Compatibility

**User Story:** As a user with existing specs, I want the system to handle specs without parent-subtask hierarchy, so that my existing workflows continue to work.

#### Acceptance Criteria

1. WHEN a tasks.md contains only flat tasks (no hierarchy), THE Orchestrator SHALL treat each task as a standalone dispatch unit
2. WHEN a tasks.md contains mixed hierarchy (some parent tasks, some standalone), THE Orchestrator SHALL handle both correctly
3. THE Orchestrator SHALL NOT require changes to existing tasks.md format

### Requirement 8: Error Handling and Recovery

**User Story:** As an orchestrator, I want proper error handling when subtask execution fails, so that the system can recover gracefully.

#### Acceptance Criteria

1. IF a subtask fails during execution, THEN THE Agent SHALL report the failure and stop executing subsequent subtasks
2. IF a subtask fails, THEN THE Orchestrator SHALL mark that subtask as blocked and the parent task as blocked
3. WHEN a blocked subtask is unblocked, THE Orchestrator SHALL resume execution from that subtask (not restart from the beginning)
4. THE Orchestrator SHALL preserve completed subtask results even when a later subtask fails

### Requirement 9: Review Integration

**User Story:** As a reviewer, I want to review the entire parent task as a unit, so that I can assess the complete implementation coherently.

#### Acceptance Criteria

1. WHEN all subtasks of a parent task reach pending_review status, THE Orchestrator SHALL dispatch a single review for the parent task
2. THE Review_Agent SHALL receive the complete context of all subtasks and their outputs
3. IF the review identifies issues, THEN THE Orchestrator SHALL mark the appropriate subtask(s) as fix_required
4. THE Orchestrator SHALL NOT dispatch separate reviews for individual subtasks
