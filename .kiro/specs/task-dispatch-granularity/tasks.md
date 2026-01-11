# Implementation Plan: Task Dispatch Granularity Optimization

## Overview

This implementation plan transforms the multi-agent orchestration system from leaf-task dispatch to parent-task dispatch. The changes are primarily in `spec_parser.py` and `dispatch_batch.py`, with updates to the payload format and status handling.

## Tasks

- [x] 1. Add Dispatch Unit Identification Functions
  - [x] 1.1 Implement `is_dispatch_unit()` function in spec_parser.py
    - Add function to check if a task is a dispatch unit (parent or standalone)
    - Return True for tasks with subtasks OR tasks with no parent and no subtasks
    - Return False for leaf tasks that have a parent
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 1.2 Write property test for dispatch unit identification
    - **Property 1: Dispatch Unit Selection**
    - **Validates: Requirements 1.1, 1.2, 1.3, 4.3**
  - [x] 1.3 Implement `get_dispatchable_units()` function in spec_parser.py
    - Replace `get_ready_tasks()` logic for dispatch unit selection
    - Return only parent tasks and standalone tasks with satisfied dependencies
    - Exclude leaf tasks that belong to a parent
    - _Requirements: 1.1, 1.2, 1.3, 4.3_

- [x] 2. Update Dispatch Payload Structure
  - [x] 2.1 Create `DispatchPayload` and `SubtaskInfo` dataclasses in dispatch_batch.py
    - Define payload structure with dispatch_unit_id, description, subtasks list
    - Include metadata fields (criticality, file manifests)
    - _Requirements: 5.1, 5.2_
  - [x] 2.2 Implement `build_dispatch_payload()` function
    - Build payload for parent tasks with all subtasks in sorted order
    - Build payload for standalone tasks as single-item work units
    - Include spec_path references
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 2.3 Write property test for payload structure
    - **Property 4: Payload Structure Completeness**
    - **Validates: Requirements 5.1, 5.2, 5.3**

- [x] 3. Modify Task Content/Prompt Generation
  - [x] 3.1 Update `build_task_content()` to use new payload format
    - Generate prompt with parent task overview
    - Include ordered subtask list with step numbers
    - Add instructions for sequential execution
    - _Requirements: 2.1, 2.2_
  - [x] 3.2 Update `TaskConfig` to support dispatch unit format
    - Modify heredoc format to include subtask information
    - Ensure backward compatibility with standalone tasks
    - _Requirements: 5.3_

- [x] 4. Update Ready Task Selection in dispatch_batch.py
  - [x] 4.1 Replace `get_ready_tasks()` with `get_dispatchable_units()` call    
    - Update dispatch_batch() to use new function
    - Ensure dependency expansion still works correctly
    - _Requirements: 4.1, 4.3, 4.4_
  - [x] 4.2 Write property test for dependency expansion
    - **Property 3: Dependency Expansion**
    - **Validates: Requirements 4.1, 4.4**

- [x] 5. Checkpoint - Core dispatch logic complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update Window Allocation Logic
  - [x] 6.1 Modify window allocation to use dispatch units
    - Allocate one window per dispatch unit (not per subtask)
    - Update `find_missing_dispatch_fields()` to check dispatch units only
    - _Requirements: 6.1, 6.2, 6.3_
  - [x] 6.2 Write property test for window allocation
    - **Property 5: Window Allocation Invariant**
    - **Validates: Requirements 6.1, 6.3**

- [x] 7. Update Status Tracking
  - [x] 7.1 Verify `update_parent_statuses()` handles new dispatch model        
    - Ensure parent status derivation works correctly
    - Test with various subtask status combinations
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [x] 7.2 Write property test for parent status derivation
    - **Property 2: Parent Status Derivation**
    - **Validates: Requirements 3.3, 3.4, 3.5**

- [x] 8. Update Review Dispatch Logic
  - [x] 8.1 Modify review dispatch to use dispatch units
    - Dispatch single review when all subtasks reach pending_review
    - Include all subtask outputs in review payload
    - _Requirements: 9.1, 9.2_
  - [x] 8.2 Write property test for review dispatch
    - **Property 6: Review Dispatch Consolidation**
    - **Validates: Requirements 9.1, 9.4**

- [x] 9. Implement Error Handling
  - [x] 9.1 Add `handle_partial_completion()` function
    - Preserve completed subtask results on failure
    - Mark failed subtask and parent as blocked
    - Record blocked_reason and blocked_by
    - _Requirements: 8.1, 8.2, 8.4_
  - [x] 9.2 Write property test for failure isolation
    - **Property 8: Subtask Failure Isolation**
    - **Validates: Requirements 8.2, 8.4**
  - [x] 9.3 Implement resume logic for unblocked subtasks
    - Resume from blocked subtask, not from beginning
    - Skip already completed subtasks
    - _Requirements: 8.3_

- [x] 10. Checkpoint - Error handling complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Backward Compatibility
  - [x] 11.1 Test with flat tasks.md (no hierarchy)
    - Verify each task treated as standalone dispatch unit
    - Verify behavior matches current implementation
    - _Requirements: 7.1, 7.2, 7.3_
  - [x] 11.2 Write property test for backward compatibility
    - **Property 7: Backward Compatibility - Flat Tasks**
    - **Validates: Requirements 7.1, 7.2**

- [x] 12. Update Exports and Documentation
  - [x] 12.1 Update `__init__.py` exports
    - Export new functions: `is_dispatch_unit`, `get_dispatchable_units`, `build_dispatch_payload`
    - Maintain backward compatibility for existing exports
    - _Requirements: 7.3_
  - [x] 12.2 Update SKILL.md documentation
    - Document new dispatch unit concept
    - Update workflow description
    - _Requirements: 7.3_

- [x] 13. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks including property-based tests are required
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
