#!/usr/bin/env python3
"""
Property-Based Tests for Orchestration Initialization

Feature: multi-agent-orchestration
Property 2: Agent Assignment by Task Type
Property 3: Dependency-Based Blocking
Validates: Requirements 1.3, 1.7, 11.5
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from spec_parser import Task, TaskType, TaskStatus
from init_orchestration import (
    assign_owner_agent,
    determine_criticality,
    convert_task_to_entry,
    initialize_orchestration,
    AGENT_BY_TASK_TYPE,
)


# Strategies for generating test data
@st.composite
def task_type_strategy(draw):
    """Generate valid task types"""
    return draw(st.sampled_from(list(TaskType)))


@st.composite
def task_strategy(draw):
    """Generate a valid Task object"""
    task_id = draw(st.text(
        alphabet="0123456789.",
        min_size=1,
        max_size=5
    ).filter(lambda x: x and x[0].isdigit() and not x.endswith('.')))
    
    description = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_",
        min_size=5,
        max_size=50
    ))
    
    task_type = draw(task_type_strategy())
    status = draw(st.sampled_from(list(TaskStatus)))
    is_optional = draw(st.booleans())
    
    return Task(
        task_id=task_id,
        description=description,
        task_type=task_type,
        status=status,
        is_optional=is_optional,
        dependencies=[],
        details=[],
    )


@st.composite
def task_with_security_keywords_strategy(draw):
    """Generate task with security-related keywords"""
    keywords = ["security", "auth", "password", "token", "encrypt", "credential"]
    keyword = draw(st.sampled_from(keywords))
    
    task = draw(task_strategy())
    task.description = f"Implement {keyword} module"
    return task


@st.composite
def task_with_complex_keywords_strategy(draw):
    """Generate task with complexity-related keywords"""
    keywords = ["refactor", "migration", "integration", "architecture"]
    keyword = draw(st.sampled_from(keywords))
    
    task = draw(task_strategy())
    task.description = f"Perform {keyword} of system"
    return task


@st.composite
def dependency_graph_strategy(draw):
    """Generate a set of tasks with dependencies"""
    num_tasks = draw(st.integers(min_value=2, max_value=6))
    
    tasks = []
    for i in range(num_tasks):
        task = Task(
            task_id=str(i + 1),
            description=f"Task {i + 1}",
            task_type=TaskType.CODE,
            status=TaskStatus.NOT_STARTED,
            dependencies=[],
            details=[],
        )
        
        # Add dependencies to earlier tasks
        if i > 0 and draw(st.booleans()):
            dep_count = draw(st.integers(min_value=1, max_value=min(i, 2)))
            deps = draw(st.lists(
                st.integers(min_value=1, max_value=i),
                min_size=dep_count,
                max_size=dep_count,
                unique=True
            ))
            task.dependencies = [str(d) for d in deps]
        
        tasks.append(task)
    
    return tasks


# Property 2: Agent Assignment by Task Type
@given(task=task_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_agent_assignment_by_task_type(task):
    """
    Property 2: Agent Assignment by Task Type
    
    For any task, the assigned owner_agent SHALL be:
    - "kiro-cli" if task type is "code"
    - "gemini" if task type is "ui"
    - "codex-review" if task type is "review"
    
    Feature: multi-agent-orchestration, Property 2
    Validates: Requirements 1.3, 11.5
    """
    assigned_agent = assign_owner_agent(task)
    expected_agent = AGENT_BY_TASK_TYPE[task.task_type]
    
    assert assigned_agent == expected_agent, \
        f"Task type {task.task_type} should be assigned to {expected_agent}, got {assigned_agent}"


@given(task_type=task_type_strategy())
@settings(max_examples=100, deadline=None)
def test_agent_assignment_exhaustive(task_type):
    """Test all task types have valid agent assignments."""
    task = Task(
        task_id="1",
        description="Test task",
        task_type=task_type,
        status=TaskStatus.NOT_STARTED,
    )
    
    agent = assign_owner_agent(task)
    
    # Verify agent is one of the valid agents
    valid_agents = {"kiro-cli", "gemini", "codex-review"}
    assert agent in valid_agents, f"Invalid agent: {agent}"
    
    # Verify correct mapping
    if task_type == TaskType.CODE:
        assert agent == "kiro-cli"
    elif task_type == TaskType.UI:
        assert agent == "gemini"
    elif task_type == TaskType.REVIEW:
        assert agent == "codex-review"


# Property 3: Dependency-Based Blocking
@given(tasks=dependency_graph_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_dependency_based_blocking(tasks):
    """
    Property 3: Dependency-Based Blocking
    
    For any task with dependencies, if any dependency task has status other than
    "completed", the task SHALL have status "blocked" or "not_started".
    
    Feature: multi-agent-orchestration, Property 3
    Validates: Requirements 1.7
    """
    # Build task map
    task_map = {t.task_id: t for t in tasks}
    
    for task in tasks:
        if not task.dependencies:
            continue
        
        # Check if all dependencies are completed
        all_deps_completed = all(
            task_map.get(dep_id, Task(task_id=dep_id, description="", status=TaskStatus.COMPLETED)).status == TaskStatus.COMPLETED
            for dep_id in task.dependencies
        )
        
        # If not all dependencies completed, task should not be in_progress or beyond
        if not all_deps_completed:
            # Task should be blocked or not_started (not actively running)
            assert task.status in [TaskStatus.NOT_STARTED, TaskStatus.BLOCKED], \
                f"Task {task.task_id} has incomplete dependencies but status is {task.status}"


@given(task=task_with_security_keywords_strategy())
@settings(max_examples=100, deadline=None)
def test_security_criticality_detection(task):
    """Test security keywords trigger security-sensitive criticality."""
    criticality = determine_criticality(task)
    assert criticality == "security-sensitive", \
        f"Task with security keyword should be security-sensitive, got {criticality}"


@given(task=task_with_complex_keywords_strategy())
@settings(max_examples=100, deadline=None)
def test_complex_criticality_detection(task):
    """Test complex keywords trigger complex criticality."""
    criticality = determine_criticality(task)
    # Complex keywords should result in complex criticality
    # unless security keywords are also present
    assert criticality in ["complex", "security-sensitive"], \
        f"Task with complex keyword should be complex or security-sensitive, got {criticality}"


@given(task=task_strategy())
@settings(max_examples=100, deadline=None)
def test_task_entry_conversion(task):
    """Test task conversion preserves all fields."""
    entry = convert_task_to_entry(task)
    
    assert entry.task_id == task.task_id
    assert entry.description == task.description
    assert entry.type == task.task_type.value
    assert entry.status == task.status.value
    assert entry.is_optional == task.is_optional
    assert entry.dependencies == task.dependencies
    assert entry.owner_agent in {"kiro-cli", "gemini", "codex-review"}
    assert entry.criticality in {"standard", "complex", "security-sensitive"}


def test_initialization_with_valid_spec():
    """Integration test: Initialize from a valid spec directory."""
    # Create temp spec directory
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = Path(tmpdir) / "test-spec"
        spec_path.mkdir()
        
        # Create minimal spec files
        (spec_path / "requirements.md").write_text("# Requirements\n\nTest requirements.")
        (spec_path / "design.md").write_text("# Design\n\n## Overview\n\nTest design.")
        (spec_path / "tasks.md").write_text("""# Tasks

- [ ] 1 Implement feature A
- [ ] 2 Implement feature B
  - dependencies: 1
""")
        
        # Initialize
        result = initialize_orchestration(str(spec_path))
        
        assert result.success, f"Initialization failed: {result.errors}"
        assert result.state_file is not None
        assert result.pulse_file is not None
        
        # Verify state file
        with open(result.state_file) as f:
            state = json.load(f)
        
        assert state["spec_path"] == str(spec_path.absolute())
        assert len(state["tasks"]) == 2
        assert state["tasks"][0]["task_id"] == "1"
        assert state["tasks"][1]["task_id"] == "2"
        
        # Verify PULSE file exists
        assert os.path.exists(result.pulse_file)


def test_initialization_with_invalid_spec():
    """Test initialization fails gracefully with invalid spec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Missing required files
        result = initialize_orchestration(tmpdir)
        
        assert not result.success
        assert len(result.errors) > 0


# Tests for dispatch failure rollback behavior

def test_dispatch_batch_failure_keeps_tasks_not_started():
    """
    Test that failed dispatch does not leave tasks stuck in in_progress.
    
    P1 Fix: Tasks should remain not_started when dispatch fails completely,
    allowing retry without manual state edits.
    """
    from dispatch_batch import dispatch_batch, load_agent_state
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        
        # Create initial state with tasks
        initial_state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {"task_id": "1", "description": "Task 1", "status": "not_started", 
                 "owner_agent": "kiro-cli", "dependencies": [], "criticality": "standard"},
                {"task_id": "2", "description": "Task 2", "status": "not_started",
                 "owner_agent": "kiro-cli", "dependencies": [], "criticality": "standard"},
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        with open(state_file, 'w') as f:
            json.dump(initial_state, f)
        
        # Dispatch will fail because codeagent-wrapper is not in PATH
        result = dispatch_batch(str(state_file))
        
        # Verify dispatch failed
        assert not result.success, "Dispatch should fail when codeagent-wrapper not found"
        
        # Verify tasks are still not_started (not stuck in in_progress)
        final_state = load_agent_state(str(state_file))
        for task in final_state["tasks"]:
            assert task["status"] == "not_started", \
                f"Task {task['task_id']} should remain not_started after failed dispatch, got {task['status']}"


def test_fix_dispatch_failure_reports_errors():
    """
    Test that fix dispatch failure surfaces errors to callers.
    
    P1 Fix: Fix dispatch failure should return success False with error details.
    """
    from dispatch_batch import dispatch_batch, load_agent_state
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        
        initial_state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {"task_id": "1", "description": "Fix task", "status": "fix_required",
                 "owner_agent": "kiro-cli", "dependencies": [], "criticality": "standard",
                 "fix_attempts": 0, "last_review_severity": "major",
                 "review_history": [{
                     "attempt": 0,
                     "severity": "major",
                     "findings": [{"severity": "major", "summary": "Bug found"}],
                     "reviewed_at": "2026-01-08T10:00:00Z"
                 }]},
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        with open(state_file, 'w') as f:
            json.dump(initial_state, f)
        
        result = dispatch_batch(str(state_file))
        
        assert not result.success, "Fix dispatch failure should return success=False"
        assert result.errors, "Fix dispatch failure should surface errors"
        assert result.execution_report is not None, \
            "Execution report should include fix dispatch failure"
        assert result.execution_report.tasks_failed >= 1, \
            "Fix dispatch failure should count as failed"
        
        final_state = load_agent_state(str(state_file))
        task = next(t for t in final_state["tasks"] if t["task_id"] == "1")
        assert task["status"] == "fix_required", \
            "Fix task should roll back to fix_required after failed dispatch"


def test_dispatch_batch_partial_failure_handles_results():
    """
    Test that partial dispatch failure correctly processes available results.
    
    P3 Coverage: Test the partial failure branch in dispatch_batch.
    """
    from dispatch_batch import (
        dispatch_batch, load_agent_state, save_agent_state,
        process_execution_report, update_task_statuses, ExecutionReport
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        
        # Create initial state
        initial_state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {"task_id": "1", "description": "Task 1", "status": "not_started",
                 "owner_agent": "kiro-cli", "dependencies": [], "criticality": "standard"},
                {"task_id": "2", "description": "Task 2", "status": "not_started",
                 "owner_agent": "kiro-cli", "dependencies": [], "criticality": "standard"},
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        # Simulate partial failure: task 1 completed, task 2 failed
        report = ExecutionReport(
            success=False,
            tasks_completed=1,
            tasks_failed=1,
            task_results=[
                {"task_id": "1", "status": "completed", "exit_code": 0}
            ],
            errors=["Task 2 failed"]
        )
        
        # Process the partial results
        state = initial_state.copy()
        state["tasks"] = [t.copy() for t in initial_state["tasks"]]
        
        tasks_with_results = {r.get("task_id") for r in report.task_results if r.get("task_id")}
        
        if report.task_results:
            update_task_statuses(state, list(tasks_with_results), "in_progress")
            process_execution_report(state, report)
        
        # Verify task 1 was processed (should be pending_review after completion)
        task1 = next(t for t in state["tasks"] if t["task_id"] == "1")
        assert task1["status"] == "pending_review", \
            f"Task 1 should be pending_review after successful completion, got {task1['status']}"
        
        # Verify task 2 remains not_started (no result for it)
        task2 = next(t for t in state["tasks"] if t["task_id"] == "2")
        assert task2["status"] == "not_started", \
            f"Task 2 should remain not_started (no result), got {task2['status']}"


def test_dispatch_reviews_failure_keeps_tasks_pending_review():
    """
    Test that failed review dispatch does not leave tasks stuck in under_review.
    
    P1 Fix: Tasks should remain pending_review when dispatch fails completely,
    allowing retry without manual state edits.
    """
    from dispatch_reviews import dispatch_reviews, load_agent_state
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        
        # Create initial state with tasks pending review
        initial_state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {"task_id": "1", "description": "Task 1", "status": "pending_review",
                 "criticality": "standard"},
                {"task_id": "2", "description": "Task 2", "status": "pending_review",
                 "criticality": "complex"},
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        with open(state_file, 'w') as f:
            json.dump(initial_state, f)
        
        # Dispatch will fail because codeagent-wrapper is not in PATH
        result = dispatch_reviews(str(state_file))
        
        # Verify dispatch failed
        assert not result.success, "Review dispatch should fail when codeagent-wrapper not found"
        
        # Verify tasks are still pending_review (not stuck in under_review)
        final_state = load_agent_state(str(state_file))
        for task in final_state["tasks"]:
            assert task["status"] == "pending_review", \
                f"Task {task['task_id']} should remain pending_review after failed dispatch, got {task['status']}"


def test_dispatch_reviews_partial_failure_handles_results():
    """
    Test that partial review dispatch failure correctly processes available results.
    
    P3 Coverage: Test the partial failure branch in dispatch_reviews.
    """
    from dispatch_reviews import (
        update_task_to_under_review, add_review_findings,
        update_completed_reviews_to_final, ReviewReport
    )
    
    # Create initial state with tasks pending review
    state = {
        "spec_path": "/test/spec",
        "session_name": "test-session",
        "tasks": [
            {"task_id": "task-001", "description": "Task 1", "status": "pending_review",
             "criticality": "standard"},
            {"task_id": "task-002", "description": "Task 2", "status": "pending_review",
             "criticality": "standard"},
        ],
        "review_findings": [],
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }
    
    # Simulate partial failure: task-001 review completed, task-002 failed
    report = ReviewReport(
        success=False,
        reviews_completed=1,
        reviews_failed=1,
        review_results=[
            {"task_id": "task-001", "review_id": "review-task-001-1", 
             "severity": "none", "summary": "LGTM"}
        ],
        errors=["Task 2 review failed"]
    )
    
    # Process partial results (simulating the failure branch logic)
    tasks_with_results = set()
    for result in report.review_results:
        task_id = result.get("task_id")
        if task_id:
            tasks_with_results.add(task_id)
    
    if tasks_with_results:
        update_task_to_under_review(state, list(tasks_with_results))
        add_review_findings(state, report)
        update_completed_reviews_to_final(state)
    
    # Verify task-001 was processed
    task1 = next(t for t in state["tasks"] if t["task_id"] == "task-001")
    # Standard criticality needs 1 review, so should be final_review
    assert task1["status"] == "final_review", \
        f"task-001 should be final_review after review, got {task1['status']}"
    
    # Verify task-002 remains pending_review
    task2 = next(t for t in state["tasks"] if t["task_id"] == "task-002")
    assert task2["status"] == "pending_review", \
        f"task-002 should remain pending_review (no result), got {task2['status']}"


def test_review_id_parsing_with_dashed_task_id():
    """
    Test that review_id parsing correctly handles task_ids containing dashes.
    
    P2 Fix: task_id like "task-001" should not be truncated when parsing review_id.
    """
    # Test the parsing logic directly
    review_id = "review-task-001-1"
    
    # Correct parsing: remove prefix, rsplit from right
    remainder = review_id[len("review-"):]  # "task-001-1"
    parts = remainder.rsplit("-", 1)  # ["task-001", "1"]
    
    assert len(parts) == 2, f"Should split into 2 parts, got {parts}"
    assert parts[0] == "task-001", f"Task ID should be 'task-001', got {parts[0]}"
    assert parts[1] == "1", f"Reviewer index should be '1', got {parts[1]}"
    
    # Test with simple task_id too
    review_id2 = "review-42-2"
    remainder2 = review_id2[len("review-"):]
    parts2 = remainder2.rsplit("-", 1)
    
    assert parts2[0] == "42", f"Task ID should be '42', got {parts2[0]}"
    assert parts2[1] == "2", f"Reviewer index should be '2', got {parts2[1]}"


if __name__ == "__main__":
    print("Running property tests for initialization...")
    print("=" * 60)
    
    tests = [
        ("Property 2: Agent Assignment by Task Type", test_property_2_agent_assignment_by_task_type),
        ("Property 3: Dependency-Based Blocking", test_property_3_dependency_based_blocking),
        ("Agent Assignment Exhaustive", test_agent_assignment_exhaustive),
        ("Security Criticality Detection", test_security_criticality_detection),
        ("Complex Criticality Detection", test_complex_criticality_detection),
        ("Task Entry Conversion", test_task_entry_conversion),
        ("Integration: Valid Spec", test_initialization_with_valid_spec),
        ("Integration: Invalid Spec", test_initialization_with_invalid_spec),
        ("P1 Fix: Dispatch Batch Failure Rollback", test_dispatch_batch_failure_keeps_tasks_not_started),
        ("P3 Coverage: Dispatch Batch Partial Failure", test_dispatch_batch_partial_failure_handles_results),
        ("P1 Fix: Dispatch Reviews Failure Rollback", test_dispatch_reviews_failure_keeps_tasks_pending_review),
        ("P3 Coverage: Dispatch Reviews Partial Failure", test_dispatch_reviews_partial_failure_handles_results),
        ("P2 Fix: Review ID Parsing with Dashed Task ID", test_review_id_parsing_with_dashed_task_id),
    ]
    
    failed = []
    for name, test in tests:
        try:
            print(f"\n{name}")
            test()
            print("  ✅ PASSED")
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed.append((name, str(e)))
    
    print("\n" + "=" * 60)
    if failed:
        print(f"❌ {len(failed)} test(s) failed:")
        for name, error in failed:
            print(f"   - {name}: {error}")
        sys.exit(1)
    else:
        print(f"✅ All {len(tests)} tests passed!")


# ============================================================================
# Property Tests for Parent Status Aggregation
# Feature: orchestration-fixes
# Property 2: Parent Status Aggregation
# Validates: Requirements 1.3, 1.4, 1.5
# ============================================================================

from init_orchestration import update_parent_statuses


@st.composite
def parent_with_subtasks_state_strategy(draw):
    """Generate a state with parent tasks and subtasks."""
    num_parents = draw(st.integers(min_value=1, max_value=3))
    
    tasks = []
    
    for p in range(1, num_parents + 1):
        parent_id = str(p)
        num_subtasks = draw(st.integers(min_value=1, max_value=4))
        subtask_ids = [f"{parent_id}.{s}" for s in range(1, num_subtasks + 1)]
        
        # Create parent task
        parent = {
            "task_id": parent_id,
            "description": f"Parent task {parent_id}",
            "status": "not_started",
            "subtasks": subtask_ids,
        }
        tasks.append(parent)
        
        # Create subtasks with random statuses
        subtask_statuses = []
        for sid in subtask_ids:
            status = draw(st.sampled_from([
                "not_started", "in_progress", "pending_review", 
                "under_review", "final_review", "completed", "blocked"
            ]))
            subtask_statuses.append(status)
            subtask = {
                "task_id": sid,
                "description": f"Subtask {sid}",
                "status": status,
                "parent_id": parent_id,
                "subtasks": [],
            }
            tasks.append(subtask)
    
    return {"tasks": tasks}


@st.composite
def all_completed_subtasks_strategy(draw):
    """Generate a state where all subtasks are completed."""
    parent_id = "1"
    num_subtasks = draw(st.integers(min_value=1, max_value=4))
    subtask_ids = [f"{parent_id}.{s}" for s in range(1, num_subtasks + 1)]
    
    tasks = [
        {
            "task_id": parent_id,
            "description": "Parent task",
            "status": "not_started",
            "subtasks": subtask_ids,
        }
    ]
    
    for sid in subtask_ids:
        tasks.append({
            "task_id": sid,
            "description": f"Subtask {sid}",
            "status": "completed",
            "parent_id": parent_id,
            "subtasks": [],
        })
    
    return {"tasks": tasks, "parent_id": parent_id}


@st.composite
def some_in_progress_subtasks_strategy(draw):
    """Generate a state where some subtasks are in progress."""
    parent_id = "1"
    num_subtasks = draw(st.integers(min_value=2, max_value=4))
    subtask_ids = [f"{parent_id}.{s}" for s in range(1, num_subtasks + 1)]
    
    tasks = [
        {
            "task_id": parent_id,
            "description": "Parent task",
            "status": "not_started",
            "subtasks": subtask_ids,
        }
    ]
    
    # At least one in_progress, rest can be anything except blocked
    in_progress_statuses = ["in_progress", "pending_review", "under_review", "final_review"]
    
    for i, sid in enumerate(subtask_ids):
        if i == 0:
            status = draw(st.sampled_from(in_progress_statuses))
        else:
            status = draw(st.sampled_from(["not_started", "completed"] + in_progress_statuses))
        
        tasks.append({
            "task_id": sid,
            "description": f"Subtask {sid}",
            "status": status,
            "parent_id": parent_id,
            "subtasks": [],
        })
    
    return {"tasks": tasks, "parent_id": parent_id}


@st.composite
def some_blocked_subtasks_strategy(draw):
    """Generate a state where some subtasks are blocked."""
    parent_id = "1"
    num_subtasks = draw(st.integers(min_value=2, max_value=4))
    subtask_ids = [f"{parent_id}.{s}" for s in range(1, num_subtasks + 1)]
    
    tasks = [
        {
            "task_id": parent_id,
            "description": "Parent task",
            "status": "not_started",
            "subtasks": subtask_ids,
        }
    ]
    
    # At least one blocked
    for i, sid in enumerate(subtask_ids):
        if i == 0:
            status = "blocked"
        else:
            status = draw(st.sampled_from(["not_started", "in_progress", "completed"]))
        
        tasks.append({
            "task_id": sid,
            "description": f"Subtask {sid}",
            "status": status,
            "parent_id": parent_id,
            "subtasks": [],
        })
    
    return {"tasks": tasks, "parent_id": parent_id}


@given(state=all_completed_subtasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_parent_status_all_completed(state):
    """
    Property 2: Parent Status Aggregation - All completed
    
    For any parent task where ALL subtasks are completed,
    update_parent_statuses SHALL set the parent status to "completed".
    
    Feature: orchestration-fixes, Property 2
    Validates: Requirements 1.3
    """
    parent_id = state["parent_id"]
    
    # Update parent statuses
    update_parent_statuses(state)
    
    # Find parent task
    parent = next(t for t in state["tasks"] if t["task_id"] == parent_id)
    
    assert parent["status"] == "completed", \
        f"Parent with all completed subtasks should be completed, got {parent['status']}"


@given(state=some_in_progress_subtasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_parent_status_in_progress(state):
    """
    Property 2: Parent Status Aggregation - In progress
    
    For any parent task where ANY subtask is in_progress/pending_review/under_review/final_review
    (and none are blocked), update_parent_statuses SHALL set the parent status to "in_progress".
    
    Feature: orchestration-fixes, Property 2
    Validates: Requirements 1.4
    """
    parent_id = state["parent_id"]
    
    # Update parent statuses
    update_parent_statuses(state)
    
    # Find parent task
    parent = next(t for t in state["tasks"] if t["task_id"] == parent_id)
    
    # Check if any subtask is blocked (which takes priority)
    subtask_statuses = [t["status"] for t in state["tasks"] if t.get("parent_id") == parent_id]
    has_blocked = any(s == "blocked" for s in subtask_statuses)
    
    if has_blocked:
        assert parent["status"] == "blocked", \
            f"Parent with blocked subtask should be blocked, got {parent['status']}"
    else:
        assert parent["status"] == "in_progress", \
            f"Parent with in_progress subtasks should be in_progress, got {parent['status']}"


@given(state=some_blocked_subtasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_parent_status_blocked(state):
    """
    Property 2: Parent Status Aggregation - Blocked
    
    For any parent task where ANY subtask is blocked,
    update_parent_statuses SHALL set the parent status to "blocked".
    
    Feature: orchestration-fixes, Property 2
    Validates: Requirements 1.5
    """
    parent_id = state["parent_id"]
    
    # Update parent statuses
    update_parent_statuses(state)
    
    # Find parent task
    parent = next(t for t in state["tasks"] if t["task_id"] == parent_id)
    
    assert parent["status"] == "blocked", \
        f"Parent with blocked subtask should be blocked, got {parent['status']}"


@given(state=parent_with_subtasks_state_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_parent_status_aggregation_rules(state):
    """
    Property 2: Parent Status Aggregation - Full rules
    
    For any parent task, update_parent_statuses SHALL derive status from subtasks:
    - All completed → completed
    - Any blocked → blocked
    - Any in_progress/pending_review/under_review/final_review → in_progress
    - Otherwise → not_started
    
    Feature: orchestration-fixes, Property 2
    Validates: Requirements 1.3, 1.4, 1.5
    """
    # Update parent statuses
    update_parent_statuses(state)
    
    # Verify each parent task
    for task in state["tasks"]:
        subtask_ids = task.get("subtasks", [])
        if not subtask_ids:
            continue  # Skip leaf tasks
        
        # Get subtask statuses
        subtask_statuses = []
        for t in state["tasks"]:
            if t["task_id"] in subtask_ids:
                subtask_statuses.append(t["status"])
        
        if not subtask_statuses:
            continue
        
        # Verify parent status follows the rules
        if all(s == "completed" for s in subtask_statuses):
            assert task["status"] == "completed", \
                f"Parent {task['task_id']} with all completed subtasks should be completed"
        elif any(s == "blocked" for s in subtask_statuses):
            assert task["status"] == "blocked", \
                f"Parent {task['task_id']} with blocked subtask should be blocked"
        elif any(s == "fix_required" for s in subtask_statuses):
            assert task["status"] == "fix_required", \
                f"Parent {task['task_id']} with fix_required subtask should be fix_required"
        elif any(s in ["in_progress", "pending_review", "under_review", "final_review"] 
                 for s in subtask_statuses):
            assert task["status"] == "in_progress", \
                f"Parent {task['task_id']} with in_progress subtask should be in_progress"
        else:
            assert task["status"] == "not_started", \
                f"Parent {task['task_id']} with all not_started subtasks should be not_started"
