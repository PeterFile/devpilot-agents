#!/usr/bin/env python3
"""
Property-Based Tests for Review Dispatch

Feature: multi-agent-orchestration
Property 8: Review Count by Criticality
Property 9: Review Pane Placement
Validates: Requirements 8.2, 8.5, 8.6
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dispatch_reviews import (
    get_review_count,
    build_review_content,
    build_review_configs,
    get_tasks_pending_review,
    REVIEW_COUNT_BY_CRITICALITY,
    ReviewTaskConfig,
)


# Strategies for generating test data
@st.composite
def criticality_strategy(draw):
    """Generate valid criticality levels"""
    return draw(st.sampled_from(["standard", "complex", "security-sensitive"]))


@st.composite
def task_pending_review_strategy(draw):
    """Generate a task in pending_review status"""
    task_id = draw(st.text(
        alphabet="0123456789",
        min_size=1,
        max_size=3
    ).filter(lambda x: x and x[0] != '0'))
    
    criticality = draw(criticality_strategy())
    
    files_changed = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz/._", min_size=5, max_size=30),
        min_size=0,
        max_size=5
    ))
    
    return {
        "task_id": task_id,
        "description": f"Task {task_id} description",
        "status": "pending_review",
        "criticality": criticality,
        "files_changed": files_changed,
        "output": f"Implementation output for task {task_id}",
    }


@st.composite
def agent_state_with_pending_reviews_strategy(draw):
    """Generate agent state with tasks pending review"""
    num_tasks = draw(st.integers(min_value=1, max_value=5))
    
    tasks = []
    used_ids = set()
    
    for _ in range(num_tasks):
        task = draw(task_pending_review_strategy())
        # Ensure unique IDs
        while task["task_id"] in used_ids:
            task["task_id"] = str(int(task["task_id"]) + 100)
        used_ids.add(task["task_id"])
        tasks.append(task)
    
    return {
        "spec_path": "/test/spec",
        "session_name": "test-session",
        "tasks": tasks,
        "review_findings": [],
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }


@st.composite
def parent_with_pending_subtasks_strategy(draw):
    """Generate a parent task with all subtasks pending_review."""
    parent_id = str(draw(st.integers(min_value=1, max_value=9)))
    num_subtasks = draw(st.integers(min_value=1, max_value=4))
    subtask_ids = [f"{parent_id}.{i}" for i in range(1, num_subtasks + 1)]

    parent = {
        "task_id": parent_id,
        "description": f"Parent {parent_id}",
        "status": "in_progress",
        "subtasks": subtask_ids,
        "parent_id": None,
        "criticality": draw(criticality_strategy()),
    }

    subtasks = []
    for sid in subtask_ids:
        subtasks.append({
            "task_id": sid,
            "description": f"Subtask {sid}",
            "status": "pending_review",
            "parent_id": parent_id,
            "subtasks": [],
            "files_changed": draw(st.lists(st.text(alphabet="abc/._", min_size=3, max_size=10), min_size=0, max_size=3)),
            "output": f"Output for {sid}",
        })

    state = {
        "spec_path": "/test/spec",
        "session_name": "test-session",
        "tasks": [parent] + subtasks,
        "review_findings": [],
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }

    return {"state": state, "parent_id": parent_id, "subtask_ids": subtask_ids}


# Property 8: Review Count by Criticality
@given(criticality=criticality_strategy())
@settings(max_examples=100, deadline=None)
def test_property_8_review_count_by_criticality(criticality):
    """
    Property 8: Review Count by Criticality
    
    For any task transitioning to "pending_review":
    - If criticality is "standard", exactly 1 Review_Codex SHALL be spawned
    - If criticality is "complex" or "security-sensitive", at least 2 Review_Codex instances SHALL be spawned
    
    Feature: multi-agent-orchestration, Property 8
    Validates: Requirements 8.5, 8.6
    """
    task = {
        "task_id": "1",
        "description": "Test task",
        "status": "pending_review",
        "criticality": criticality,
    }
    
    review_count = get_review_count(task)
    expected_count = REVIEW_COUNT_BY_CRITICALITY[criticality]
    
    assert review_count == expected_count, \
        f"Criticality {criticality} should have {expected_count} reviews, got {review_count}"
    
    # Verify the specific requirements
    if criticality == "standard":
        assert review_count == 1, "Standard tasks should have exactly 1 reviewer"
    else:
        assert review_count >= 2, f"{criticality} tasks should have at least 2 reviewers"


@given(task=task_pending_review_strategy())
@settings(max_examples=100, deadline=None)
def test_review_configs_match_criticality(task):
    """Test that review configs are generated according to criticality."""
    tasks = [task]
    configs = build_review_configs(tasks, "/test/spec", ".", all_tasks=tasks)
    
    expected_count = REVIEW_COUNT_BY_CRITICALITY[task["criticality"]]
    
    assert len(configs) == expected_count, \
        f"Expected {expected_count} review configs for {task['criticality']}, got {len(configs)}"
    
    # Verify all configs reference the correct task
    for config in configs:
        assert config.task_id == task["task_id"]
        assert config.backend == "codex"


# Property 9: Review Pane Placement
@given(task=task_pending_review_strategy())
@settings(max_examples=100, deadline=None)
def test_property_9_review_pane_placement(task):
    """
    Property 9: Review Pane Placement
    
    For any Review_Codex instance, it SHALL be placed in a new pane within
    the same window as the task being reviewed.
    
    This is verified by checking that review configs have the task_id as dependency,
    which tells codeagent-wrapper to place the review in the task's window.
    
    Feature: multi-agent-orchestration, Property 9
    Validates: Requirements 8.2
    """
    tasks = [task]
    configs = build_review_configs(tasks, "/test/spec", ".", all_tasks=tasks)
    
    for config in configs:
        # Review should depend on the task (for window placement)
        heredoc = config.to_heredoc()
        assert f"dependencies: {task['task_id']}" in heredoc, \
            f"Review config should have task {task['task_id']} as dependency for window placement"


@given(state=agent_state_with_pending_reviews_strategy())
@settings(max_examples=100, deadline=None)
def test_all_pending_tasks_get_reviews(state):
    """Test that all pending_review tasks get review configs."""
    pending_tasks = get_tasks_pending_review(state)
    configs = build_review_configs(pending_tasks, state["spec_path"], ".", all_tasks=state["tasks"])
    
    # Count expected reviews
    expected_total = sum(
        REVIEW_COUNT_BY_CRITICALITY[t["criticality"]]
        for t in pending_tasks
    )
    
    assert len(configs) == expected_total, \
        f"Expected {expected_total} total reviews, got {len(configs)}"
    
    # Verify each task has correct number of reviews
    for task in pending_tasks:
        task_reviews = [c for c in configs if c.task_id == task["task_id"]]
        expected = REVIEW_COUNT_BY_CRITICALITY[task["criticality"]]
        assert len(task_reviews) == expected, \
            f"Task {task['task_id']} should have {expected} reviews, got {len(task_reviews)}"


@given(state=agent_state_with_pending_reviews_strategy())
@settings(max_examples=100, deadline=None)
def test_review_ids_are_unique(state):
    """Test that all review IDs are unique."""
    pending_tasks = get_tasks_pending_review(state)
    configs = build_review_configs(pending_tasks, state["spec_path"], ".", all_tasks=state["tasks"])
    
    review_ids = [c.review_id for c in configs]
    assert len(review_ids) == len(set(review_ids)), \
        "Review IDs should be unique"


@given(task=task_pending_review_strategy())
@settings(max_examples=100, deadline=None)
def test_review_content_includes_task_info(task):
    """Test that review content includes necessary task information."""
    tasks = [task]
    configs = build_review_configs(tasks, "/test/spec", ".", all_tasks=tasks)
    
    for config in configs:
        content = config.content
        
        # Should include task ID
        assert task["task_id"] in content, "Review content should include task ID"
        
        # Should include reference to spec files
        assert "requirements.md" in content, "Review content should reference requirements"
        assert "design.md" in content, "Review content should reference design"
        
        # Should include severity options
        assert "critical" in content.lower(), "Review content should mention severity levels"


def test_review_content_includes_subtask_outputs():
    """Test that review content includes subtask outputs for parent tasks."""
    state = {
        "tasks": [
            {"task_id": "1", "description": "Parent", "status": "in_progress", "subtasks": ["1.1"]},
            {"task_id": "1.1", "description": "Subtask 1.1", "status": "pending_review",
             "parent_id": "1", "subtasks": [], "output": "Subtask output", "files_changed": ["file.txt"]},
        ]
    }
    parent = state["tasks"][0]
    content = build_review_content(parent, "/test/spec", 1, all_tasks=state["tasks"])

    assert "Subtask Outputs" in content
    assert "Subtask output" in content


def test_standard_criticality_single_review():
    """Test standard criticality gets exactly 1 review."""
    task = {
        "task_id": "1",
        "description": "Standard task",
        "status": "pending_review",
        "criticality": "standard",
    }
    
    configs = build_review_configs([task], "/test/spec", ".", all_tasks=[task])
    assert len(configs) == 1
    assert configs[0].reviewer_index == 1


def test_complex_criticality_multiple_reviews():
    """Test complex criticality gets 2+ reviews."""
    task = {
        "task_id": "1",
        "description": "Complex task",
        "status": "pending_review",
        "criticality": "complex",
    }
    
    configs = build_review_configs([task], "/test/spec", ".", all_tasks=[task])
    assert len(configs) >= 2
    
    # Verify reviewer indices
    indices = [c.reviewer_index for c in configs]
    assert indices == list(range(1, len(configs) + 1))


def test_security_sensitive_criticality_multiple_reviews():
    """Test security-sensitive criticality gets 2+ reviews."""
    task = {
        "task_id": "1",
        "description": "Security task",
        "status": "pending_review",
        "criticality": "security-sensitive",
    }
    
    configs = build_review_configs([task], "/test/spec", ".", all_tasks=[task])
    assert len(configs) >= 2


def test_get_tasks_pending_review_filters_correctly():
    """Test that only pending_review tasks are returned."""
    state = {
        "tasks": [
            {"task_id": "1", "status": "not_started"},
            {"task_id": "2", "status": "in_progress"},
            {"task_id": "3", "status": "pending_review", "criticality": "standard"},
            {"task_id": "4", "status": "completed"},
            {"task_id": "5", "status": "pending_review", "criticality": "complex"},
        ]
    }

    pending = get_tasks_pending_review(state)

    assert len(pending) == 2
    assert all(t["status"] == "pending_review" for t in pending)
    assert {t["task_id"] for t in pending} == {"3", "5"}


@given(data=parent_with_pending_subtasks_strategy())
@settings(max_examples=100, deadline=None)
def test_parent_with_all_pending_subtasks_is_reviewed(data):
    """Parent task is dispatched for review when all subtasks are pending_review."""
    state = data["state"]
    pending = get_tasks_pending_review(state)
    pending_ids = {t["task_id"] for t in pending}

    assert data["parent_id"] in pending_ids
    for sid in data["subtask_ids"]:
        assert sid not in pending_ids


def test_parent_with_partial_pending_subtasks_not_reviewed():
    """Parent task is not reviewed if any subtask is not pending_review."""
    state = {
        "tasks": [
            {"task_id": "1", "description": "Parent", "status": "in_progress", "subtasks": ["1.1", "1.2"]},
            {"task_id": "1.1", "description": "Subtask 1.1", "status": "pending_review", "parent_id": "1", "subtasks": []},
            {"task_id": "1.2", "description": "Subtask 1.2", "status": "completed", "parent_id": "1", "subtasks": []},
        ]
    }

    pending = get_tasks_pending_review(state)
    pending_ids = {t["task_id"] for t in pending}

    assert "1" not in pending_ids


def test_review_dispatch_consolidates_parent_only():
    """Ensure reviews are dispatched only for parent task, not individual subtasks."""
    state = {
        "spec_path": "/test/spec",
        "session_name": "test-session",
        "tasks": [
            {"task_id": "1", "description": "Parent", "status": "in_progress", "subtasks": ["1.1", "1.2"], "criticality": "standard"},
            {"task_id": "1.1", "description": "Subtask 1.1", "status": "pending_review", "parent_id": "1", "subtasks": []},
            {"task_id": "1.2", "description": "Subtask 1.2", "status": "pending_review", "parent_id": "1", "subtasks": []},
        ],
        "review_findings": [],
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }

    pending = get_tasks_pending_review(state)
    configs = build_review_configs(pending, state["spec_path"], ".", all_tasks=state["tasks"])

    assert configs, "Expected review configs for parent task"
    assert all(c.task_id == "1" for c in configs), "Reviews should target only the parent task"


if __name__ == "__main__":
    print("Running property tests for review dispatch...")
    print("=" * 60)
    
    tests = [
        ("Property 8: Review Count by Criticality", test_property_8_review_count_by_criticality),
        ("Property 9: Review Pane Placement", test_property_9_review_pane_placement),
        ("Review Configs Match Criticality", test_review_configs_match_criticality),
        ("All Pending Tasks Get Reviews", test_all_pending_tasks_get_reviews),
        ("Review IDs Are Unique", test_review_ids_are_unique),
        ("Review Content Includes Task Info", test_review_content_includes_task_info),
        ("Standard Criticality Single Review", test_standard_criticality_single_review),
        ("Complex Criticality Multiple Reviews", test_complex_criticality_multiple_reviews),
        ("Security-Sensitive Multiple Reviews", test_security_sensitive_criticality_multiple_reviews),
        ("Get Tasks Pending Review Filters", test_get_tasks_pending_review_filters_correctly),
        ("Parent Pending Review Dispatch", test_parent_with_all_pending_subtasks_is_reviewed),
        ("Parent Partial Pending Not Reviewed", test_parent_with_partial_pending_subtasks_not_reviewed),
        ("Review Dispatch Consolidates Parent Only", test_review_dispatch_consolidates_parent_only),
        ("Review Content Includes Subtask Outputs", test_review_content_includes_subtask_outputs),
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
