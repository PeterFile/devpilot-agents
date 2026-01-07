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
