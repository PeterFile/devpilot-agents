#!/usr/bin/env python3
"""
Backward Compatibility Tests for Task Dispatch Granularity

Feature: task-dispatch-granularity
Task 11.1: Test with flat tasks.md (no hierarchy)
Validates: Requirements 7.1, 7.2, 7.3

These tests verify that the system correctly handles tasks.md files
containing only flat tasks (no parent-subtask hierarchy), ensuring
backward compatibility with existing workflows.
"""

import pytest
from typing import List, Dict, Any, Set

from spec_parser import (
    Task,
    TaskStatus,
    parse_tasks,
    extract_dependencies,
    is_dispatch_unit,
    is_leaf_task,
    get_dispatchable_units,
    get_ready_tasks,
    expand_dependencies,
)
from dispatch_batch import (
    get_dispatchable_units_from_state,
    build_dispatch_payload,
    build_task_content,
    allocate_windows,
    apply_window_allocation,
    _build_standalone_task_content,
)


# ============================================================================
# Test Fixtures: Flat tasks.md content (no hierarchy)
# ============================================================================

FLAT_TASKS_MD_SIMPLE = """
# Implementation Plan: Simple Feature

## Tasks

- [ ] 1 Set up project structure
  - Create directory layout
  - Initialize configuration files
  - _Requirements: 1.1_

- [ ] 2 Implement core functionality
  - Write main logic
  - Add error handling
  - _Requirements: 1.2, 1.3_

- [ ] 3 Write unit tests
  - Test core functions
  - Test edge cases
  - _Requirements: 2.1_

- [ ] 4 Update documentation
  - Add README
  - Document API
  - _Requirements: 3.1_
"""

FLAT_TASKS_MD_WITH_STATUSES = """
# Tasks

- [x] 1 Completed task
  - Already done

- [-] 2 In progress task
  - Currently working

- [ ] 3 Not started task
  - Waiting to start

- [~] 4 Blocked task
  - Waiting on external dependency
"""

FLAT_TASKS_MD_WITH_DEPENDENCIES = """
# Tasks

- [ ] 1 First task
  - No dependencies
  - _Requirements: 1.1_

- [ ] 2 Second task
  - depends on: 1
  - _Requirements: 1.2_

- [ ] 3 Third task
  - depends on: 1, 2
  - _Requirements: 1.3_

- [ ] 4 Independent task
  - No dependencies
  - _Requirements: 2.1_
"""

FLAT_TASKS_MD_WITH_OPTIONAL = """
# Tasks

- [ ] 1 Required task
  - Must complete

- [ ]* 2 Optional task
  - Can skip

- [ ] 3 Another required task
  - Must complete
"""


# ============================================================================
# Task 11.1: Test with flat tasks.md (no hierarchy)
# ============================================================================

class TestFlatTasksParsing:
    """Test parsing of flat tasks.md files."""

    def test_parse_flat_tasks_simple(self):
        """
        Verify flat tasks are parsed correctly.
        
        Requirements: 7.1, 7.3
        """
        result = parse_tasks(FLAT_TASKS_MD_SIMPLE)
        
        assert result.success, f"Parse failed: {result.errors}"
        assert len(result.tasks) == 4
        
        # Verify task IDs
        task_ids = {t.task_id for t in result.tasks}
        assert task_ids == {"1", "2", "3", "4"}
        
        # Verify no parent-subtask relationships
        for task in result.tasks:
            assert task.parent_id is None, f"Task {task.task_id} should have no parent"
            assert len(task.subtasks) == 0, f"Task {task.task_id} should have no subtasks"

    def test_parse_flat_tasks_with_statuses(self):
        """
        Verify status markers are correctly parsed for flat tasks.
        
        Requirements: 7.1, 7.3
        """
        result = parse_tasks(FLAT_TASKS_MD_WITH_STATUSES)
        
        assert result.success
        task_map = {t.task_id: t for t in result.tasks}
        
        assert task_map["1"].status == TaskStatus.COMPLETED
        assert task_map["2"].status == TaskStatus.IN_PROGRESS
        assert task_map["3"].status == TaskStatus.NOT_STARTED
        assert task_map["4"].status == TaskStatus.BLOCKED

    def test_parse_flat_tasks_with_optional(self):
        """
        Verify optional markers are correctly parsed for flat tasks.
        
        Requirements: 7.1, 7.3
        """
        result = parse_tasks(FLAT_TASKS_MD_WITH_OPTIONAL)
        
        assert result.success
        task_map = {t.task_id: t for t in result.tasks}
        
        assert not task_map["1"].is_optional
        assert task_map["2"].is_optional
        assert not task_map["3"].is_optional


class TestFlatTasksDispatchUnitIdentification:
    """Test that flat tasks are correctly identified as dispatch units."""

    def test_flat_tasks_are_dispatch_units(self):
        """
        Verify each flat task is treated as a standalone dispatch unit.
        
        Requirements: 7.1
        """
        result = parse_tasks(FLAT_TASKS_MD_SIMPLE)
        assert result.success
        
        for task in result.tasks:
            assert is_dispatch_unit(task), \
                f"Flat task {task.task_id} should be a dispatch unit"

    def test_flat_tasks_are_leaf_tasks(self):
        """
        Verify flat tasks are also leaf tasks (no subtasks).
        
        Requirements: 7.1
        """
        result = parse_tasks(FLAT_TASKS_MD_SIMPLE)
        assert result.success
        
        for task in result.tasks:
            assert is_leaf_task(task), \
                f"Flat task {task.task_id} should be a leaf task"

    def test_get_dispatchable_units_returns_all_flat_tasks(self):
        """
        Verify get_dispatchable_units returns all flat tasks when ready.
        
        Requirements: 7.1, 7.2
        """
        result = parse_tasks(FLAT_TASKS_MD_SIMPLE)
        assert result.success
        
        # With no completed tasks, all should be dispatchable
        dispatchable = get_dispatchable_units(result.tasks, set())
        dispatchable_ids = {t.task_id for t in dispatchable}
        
        expected_ids = {t.task_id for t in result.tasks}
        assert dispatchable_ids == expected_ids, \
            f"All flat tasks should be dispatchable, got {dispatchable_ids}"


class TestFlatTasksDependencies:
    """Test dependency handling for flat tasks."""

    def test_flat_tasks_dependency_extraction(self):
        """
        Verify dependencies are correctly extracted from flat tasks.
        
        Requirements: 7.2
        """
        result = parse_tasks(FLAT_TASKS_MD_WITH_DEPENDENCIES)
        assert result.success
        
        # Extract dependencies from task details
        extract_dependencies(result.tasks)
        
        task_map = {t.task_id: t for t in result.tasks}
        
        # Task 1 has no dependencies
        assert task_map["1"].dependencies == []
        
        # Task 2 depends on 1
        assert "1" in task_map["2"].dependencies
        
        # Task 3 depends on 1 and 2
        assert "1" in task_map["3"].dependencies
        assert "2" in task_map["3"].dependencies
        
        # Task 4 has no dependencies
        assert task_map["4"].dependencies == []

    def test_flat_tasks_dependency_expansion_unchanged(self):
        """
        Verify expand_dependencies returns flat task IDs unchanged.
        
        Requirements: 7.2
        """
        result = parse_tasks(FLAT_TASKS_MD_WITH_DEPENDENCIES)
        assert result.success
        
        # Extract dependencies from task details
        extract_dependencies(result.tasks)
        
        task_map = {t.task_id: t for t in result.tasks}
        
        # Expanding a flat task dependency should return it unchanged
        expanded = expand_dependencies(["1"], task_map)
        assert expanded == ["1"]
        
        expanded = expand_dependencies(["1", "2"], task_map)
        assert set(expanded) == {"1", "2"}

    def test_flat_tasks_ready_respects_dependencies(self):
        """
        Verify get_dispatchable_units respects dependencies for flat tasks.
        
        Requirements: 7.2
        """
        result = parse_tasks(FLAT_TASKS_MD_WITH_DEPENDENCIES)
        assert result.success
        
        # Extract dependencies from task details
        extract_dependencies(result.tasks)
        
        # With no completions, only tasks without dependencies are ready
        dispatchable = get_dispatchable_units(result.tasks, set())
        dispatchable_ids = {t.task_id for t in dispatchable}
        
        assert "1" in dispatchable_ids, "Task 1 (no deps) should be ready"
        assert "4" in dispatchable_ids, "Task 4 (no deps) should be ready"
        assert "2" not in dispatchable_ids, "Task 2 (deps on 1) should not be ready"
        assert "3" not in dispatchable_ids, "Task 3 (deps on 1,2) should not be ready"
        
        # After completing task 1, task 2 becomes ready
        dispatchable = get_dispatchable_units(result.tasks, {"1"})
        dispatchable_ids = {t.task_id for t in dispatchable}
        
        assert "2" in dispatchable_ids, "Task 2 should be ready after 1 completes"
        assert "3" not in dispatchable_ids, "Task 3 still needs 2"
        
        # After completing tasks 1 and 2, task 3 becomes ready
        dispatchable = get_dispatchable_units(result.tasks, {"1", "2"})
        dispatchable_ids = {t.task_id for t in dispatchable}
        
        assert "3" in dispatchable_ids, "Task 3 should be ready after 1,2 complete"


class TestFlatTasksDispatchPayload:
    """Test dispatch payload generation for flat tasks."""

    def test_flat_task_payload_single_item(self):
        """
        Verify flat task payload contains task as single work item.
        
        Requirements: 7.1, 7.3
        """
        dispatch_unit = {
            "task_id": "1",
            "description": "Set up project structure",
            "details": ["Create directory layout", "Initialize configuration"],
        }
        all_tasks = [dispatch_unit]
        
        payload = build_dispatch_payload(dispatch_unit, all_tasks, "specs/test")
        
        assert payload.dispatch_unit_id == "1"
        assert payload.description == "Set up project structure"
        assert len(payload.subtasks) == 1
        assert payload.subtasks[0].task_id == "1"
        assert payload.subtasks[0].description == "Set up project structure"

    def test_flat_task_content_standalone_format(self):
        """
        Verify flat task content uses standalone format (not dispatch unit format).
        
        Requirements: 7.1, 7.3
        """
        task = {
            "task_id": "1",
            "description": "Set up project structure",
            "type": "code",
            "details": ["Create directory layout", "Initialize configuration"],
        }
        
        content = build_task_content(task, "specs/test", all_tasks=[task])
        
        # Should use standalone format (starts with "Task:")
        assert content.startswith("Task:"), \
            "Flat task should use standalone content format"
        assert "Task Group:" not in content, \
            "Flat task should not use dispatch unit format"
        assert "Subtasks (Execute in Order)" not in content, \
            "Flat task should not have subtasks section"


class TestFlatTasksWindowAllocation:
    """Test window allocation for flat tasks."""

    def test_flat_tasks_one_window_each(self):
        """
        Verify each flat task gets exactly one window.
        
        Requirements: 7.1
        """
        dispatch_units = [
            {"task_id": "1", "description": "Task 1"},
            {"task_id": "2", "description": "Task 2"},
            {"task_id": "3", "description": "Task 3"},
        ]
        
        mapping = allocate_windows(dispatch_units, max_windows=10)
        
        assert len(mapping) == 3
        assert set(mapping.keys()) == {"1", "2", "3"}
        # Each task should have a unique window
        assert len(set(mapping.values())) == 3


class TestFlatTasksStateIntegration:
    """Test flat tasks with AGENT_STATE.json format."""

    def test_get_dispatchable_units_from_state_flat_tasks(self):
        """
        Verify get_dispatchable_units_from_state works with flat tasks.
        
        Requirements: 7.1, 7.2
        """
        state = {
            "spec_path": "specs/test",
            "tasks": [
                {
                    "task_id": "1",
                    "description": "First task",
                    "status": "not_started",
                    "subtasks": [],
                    "parent_id": None,
                    "dependencies": [],
                    "owner_agent": "kiro-cli",
                    "target_window": "task-1",
                },
                {
                    "task_id": "2",
                    "description": "Second task",
                    "status": "not_started",
                    "subtasks": [],
                    "parent_id": None,
                    "dependencies": ["1"],
                    "owner_agent": "kiro-cli",
                    "target_window": "task-2",
                },
                {
                    "task_id": "3",
                    "description": "Third task",
                    "status": "not_started",
                    "subtasks": [],
                    "parent_id": None,
                    "dependencies": [],
                    "owner_agent": "kiro-cli",
                    "target_window": "task-3",
                },
            ]
        }
        
        # Get dispatchable units
        ready = get_dispatchable_units_from_state(state)
        ready_ids = {t["task_id"] for t in ready}
        
        # Tasks 1 and 3 should be ready (no dependencies)
        assert "1" in ready_ids
        assert "3" in ready_ids
        # Task 2 should not be ready (depends on 1)
        assert "2" not in ready_ids

    def test_flat_tasks_completed_excluded(self):
        """
        Verify completed flat tasks are excluded from dispatch.
        
        Requirements: 7.2
        """
        state = {
            "spec_path": "specs/test",
            "tasks": [
                {
                    "task_id": "1",
                    "description": "Completed task",
                    "status": "completed",
                    "subtasks": [],
                    "parent_id": None,
                    "dependencies": [],
                },
                {
                    "task_id": "2",
                    "description": "Not started task",
                    "status": "not_started",
                    "subtasks": [],
                    "parent_id": None,
                    "dependencies": [],
                },
            ]
        }
        
        ready = get_dispatchable_units_from_state(state)
        ready_ids = {t["task_id"] for t in ready}
        
        assert "1" not in ready_ids, "Completed task should not be dispatchable"
        assert "2" in ready_ids, "Not started task should be dispatchable"


class TestFlatTasksBehaviorMatchesCurrent:
    """
    Test that flat tasks behavior matches current (pre-dispatch-granularity) implementation.
    
    This ensures backward compatibility - existing workflows continue to work.
    """

    def test_flat_tasks_get_ready_tasks_matches_get_dispatchable_units(self):
        """
        Verify get_ready_tasks and get_dispatchable_units return same results for flat tasks.
        
        For flat tasks (no hierarchy), both functions should return the same set of tasks.
        This ensures backward compatibility.
        
        Requirements: 7.1, 7.2
        """
        result = parse_tasks(FLAT_TASKS_MD_WITH_DEPENDENCIES)
        assert result.success
        
        # Extract dependencies from task details
        extract_dependencies(result.tasks)
        
        # Test with various completion states
        for completed in [set(), {"1"}, {"1", "4"}, {"1", "2", "4"}]:
            ready_old = get_ready_tasks(result.tasks, completed)
            ready_new = get_dispatchable_units(result.tasks, completed)
            
            old_ids = {t.task_id for t in ready_old}
            new_ids = {t.task_id for t in ready_new}
            
            assert old_ids == new_ids, \
                f"For completed={completed}: get_ready_tasks={old_ids} != get_dispatchable_units={new_ids}"

    def test_flat_tasks_no_subtask_grouping(self):
        """
        Verify flat tasks are not grouped into parent-subtask relationships.
        
        Requirements: 7.1
        """
        result = parse_tasks(FLAT_TASKS_MD_SIMPLE)
        assert result.success
        
        for task in result.tasks:
            # No task should have subtasks
            assert len(task.subtasks) == 0
            # No task should have a parent
            assert task.parent_id is None


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================================
# Property-Based Tests for Backward Compatibility
# Feature: task-dispatch-granularity
# Property 7: Backward Compatibility - Flat Tasks
# Validates: Requirements 7.1, 7.2
# ============================================================================

import string
from hypothesis import given, strategies as st, settings, assume


@st.composite
def flat_task_id_strategy(draw):
    """Generate valid flat task IDs (no dots - single level)."""
    return str(draw(st.integers(min_value=1, max_value=100)))


@st.composite
def flat_task_description_strategy(draw):
    """Generate valid task descriptions."""
    chars = string.ascii_letters + string.digits + " -_.,;:()"
    desc = draw(st.text(alphabet=chars, min_size=5, max_size=60)).strip()
    # Ensure description doesn't start with special characters
    if not desc or desc[0] in "-*#":
        desc = "Task " + desc
    return desc


@st.composite
def flat_task_status_strategy(draw):
    """Generate valid task status markers."""
    return draw(st.sampled_from([
        ("[ ]", TaskStatus.NOT_STARTED),
        ("[x]", TaskStatus.COMPLETED),
        ("[-]", TaskStatus.IN_PROGRESS),
        ("[~]", TaskStatus.BLOCKED),
    ]))


@st.composite
def single_flat_task_strategy(draw):
    """Generate a single flat task (no hierarchy)."""
    task_id = draw(flat_task_id_strategy())
    status_marker, expected_status = draw(flat_task_status_strategy())
    is_optional = draw(st.booleans())
    description = draw(flat_task_description_strategy())
    
    optional_marker = "*" if is_optional else ""
    task_line = f"- {status_marker}{optional_marker} {task_id} {description}"
    
    return {
        "task_id": task_id,
        "description": description,
        "status": expected_status,
        "is_optional": is_optional,
        "task_line": task_line,
    }


@st.composite
def flat_tasks_md_strategy(draw):
    """Generate valid flat tasks.md content (no hierarchy)."""
    num_tasks = draw(st.integers(min_value=1, max_value=8))
    
    lines = ["# Tasks", ""]
    expected_tasks = []
    used_ids = set()
    
    for _ in range(num_tasks):
        task_data = draw(single_flat_task_strategy())
        
        # Ensure unique ID
        base_id = task_data["task_id"]
        task_id = base_id
        counter = 1
        while task_id in used_ids:
            task_id = str(int(base_id) + counter * 100)
            counter += 1
        used_ids.add(task_id)
        
        # Update task data with unique ID
        status_markers = {
            TaskStatus.NOT_STARTED: "[ ]",
            TaskStatus.COMPLETED: "[x]",
            TaskStatus.IN_PROGRESS: "[-]",
            TaskStatus.BLOCKED: "[~]",
        }
        optional = "*" if task_data["is_optional"] else ""
        task_data["task_id"] = task_id
        task_data["task_line"] = f"- {status_markers[task_data['status']]}{optional} {task_id} {task_data['description']}"
        
        lines.append(task_data["task_line"])
        lines.append("")
        expected_tasks.append(task_data)
    
    return {"content": "\n".join(lines), "expected_tasks": expected_tasks}


@st.composite
def flat_tasks_with_deps_strategy(draw):
    """Generate flat tasks with dependencies between them."""
    num_tasks = draw(st.integers(min_value=2, max_value=6))
    
    lines = ["# Tasks", ""]
    task_ids = [str(i + 1) for i in range(num_tasks)]
    task_data_list = []
    
    for i, task_id in enumerate(task_ids):
        description = draw(flat_task_description_strategy())
        
        # Generate dependencies (only on earlier tasks to avoid cycles)
        possible_deps = task_ids[:i]
        if possible_deps:
            num_deps = draw(st.integers(min_value=0, max_value=min(2, len(possible_deps))))
            deps = draw(st.lists(
                st.sampled_from(possible_deps),
                min_size=num_deps,
                max_size=num_deps,
                unique=True
            ))
        else:
            deps = []
        
        task_line = f"- [ ] {task_id} {description}"
        lines.append(task_line)
        
        if deps:
            lines.append(f"  - depends on: {', '.join(deps)}")
        
        lines.append("")
        
        task_data_list.append({
            "task_id": task_id,
            "description": description,
            "dependencies": deps,
        })
    
    return {
        "content": "\n".join(lines),
        "tasks": task_data_list,
        "task_ids": task_ids,
    }


# ============================================================================
# Property 7: Backward Compatibility - Flat Tasks
# ============================================================================

@given(data=flat_tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_flat_tasks_all_dispatch_units(data):
    """
    Property 7: Backward Compatibility - All flat tasks are dispatch units
    
    For any tasks.md containing only flat tasks (no hierarchy), each task
    SHALL be treated as a standalone dispatch unit.
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.1
    """
    result = parse_tasks(data["content"])
    assert result.success, f"Parse failed: {result.errors}"
    
    # Every flat task should be a dispatch unit
    for task in result.tasks:
        assert is_dispatch_unit(task), \
            f"Flat task {task.task_id} should be a dispatch unit"
        
        # Flat tasks should have no parent
        assert task.parent_id is None, \
            f"Flat task {task.task_id} should have no parent"
        
        # Flat tasks should have no subtasks
        assert len(task.subtasks) == 0, \
            f"Flat task {task.task_id} should have no subtasks"


@given(data=flat_tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_flat_tasks_also_leaf_tasks(data):
    """
    Property 7: Backward Compatibility - Flat tasks are also leaf tasks
    
    For any flat task, it SHALL be both a dispatch unit AND a leaf task.
    This ensures backward compatibility with the old dispatch model.
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.1
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    for task in result.tasks:
        # Flat tasks are both dispatch units and leaf tasks
        assert is_dispatch_unit(task), \
            f"Flat task {task.task_id} should be a dispatch unit"
        assert is_leaf_task(task), \
            f"Flat task {task.task_id} should be a leaf task"


@given(data=flat_tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_get_ready_equals_get_dispatchable_for_flat(data):
    """
    Property 7: Backward Compatibility - Ready tasks match dispatchable units
    
    For any flat tasks.md, get_ready_tasks and get_dispatchable_units SHALL
    return the same set of not_started tasks (when filtering by the same criteria).
    
    Note: get_dispatchable_units only returns not_started tasks, while get_ready_tasks
    returns any non-completed task. For backward compatibility, we verify that
    the not_started subset is identical.
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.1, 7.2
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    # Get not_started tasks only
    not_started_tasks = [t for t in result.tasks if t.status == TaskStatus.NOT_STARTED]
    
    if not not_started_tasks:
        return  # Skip if no not_started tasks
    
    # With no completed tasks
    ready_old = get_ready_tasks(result.tasks, set())
    ready_new = get_dispatchable_units(result.tasks, set())
    
    # Filter get_ready_tasks to only not_started (to match get_dispatchable_units behavior)
    old_not_started_ids = {t.task_id for t in ready_old if t.status == TaskStatus.NOT_STARTED}
    new_ids = {t.task_id for t in ready_new}
    
    # For flat tasks, the not_started subset should be the same
    assert old_not_started_ids == new_ids, \
        f"get_ready_tasks (not_started)={old_not_started_ids} != get_dispatchable_units={new_ids}"


@given(data=flat_tasks_with_deps_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_flat_tasks_dependency_behavior_unchanged(data):
    """
    Property 7: Backward Compatibility - Dependency behavior unchanged
    
    For any flat tasks with dependencies, the dependency resolution SHALL
    behave identically between get_ready_tasks and get_dispatchable_units.
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.2
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    # Extract dependencies
    extract_dependencies(result.tasks)
    
    task_ids = data["task_ids"]
    
    # Test with various completion states
    for num_completed in range(len(task_ids) + 1):
        completed = set(task_ids[:num_completed])
        
        ready_old = get_ready_tasks(result.tasks, completed)
        ready_new = get_dispatchable_units(result.tasks, completed)
        
        old_ids = {t.task_id for t in ready_old}
        new_ids = {t.task_id for t in ready_new}
        
        assert old_ids == new_ids, \
            f"With completed={completed}: get_ready_tasks={old_ids} != get_dispatchable_units={new_ids}"


@given(data=flat_tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_flat_tasks_expand_dependencies_identity(data):
    """
    Property 7: Backward Compatibility - Dependency expansion is identity
    
    For any flat task dependency, expand_dependencies SHALL return the
    same task ID unchanged (since flat tasks have no subtasks to expand).
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.2
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    task_map = {t.task_id: t for t in result.tasks}
    
    # For each task, expanding it as a dependency should return itself
    for task in result.tasks:
        expanded = expand_dependencies([task.task_id], task_map)
        assert expanded == [task.task_id], \
            f"Flat task {task.task_id} should expand to itself, got {expanded}"


@given(data=flat_tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_flat_tasks_dispatchable_count_equals_not_started(data):
    """
    Property 7: Backward Compatibility - Dispatchable count matches not_started
    
    For any flat tasks.md with no dependencies, the number of dispatchable
    units SHALL equal the number of not_started tasks.
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.1
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    # Count not_started tasks
    not_started_count = sum(1 for t in result.tasks if t.status == TaskStatus.NOT_STARTED)
    
    # Get dispatchable units (no dependencies in this test data)
    dispatchable = get_dispatchable_units(result.tasks, set())
    
    assert len(dispatchable) == not_started_count, \
        f"Expected {not_started_count} dispatchable, got {len(dispatchable)}"


@given(data=flat_tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_7_flat_tasks_payload_single_subtask(data):
    """
    Property 7: Backward Compatibility - Payload has single subtask
    
    For any flat task, build_dispatch_payload SHALL create a payload
    with exactly one subtask (the task itself).
    
    Feature: task-dispatch-granularity, Property 7
    Validates: Requirements 7.1
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    if not result.tasks:
        return
    
    # Build payload for each task
    all_tasks_dict = [t.to_dict() for t in result.tasks]
    
    for task in result.tasks:
        task_dict = task.to_dict()
        payload = build_dispatch_payload(task_dict, all_tasks_dict, "specs/test")
        
        # Payload should have exactly one subtask
        assert len(payload.subtasks) == 1, \
            f"Flat task {task.task_id} payload should have 1 subtask, got {len(payload.subtasks)}"
        
        # The subtask should be the task itself
        assert payload.subtasks[0].task_id == task.task_id, \
            f"Subtask ID should be {task.task_id}, got {payload.subtasks[0].task_id}"


# ============================================================================
# Run property tests
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("Running Property 7: Backward Compatibility tests...")
    print("=" * 60)
    
    tests = [
        ("Property 7: All flat tasks are dispatch units", test_property_7_flat_tasks_all_dispatch_units),
        ("Property 7: Flat tasks are also leaf tasks", test_property_7_flat_tasks_also_leaf_tasks),
        ("Property 7: Ready equals dispatchable for flat", test_property_7_get_ready_equals_get_dispatchable_for_flat),
        ("Property 7: Dependency behavior unchanged", test_property_7_flat_tasks_dependency_behavior_unchanged),
        ("Property 7: Dependency expansion is identity", test_property_7_flat_tasks_expand_dependencies_identity),
        ("Property 7: Dispatchable count equals not_started", test_property_7_flat_tasks_dispatchable_count_equals_not_started),
        ("Property 7: Payload has single subtask", test_property_7_flat_tasks_payload_single_subtask),
    ]
    
    failed = []
    for name, test in tests:
        try:
            print(f"\n{name}")
            test()
            print("  ✅ PASSED")
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed.append((name, e))
    
    print("\n" + "=" * 60)
    if failed:
        print(f"❌ {len(failed)} failed")
        for name, e in failed:
            print(f"  - {name}: {e}")
        sys.exit(1)
    else:
        print(f"✅ All {len(tests)} property tests passed!")
