 # Implementation Plan: Orchestration Fixes

## Overview

This implementation plan addresses three critical issues in the multi-agent orchestration system:
1. Parent-Subtask Execution Model - Only leaf tasks should be dispatched
2. File Conflict Detection - Prevent parallel tasks from modifying same files
3. Fix Loop Workflow - Retry mechanism for failed reviews

Implementation uses Python for orchestration scripts (consistent with existing codebase).

## Tasks

- [x] 1. Fix Parent-Subtask Execution Model
  - [x] 1.1 Update get_ready_tasks() to filter out parent tasks
    - Modify `spec_parser.py` to add `is_leaf_task()` helper
    - Update `get_ready_tasks()` to skip tasks with subtasks
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Write property test for leaf task filtering
    - **Property 1: Leaf Task Filtering**
    - **Validates: Requirements 1.1, 1.2**

  - [x] 1.3 Implement dependency expansion for parent tasks
    - Add `expand_dependencies()` function to `spec_parser.py`
    - Expand parent task IDs to their subtask IDs recursively
    - Update `get_ready_tasks()` to use expanded dependencies
    - _Requirements: 1.6, 1.7, 5.1, 5.2, 5.4_

  - [x] 1.4 Write property test for dependency expansion
    - **Property 3: Dependency Expansion**
    - **Validates: Requirements 1.6, 1.7, 5.1, 5.2, 5.4, 5.5**

  - [x] 1.5 Implement parent status aggregation
    - Add `update_parent_statuses()` function to `init_orchestration.py`
    - Derive parent status from subtask statuses
    - Call after each batch completion
    - _Requirements: 1.3, 1.4, 1.5_

  - [x] 1.6 Write property test for parent status aggregation
    - **Property 2: Parent Status Aggregation**
    - **Validates: Requirements 1.3, 1.4, 1.5**

- [x] 2. Checkpoint - Ensure parent-subtask model tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement File Conflict Detection
  - [x] 3.1 Add file manifest fields to Task dataclass
    - Add `writes: List[str]` and `reads: List[str]` fields to Task
    - Update `to_dict()` to include new fields
    - _Requirements: 2.1_

  - [x] 3.2 Implement file manifest parsing in spec_parser.py
    - Add `_extract_file_manifest()` function
    - Parse `_writes:` and `_reads:` markers from task details
    - Integrate into `parse_tasks()` function
    - _Requirements: 2.2_

  - [x] 3.3 Write property test for file manifest parsing
    - **Property 4: File Manifest Parsing**
    - **Validates: Requirements 2.2**

  - [x] 3.4 Implement file conflict detection
    - Add `FileConflict` dataclass to `dispatch_batch.py`
    - Add `detect_file_conflicts()` function
    - Add `partition_by_conflicts()` function for batch partitioning
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 3.5 Write property test for conflict-aware batching
    - **Property 5: Conflict-Aware Batching**
    - **Validates: Requirements 2.3, 2.4, 2.5, 2.6**

  - [x] 3.6 Integrate conflict detection into dispatch_batch.py
    - Update `dispatch_batch()` to use `partition_by_conflicts()`
    - Dispatch batches sequentially
    - Add logging for conflict warnings
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 4. Checkpoint - Ensure file conflict detection tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Fix Loop Workflow
  - [x] 5.1 Extend TaskStatus enum with fix_required
    - Add `FIX_REQUIRED = "fix_required"` to TaskStatus enum
    - Update `VALID_TRANSITIONS` to include fix_required transitions
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 5.2 Write property test for fix loop state transitions
    - **Property 8: Fix Loop State Transitions**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**

  - [x] 5.3 Extend Task dataclass with fix loop fields
    - Add `fix_attempts`, `escalated`, `escalated_at`, `original_agent` fields
    - Add `last_review_severity`, `review_history` fields
    - Add `blocked_reason`, `blocked_by` fields
    - _Requirements: 3.10_

  - [x] 5.4 Implement fix loop entry and blocking
    - Create `fix_loop.py` module
    - Add `enter_fix_loop()` function
    - Add `get_all_dependent_task_ids()` with transitive closure
    - Add `block_dependent_tasks()` function
    - _Requirements: 3.1, 3.2_

  - [x] 5.5 Write property test for fix loop entry
    - **Property 6: Fix Loop Entry**
    - **Validates: Requirements 3.1, 3.2**

  - [x] 5.6 Implement fix loop action evaluation
    - Add `FixLoopAction` enum
    - Add `evaluate_fix_loop_action()` function
    - Implement escalation threshold (2 completed attempts)
    - Implement human fallback threshold (3 completed attempts)
    - _Requirements: 3.3, 3.6, 3.7_

  - [x] 5.7 Write property test for fix loop retry budget
    - **Property 7: Fix Loop Retry Budget**
    - **Validates: Requirements 3.3, 3.6, 3.7, 3.8, 3.9**

  - [x] 5.8 Implement fix request creation and prompt building
    - Add `FixRequest` dataclass
    - Add `create_fix_request()` function
    - Add `build_fix_prompt()` function with history for escalation
    - Add `format_review_history()` function
    - _Requirements: 3.4, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 5.9 Write property test for fix prompt content
    - **Property 9: Fix Prompt Content**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

  - [x] 5.10 Implement fix loop scheduling
    - Add `get_fix_required_tasks()` function
    - Add `process_fix_loop()` function
    - Add `on_fix_task_complete()` function
    - Add `on_review_complete()` function
    - _Requirements: 4.6, 3.5_

  - [x] 5.11 Implement unblock and success handling
    - Add `unblock_dependent_tasks()` function
    - Add `handle_fix_loop_success()` function
    - _Requirements: 3.9_

  - [x] 5.12 Implement human fallback
    - Add `trigger_human_fallback()` function
    - Create pending_decision entry with context
    - Block dependent tasks
    - _Requirements: 3.7, 3.8_

- [x] 6. Checkpoint - Ensure fix loop tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Integration and wiring
  - [x] 7.1 Integrate parent status updates into orchestration flow
    - Call `update_parent_statuses()` after each batch in `dispatch_batch.py`
    - _Requirements: 1.3, 1.4, 1.5_

  - [x] 7.2 Integrate fix loop into review dispatch flow
    - Update `dispatch_reviews.py` to call `on_review_complete()`
    - Update `consolidate_reviews.py` to trigger fix loop on critical/major
    - _Requirements: 3.1, 4.6_

  - [x] 7.3 Update agent-state-schema.json
    - Add new task fields (writes, reads, fix_attempts, etc.)
    - Add fix_required to status enum
    - Update review_history structure
    - _Requirements: All_

  - [x] 7.4 Write integration test for full fix loop workflow
    - Test initial review failure → fix → re-review → success
    - Test escalation after 2 failures
    - Test human fallback after 3 failures
    - _Requirements: All fix loop requirements_

- [x] 8. Final checkpoint - Full system verification
  - Ensure all tests pass, ask the user if questions arise.
  - Verify parent-subtask model works correctly
  - Verify file conflict detection prevents parallel conflicts
  - Verify fix loop workflow handles all scenarios

- [x] 9. Fix Integration Gaps (Audit Findings)
  - [x] 9.1 Fix dispatch_batch.py to use leaf task filtering and dependency expansion
    - Replace local `get_ready_tasks()` with import from `spec_parser.py`
    - Or reimplement using `is_leaf_task()` and `expand_dependencies()` from spec_parser
    - Ensure parent tasks are never dispatched
    - _Requirements: 1.1, 1.2, 1.6, 1.7_
    - _writes: skills/multi-agent-orchestrator/scripts/dispatch_batch.py_

  - [x] 9.2 Fix init_orchestration.py to preserve all Task fields in AGENT_STATE
    - Update `TaskEntry` dataclass to include `subtasks`, `parent_id`, `writes`, `reads`
    - Update `convert_task_to_entry()` to copy these fields from parsed Task
    - Ensure `update_parent_statuses()` can find subtask relationships
    - _Requirements: 1.3, 1.4, 1.5, 2.1, 2.2_
    - _writes: skills/multi-agent-orchestrator/scripts/init_orchestration.py_

  - [x] 9.3 Integrate fix loop dispatch into dispatch_batch.py
    - Add call to `process_fix_loop()` before getting ready tasks
    - Handle `fix_required` status tasks alongside `not_started` tasks
    - Dispatch fix requests returned by `process_fix_loop()`
    - _Requirements: 3.1, 4.6_
    - _writes: skills/multi-agent-orchestrator/scripts/dispatch_batch.py_

  - [x] 9.4 Write integration test for full dispatch chain
    - Test that parent tasks are never dispatched
    - Test that subtasks/parent_id/writes/reads are preserved in AGENT_STATE
    - Test that fix_required tasks are processed by fix loop
    - _Requirements: All_
    - _writes: skills/multi-agent-orchestrator/scripts/test_dispatch_integration.py_

- [x] 10. Checkpoint - Verify audit findings are resolved
  - Run all tests to ensure fixes work correctly
  - Verify parent tasks are filtered out in dispatch
  - Verify file manifest data flows through to conflict detection
  - Verify fix loop is called during dispatch

- [x] 11. Fix Critical Fix Loop Gaps (New Findings)
  - [x] 11.1 Add on_fix_task_complete call after fix task execution
    - Update `dispatch_batch.py` to call `on_fix_task_complete()` when fix task completes
    - Ensure `fix_attempts` is incremented after each completed fix attempt
    - Add callback mechanism or explicit call in fix task dispatch flow
    - _Requirements: 7.1, 7.2, 7.3, 7.6_
    - _writes: skills/multi-agent-orchestrator/scripts/dispatch_batch.py, skills/multi-agent-orchestrator/scripts/fix_loop.py_

  - [x] 11.2 Add rollback on fix task dispatch failure
    - Update `process_fix_loop()` to handle dispatch failures
    - Rollback task status from `in_progress` to `fix_required` on failure
    - Ensure `fix_attempts` is NOT incremented on dispatch failure
    - _Requirements: 7.4, 7.5_
    - _writes: skills/multi-agent-orchestrator/scripts/fix_loop.py_

  - [x] 11.3 Write property test for fix_attempts increment
    - **Property 11: Fix Attempts Increment**
    - Test that fix_attempts only increments after successful fix completion
    - Test that dispatch failure does not increment fix_attempts
    - **Validates: Requirements 7.1, 7.4, 7.5, 7.6**

  - [x] 11.4 Ensure update_parent_statuses runs after all dispatch paths
    - Move `update_parent_statuses()` call to end of dispatch cycle using try/finally
    - Ensure it runs even when only fix tasks are dispatched
    - Ensure it runs even when dispatch returns early with no ready tasks
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
    - _writes: skills/multi-agent-orchestrator/scripts/dispatch_batch.py_

  - [x] 11.5 Write integration test for fix loop completion flow
    - Test fix task dispatch → completion → fix_attempts increment → re-review
    - Test dispatch failure → rollback → retry
    - Test escalation triggers at correct fix_attempts count
    - Test human fallback triggers at correct fix_attempts count
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 12. Final Checkpoint - Verify all fix loop gaps resolved
  - Run all tests including new property tests
  - Verify fix_attempts increments correctly after fix completion
  - Verify dispatch failure rolls back status correctly
  - Verify update_parent_statuses runs in all dispatch paths

## Notes

- Implementation uses Python with hypothesis for property-based testing
- All changes are to existing files in `skills/multi-agent-orchestrator/scripts/`
- New `fix_loop.py` module contains fix loop specific logic
- Property tests should run minimum 100 iterations

