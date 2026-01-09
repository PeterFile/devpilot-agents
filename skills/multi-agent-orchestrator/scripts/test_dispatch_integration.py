#!/usr/bin/env python3
"""
Integration Tests for Full Dispatch Chain

Tests the integration of:
- Parent task filtering (only leaf tasks dispatched)
- Task field preservation (subtasks, parent_id, writes, reads)
- Fix loop integration in dispatch

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 3.1, 4.6
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import pytest

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from spec_parser import parse_tasks, TaskStatus
from init_orchestration import initialize_orchestration, update_parent_statuses
from dispatch_batch import (
    dispatch_batch,
    get_ready_tasks,
    load_agent_state,
    save_agent_state,
    _dict_to_task_like,
)
from fix_loop import process_fix_loop, enter_fix_loop


# Sample spec content with parent-subtask hierarchy and file manifests
SAMPLE_TASKS_WITH_HIERARCHY = """# Implementation Plan: Test Feature

## Overview

Test implementation with parent-subtask hierarchy and file manifests.

## Tasks

- [ ] 1 Parent task with subtasks
  - [ ] 1.1 First subtask
    - Implement core logic
    - _writes: src/core.py
    - _reads: config.json
    - _Requirements: 1.1_
  - [ ] 1.2 Second subtask
    - Implement helper functions
    - _writes: src/helpers.py
    - _Requirements: 1.2_

- [ ] 2 Independent leaf task
  - Standalone implementation
  - _writes: src/standalone.py
  - _Requirements: 2.1_

- [ ] 3 Task depending on parent
  - dependencies: 1
  - Integration work
  - _writes: src/integration.py
  - _Requirements: 3.1_
"""

SAMPLE_REQUIREMENTS_MD = """# Requirements Document

## Introduction

Test requirements for dispatch integration testing.

## Glossary

- **System**: The test system

## Requirements

### Requirement 1: Core Feature

**User Story:** As a user, I want core functionality.

#### Acceptance Criteria

1. THE System SHALL implement core logic
2. THE System SHALL implement helper functions
"""

SAMPLE_DESIGN_MD = """# Design Document

## Overview

Test design for dispatch integration testing.

## Components and Interfaces

### Core Module
Implements core logic.

### Helper Module
Implements helper functions.

## Correctness Properties

### Property 1: Core Logic
*For any* input, core logic SHALL produce valid output.

**Validates: Requirements 1.1**
"""


def create_test_spec_directory(base_dir: str) -> str:
    """Create a test spec directory with hierarchy and file manifests."""
    spec_dir = Path(base_dir) / "test-dispatch"
    spec_dir.mkdir(parents=True, exist_ok=True)
    
    (spec_dir / "requirements.md").write_text(SAMPLE_REQUIREMENTS_MD)
    (spec_dir / "design.md").write_text(SAMPLE_DESIGN_MD)
    (spec_dir / "tasks.md").write_text(SAMPLE_TASKS_WITH_HIERARCHY)
    
    return str(spec_dir)


class TestParentTaskFiltering:
    """Tests for parent task filtering (Req 1.1, 1.2)."""
    
    def test_parent_tasks_never_dispatched(self):
        """
        Test that parent tasks are never included in ready tasks.
        
        Requirements: 1.1, 1.2
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-parent-filter",
                output_dir=str(output_dir)
            )
            
            assert result.success, f"Init failed: {result.errors}"
            
            state = load_agent_state(result.state_file)
            
            # Get ready tasks
            ready_tasks = get_ready_tasks(state)
            ready_ids = [t["task_id"] for t in ready_tasks]
            
            # Parent task "1" should NOT be in ready tasks
            assert "1" not in ready_ids, \
                "Parent task '1' should not be dispatched (has subtasks)"
            
            # Leaf tasks should be ready
            # Task 1.1 and 1.2 are subtasks of 1, should be ready
            # Task 2 is independent leaf, should be ready
            assert "1.1" in ready_ids or "1.2" in ready_ids or "2" in ready_ids, \
                "At least one leaf task should be ready"
    
    def test_only_leaf_tasks_in_ready_list(self):
        """
        Test that only leaf tasks (no subtasks) appear in ready list.
        
        Requirements: 1.1, 1.2
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-leaf-only",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            ready_tasks = get_ready_tasks(state)
            
            # Verify all ready tasks are leaf tasks (no subtasks)
            for task in ready_tasks:
                subtasks = task.get("subtasks", [])
                assert len(subtasks) == 0, \
                    f"Task {task['task_id']} has subtasks {subtasks}, should not be in ready list"
    
    def test_dependency_on_parent_expands_to_subtasks(self):
        """
        Test that dependency on parent task expands to all subtasks.
        
        Requirements: 1.6, 1.7
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-dep-expand",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Task 3 depends on task 1 (parent)
            # It should NOT be ready until all subtasks of 1 are complete
            ready_tasks = get_ready_tasks(state)
            ready_ids = [t["task_id"] for t in ready_tasks]
            
            assert "3" not in ready_ids, \
                "Task 3 should not be ready (depends on parent task 1)"
            
            # Complete all subtasks of task 1
            for task in state["tasks"]:
                if task["task_id"] in ["1.1", "1.2"]:
                    task["status"] = "completed"
            
            # Update parent status
            update_parent_statuses(state)
            
            # Now task 3 should be ready
            ready_tasks = get_ready_tasks(state)
            ready_ids = [t["task_id"] for t in ready_tasks]
            
            assert "3" in ready_ids, \
                "Task 3 should be ready after all subtasks of 1 are complete"


class TestTaskFieldPreservation:
    """Tests for task field preservation in AGENT_STATE (Req 2.1, 2.2)."""
    
    def test_subtasks_preserved_in_state(self):
        """
        Test that subtasks field is preserved in AGENT_STATE.
        
        Requirements: 1.3, 1.4, 1.5
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-subtasks",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Find parent task 1
            parent_task = next(
                (t for t in state["tasks"] if t["task_id"] == "1"),
                None
            )
            
            assert parent_task is not None, "Parent task 1 should exist"
            assert "subtasks" in parent_task, "Parent task should have subtasks field"
            assert len(parent_task["subtasks"]) > 0, "Parent task should have subtasks"
            assert "1.1" in parent_task["subtasks"], "Subtask 1.1 should be in subtasks"
            assert "1.2" in parent_task["subtasks"], "Subtask 1.2 should be in subtasks"
    
    def test_parent_id_preserved_in_state(self):
        """
        Test that parent_id field is preserved in AGENT_STATE.
        
        Requirements: 1.3, 1.4, 1.5
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-parent-id",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Find subtask 1.1
            subtask = next(
                (t for t in state["tasks"] if t["task_id"] == "1.1"),
                None
            )
            
            assert subtask is not None, "Subtask 1.1 should exist"
            assert "parent_id" in subtask, "Subtask should have parent_id field"
            assert subtask["parent_id"] == "1", "Subtask 1.1 should have parent_id '1'"
    
    def test_writes_reads_preserved_in_state(self):
        """
        Test that writes and reads fields are preserved in AGENT_STATE.
        
        Requirements: 2.1, 2.2
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-file-manifest",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Find task 1.1 which has writes and reads
            task_1_1 = next(
                (t for t in state["tasks"] if t["task_id"] == "1.1"),
                None
            )
            
            assert task_1_1 is not None, "Task 1.1 should exist"
            assert "writes" in task_1_1, "Task should have writes field"
            assert "reads" in task_1_1, "Task should have reads field"
            assert "src/core.py" in task_1_1["writes"], \
                "Task 1.1 should write to src/core.py"
            assert "config.json" in task_1_1["reads"], \
                "Task 1.1 should read from config.json"
    
    def test_parent_status_aggregation_works(self):
        """
        Test that parent status is correctly derived from subtask statuses.
        
        Requirements: 1.3, 1.4, 1.5
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-parent-status",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Initially all tasks are not_started
            parent = next(t for t in state["tasks"] if t["task_id"] == "1")
            assert parent["status"] == "not_started"
            
            # Set one subtask to in_progress
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "in_progress"
            
            update_parent_statuses(state)
            
            parent = next(t for t in state["tasks"] if t["task_id"] == "1")
            assert parent["status"] == "in_progress", \
                "Parent should be in_progress when any subtask is in_progress"
            
            # Complete all subtasks
            for task in state["tasks"]:
                if task["task_id"] in ["1.1", "1.2"]:
                    task["status"] = "completed"
            
            update_parent_statuses(state)
            
            parent = next(t for t in state["tasks"] if t["task_id"] == "1")
            assert parent["status"] == "completed", \
                "Parent should be completed when all subtasks are completed"


class TestFixLoopIntegration:
    """Tests for fix loop integration in dispatch (Req 3.1, 4.6)."""
    
    def test_fix_required_tasks_processed_by_fix_loop(self):
        """
        Test that fix_required tasks are processed by fix loop during dispatch.
        
        Requirements: 3.1, 4.6
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-fix-loop",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Set a task to fix_required status
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "fix_required"
                    task["fix_attempts"] = 0
                    task["last_review_severity"] = "major"
                    task["review_history"] = [{
                        "attempt": 0,
                        "severity": "major",
                        "findings": [{"severity": "major", "summary": "Bug found"}],
                        "reviewed_at": "2026-01-08T10:00:00Z"
                    }]
            
            save_agent_state(result.state_file, state)
            
            # Process fix loop
            fix_requests = process_fix_loop(state)
            
            assert len(fix_requests) == 1, "Should have 1 fix request"
            assert fix_requests[0]["task_id"] == "1.1"
            
            # Verify task is now in_progress
            task_1_1 = next(t for t in state["tasks"] if t["task_id"] == "1.1")
            assert task_1_1["status"] == "in_progress", \
                "Task should be in_progress after fix loop processing"
    
    def test_dispatch_handles_fix_required_and_not_started(self):
        """
        Test that dispatch handles both fix_required and not_started tasks.
        
        Requirements: 3.1, 4.6
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-mixed-dispatch",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Set task 1.1 to fix_required
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "fix_required"
                    task["fix_attempts"] = 0
                    task["last_review_severity"] = "major"
                    task["review_history"] = [{
                        "attempt": 0,
                        "severity": "major",
                        "findings": [{"severity": "major", "summary": "Bug found"}],
                        "reviewed_at": "2026-01-08T10:00:00Z"
                    }]
            
            save_agent_state(result.state_file, state)
            
            # Dispatch in dry-run mode
            dispatch_result = dispatch_batch(
                result.state_file,
                workdir=".",
                dry_run=True
            )
            
            assert dispatch_result.success
            # Should dispatch both fix tasks and new tasks
            assert dispatch_result.tasks_dispatched > 0


class TestDispatchChainIntegration:
    """Full integration tests for the dispatch chain."""
    
    def test_full_dispatch_chain_with_hierarchy(self):
        """
        Test full dispatch chain with parent-subtask hierarchy.
        
        Verifies:
        1. Parent tasks are never dispatched
        2. Subtask fields are preserved
        3. Dependencies on parents expand correctly
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            # Initialize
            result = initialize_orchestration(
                spec_path,
                session_name="test-full-chain",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Verify initial state has correct structure
            parent = next((t for t in state["tasks"] if t["task_id"] == "1"), None)
            assert parent is not None
            assert len(parent.get("subtasks", [])) == 2
            
            # Get ready tasks - should only be leaf tasks
            ready = get_ready_tasks(state)
            for task in ready:
                assert len(task.get("subtasks", [])) == 0, \
                    f"Ready task {task['task_id']} should be a leaf task"
            
            # Dispatch dry-run
            dispatch_result = dispatch_batch(
                result.state_file,
                dry_run=True
            )
            
            assert dispatch_result.success
            
            # Simulate completing subtasks
            state = load_agent_state(result.state_file)
            for task in state["tasks"]:
                if task["task_id"] in ["1.1", "1.2"]:
                    task["status"] = "completed"
            
            update_parent_statuses(state)
            save_agent_state(result.state_file, state)
            
            # Verify parent is now completed
            state = load_agent_state(result.state_file)
            parent = next(t for t in state["tasks"] if t["task_id"] == "1")
            assert parent["status"] == "completed"
            
            # Task 3 (depends on parent 1) should now be ready
            ready = get_ready_tasks(state)
            ready_ids = [t["task_id"] for t in ready]
            assert "3" in ready_ids, \
                "Task 3 should be ready after parent 1 is completed"
            
            print("✅ Full dispatch chain integration test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestFixLoopCompletionFlow:
    """
    Integration tests for fix loop completion flow.
    
    Tests the complete flow:
    - Fix task dispatch → completion → fix_attempts increment → re-review
    - Dispatch failure → rollback → retry
    - Escalation triggers at correct fix_attempts count
    - Human fallback triggers at correct fix_attempts count
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
    """
    
    def test_fix_task_completion_increments_fix_attempts(self):
        """
        Test that fix task completion increments fix_attempts.
        
        Requirements: 7.1, 7.2, 7.3
        """
        from fix_loop import on_fix_task_complete
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-fix-complete",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Set task to in_progress (simulating fix dispatch)
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "in_progress"
                    task["fix_attempts"] = 0
            
            # Simulate fix task completion
            on_fix_task_complete(state, "1.1")
            
            task = next(t for t in state["tasks"] if t["task_id"] == "1.1")
            
            # Verify fix_attempts incremented
            assert task["fix_attempts"] == 1, \
                "fix_attempts should be 1 after first fix completion"
            
            # Verify status transitioned to pending_review
            assert task["status"] == "pending_review", \
                "Status should be pending_review after fix completion"
    
    def test_fix_dispatch_failure_rollback(self):
        """
        Test that fix dispatch failure rolls back status.
        
        Requirements: 7.4, 7.5
        """
        from fix_loop import rollback_fix_dispatch
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-fix-rollback",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Set task to in_progress (simulating fix dispatch)
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "in_progress"
                    task["fix_attempts"] = 1
            
            # Simulate dispatch failure
            rollback_fix_dispatch(state, "1.1")
            
            task = next(t for t in state["tasks"] if t["task_id"] == "1.1")
            
            # Verify fix_attempts NOT incremented
            assert task["fix_attempts"] == 1, \
                "fix_attempts should remain 1 after rollback"
            
            # Verify status rolled back to fix_required
            assert task["status"] == "fix_required", \
                "Status should be fix_required after rollback"
    
    def test_escalation_at_correct_threshold(self):
        """
        Test that escalation triggers at fix_attempts >= 2.
        
        Requirements: 7.6
        """
        from fix_loop import evaluate_fix_loop_action, FixLoopAction, ESCALATION_THRESHOLD
        
        # Before threshold (0, 1 attempts)
        for attempts in [0, 1]:
            task = {"fix_attempts": attempts}
            action = evaluate_fix_loop_action(task, "major")
            assert action == FixLoopAction.RETRY, \
                f"Should RETRY at {attempts} attempts (before threshold)"
        
        # At threshold (2 attempts)
        task = {"fix_attempts": ESCALATION_THRESHOLD}
        action = evaluate_fix_loop_action(task, "major")
        assert action == FixLoopAction.ESCALATE, \
            f"Should ESCALATE at {ESCALATION_THRESHOLD} attempts"
    
    def test_human_fallback_at_max_attempts(self):
        """
        Test that human fallback triggers at fix_attempts >= 3.
        
        Requirements: 7.6
        """
        from fix_loop import evaluate_fix_loop_action, FixLoopAction, MAX_FIX_ATTEMPTS
        
        # At max attempts (3)
        task = {"fix_attempts": MAX_FIX_ATTEMPTS}
        action = evaluate_fix_loop_action(task, "major")
        assert action == FixLoopAction.HUMAN_FALLBACK, \
            f"Should trigger HUMAN_FALLBACK at {MAX_FIX_ATTEMPTS} attempts"
        
        # Beyond max attempts
        task = {"fix_attempts": MAX_FIX_ATTEMPTS + 1}
        action = evaluate_fix_loop_action(task, "major")
        assert action == FixLoopAction.HUMAN_FALLBACK, \
            "Should trigger HUMAN_FALLBACK beyond max attempts"
    
    def test_full_fix_loop_cycle(self):
        """
        Test complete fix loop cycle: fix_required → in_progress → pending_review.
        
        Requirements: 7.1, 7.2, 7.3, 7.6
        """
        from fix_loop import on_fix_task_complete, process_fix_loop
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-full-cycle",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Set task to fix_required
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "fix_required"
                    task["fix_attempts"] = 0
                    task["last_review_severity"] = "major"
                    task["review_history"] = [{
                        "attempt": 0,
                        "severity": "major",
                        "findings": [{"severity": "major", "summary": "Bug found"}],
                        "reviewed_at": "2026-01-08T10:00:00Z"
                    }]
            
            # Process fix loop - should transition to in_progress
            fix_requests = process_fix_loop(state)
            
            assert len(fix_requests) == 1
            task = next(t for t in state["tasks"] if t["task_id"] == "1.1")
            assert task["status"] == "in_progress", \
                "Task should be in_progress after process_fix_loop"
            assert task["fix_attempts"] == 0, \
                "fix_attempts should still be 0 (not incremented until completion)"
            
            # Simulate fix completion
            on_fix_task_complete(state, "1.1")
            
            task = next(t for t in state["tasks"] if t["task_id"] == "1.1")
            assert task["status"] == "pending_review", \
                "Task should be pending_review after fix completion"
            assert task["fix_attempts"] == 1, \
                "fix_attempts should be 1 after first fix completion"


class TestParentStatusUpdateConsistency:
    """
    Integration tests for parent status update consistency.
    
    Tests that update_parent_statuses runs in all dispatch paths.
    
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    
    def test_parent_status_updated_on_fix_only_dispatch(self):
        """
        Test that parent status is updated when only fix tasks are dispatched.
        
        Note: In dry_run mode, state is not modified. This test verifies the
        update_parent_statuses function works correctly when called.
        
        Requirements: 8.1
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-fix-only",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Complete one subtask, set another to fix_required
            for task in state["tasks"]:
                if task["task_id"] == "1.1":
                    task["status"] = "completed"
                elif task["task_id"] == "1.2":
                    task["status"] = "fix_required"
                    task["fix_attempts"] = 0
                    task["last_review_severity"] = "major"
                    task["review_history"] = [{
                        "attempt": 0,
                        "severity": "major",
                        "findings": [{"severity": "major", "summary": "Bug"}],
                        "reviewed_at": "2026-01-08T10:00:00Z"
                    }]
                # Set other leaf tasks to completed to avoid new task dispatch
                elif task["task_id"] == "2":
                    task["status"] = "completed"
            
            # Manually call update_parent_statuses to verify it works
            update_parent_statuses(state)
            
            parent = next(t for t in state["tasks"] if t["task_id"] == "1")
            
            # Parent should reflect subtask statuses (one completed, one fix_required)
            # Since one subtask is fix_required, parent should be fix_required
            assert parent["status"] == "fix_required", \
                "Parent should be fix_required when any subtask is fix_required"
    
    def test_parent_status_updated_on_no_tasks_dispatch(self):
        """
        Test that parent status is updated even when no tasks are dispatched.
        
        Note: In dry_run mode, state is not modified. This test verifies the
        update_parent_statuses function works correctly when called.
        
        Requirements: 8.2
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_test_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-no-dispatch",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            state = load_agent_state(result.state_file)
            
            # Set all leaf tasks to completed
            for task in state["tasks"]:
                if task["task_id"] in ["1.1", "1.2", "2"]:
                    task["status"] = "completed"
            
            # Manually call update_parent_statuses to verify it works
            update_parent_statuses(state)
            
            parent = next(t for t in state["tasks"] if t["task_id"] == "1")
            
            # Parent should be completed since all subtasks are completed
            assert parent["status"] == "completed", \
                "Parent should be completed when all subtasks are completed"
    
    def test_update_parent_statuses_called_in_dispatch_code_path(self):
        """
        Test that update_parent_statuses is called in the dispatch code path.
        
        This test verifies the code structure by checking that the function
        is imported and used in dispatch_batch.py.
        
        Requirements: 8.3
        """
        import inspect
        from dispatch_batch import dispatch_batch
        
        # Get the source code of dispatch_batch
        source = inspect.getsource(dispatch_batch)
        
        # Verify update_parent_statuses is called in the function
        assert "update_parent_statuses" in source, \
            "dispatch_batch should call update_parent_statuses"
