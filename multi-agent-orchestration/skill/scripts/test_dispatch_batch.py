#!/usr/bin/env python3
"""
Property-Based Tests for Dispatch Batch - File Conflict Detection

Feature: orchestration-fixes
Property 5: Conflict-Aware Batching
Validates: Requirements 2.3, 2.4, 2.5, 2.6
"""

import string
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Set

from dispatch_batch import (
    FileConflict,
    detect_file_conflicts,
    partition_by_conflicts,
    has_file_manifest,
    DispatchPayload,
    SubtaskInfo,
    build_dispatch_payload,
    allocate_windows,
    apply_window_allocation,
    handle_partial_completion,
    _build_dispatch_unit_content,
)


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def file_path_strategy(draw):
    """Generate valid file paths."""
    # Generate path components
    dirs = draw(st.lists(
        st.text(alphabet=string.ascii_lowercase + string.digits + "_-", min_size=1, max_size=10),
        min_size=0,
        max_size=2
    ))
    
    # Generate filename
    name = draw(st.text(alphabet=string.ascii_lowercase + string.digits + "_-", min_size=1, max_size=10))
    ext = draw(st.sampled_from([".py", ".js", ".ts", ".json", ".md", ".txt", ".go"]))
    
    filename = name + ext
    
    if dirs:
        return "/".join(dirs) + "/" + filename
    return filename


@st.composite
def task_with_manifest_strategy(draw):
    """Generate a task with file manifest."""
    task_id = str(draw(st.integers(min_value=1, max_value=100)))
    
    # Generate writes list (0-5 files)
    num_writes = draw(st.integers(min_value=0, max_value=5))
    writes = list(dict.fromkeys([draw(file_path_strategy()) for _ in range(num_writes)]))
    
    # Generate reads list (0-5 files)
    num_reads = draw(st.integers(min_value=0, max_value=5))
    reads = list(dict.fromkeys([draw(file_path_strategy()) for _ in range(num_reads)]))
    
    return {
        "task_id": task_id,
        "writes": writes if writes else [],
        "reads": reads if reads else [],
    }


@st.composite
def task_without_manifest_strategy(draw):
    """Generate a task without file manifest."""
    task_id = str(draw(st.integers(min_value=1, max_value=100)))
    return {
        "task_id": task_id,
        # No writes or reads fields
    }


@st.composite
def conflicting_tasks_strategy(draw):
    """Generate tasks with guaranteed write-write conflicts."""
    # Generate a shared file that will cause conflict
    shared_file = draw(file_path_strategy())
    
    # Generate two tasks that both write to the shared file
    task_a_id = str(draw(st.integers(min_value=1, max_value=50)))
    task_b_id = str(draw(st.integers(min_value=51, max_value=100)))
    
    # Additional unique files for each task
    task_a_extra = [draw(file_path_strategy()) for _ in range(draw(st.integers(min_value=0, max_value=2)))]
    task_b_extra = [draw(file_path_strategy()) for _ in range(draw(st.integers(min_value=0, max_value=2)))]
    
    task_a = {
        "task_id": task_a_id,
        "writes": [shared_file] + task_a_extra,
        "reads": [],
    }
    
    task_b = {
        "task_id": task_b_id,
        "writes": [shared_file] + task_b_extra,
        "reads": [],
    }
    
    return {
        "task_a": task_a,
        "task_b": task_b,
        "shared_file": shared_file,
    }


@st.composite
def non_conflicting_tasks_strategy(draw):
    """Generate tasks with no write-write conflicts."""
    num_tasks = draw(st.integers(min_value=2, max_value=5))
    
    tasks = []
    all_write_files: Set[str] = set()
    
    for i in range(num_tasks):
        task_id = str(i + 1)
        
        # Generate unique write files (not in any other task's writes)
        num_writes = draw(st.integers(min_value=1, max_value=3))
        writes = []
        for _ in range(num_writes):
            # Keep generating until we get a unique file
            for _ in range(10):  # Max attempts
                f = draw(file_path_strategy())
                if f not in all_write_files:
                    writes.append(f)
                    all_write_files.add(f)
                    break
        
        # Reads can overlap (no conflict)
        num_reads = draw(st.integers(min_value=0, max_value=3))
        reads = [draw(file_path_strategy()) for _ in range(num_reads)]
        
        tasks.append({
            "task_id": task_id,
            "writes": writes,
            "reads": reads,
        })
    
    return tasks


@st.composite
def mixed_tasks_strategy(draw):
    """Generate a mix of tasks with and without manifests, with and without conflicts."""
    # Tasks with manifest (some may conflict)
    num_manifest_tasks = draw(st.integers(min_value=1, max_value=4))
    manifest_tasks = [draw(task_with_manifest_strategy()) for _ in range(num_manifest_tasks)]
    
    # Ensure unique task IDs
    used_ids = set()
    for i, task in enumerate(manifest_tasks):
        while task["task_id"] in used_ids:
            task["task_id"] = str(int(task["task_id"]) + 100)
        used_ids.add(task["task_id"])
    
    # Tasks without manifest
    num_no_manifest = draw(st.integers(min_value=0, max_value=3))
    no_manifest_tasks = []
    for i in range(num_no_manifest):
        task = draw(task_without_manifest_strategy())
        while task["task_id"] in used_ids:
            task["task_id"] = str(int(task["task_id"]) + 200)
        used_ids.add(task["task_id"])
        no_manifest_tasks.append(task)
    
    return {
        "manifest_tasks": manifest_tasks,
        "no_manifest_tasks": no_manifest_tasks,
        "all_tasks": manifest_tasks + no_manifest_tasks,
    }


@st.composite
def subtask_details_strategy(draw):
    """Generate a list of short detail strings."""
    alphabet = string.ascii_letters + string.digits + " -_,.;:()"
    return draw(st.lists(
        st.text(alphabet=alphabet, min_size=0, max_size=40),
        min_size=0,
        max_size=3
    ))


@st.composite
def dispatch_unit_parent_strategy(draw):
    """Generate a parent dispatch unit with subtasks and full task list."""
    parent_id = str(draw(st.integers(min_value=1, max_value=20)))
    num_subtasks = draw(st.integers(min_value=1, max_value=5))
    subtask_ids = [f"{parent_id}.{i}" for i in range(1, num_subtasks + 1)]
    shuffled_subtasks = list(draw(st.permutations(subtask_ids)))

    # Build subtasks with details
    all_tasks = []
    for sid in subtask_ids:
        all_tasks.append({
            "task_id": sid,
            "description": f"Subtask {sid}",
            "details": draw(subtask_details_strategy()),
            "is_optional": draw(st.booleans()),
        })

    # Optional manifest metadata
    writes = draw(st.lists(file_path_strategy(), min_size=0, max_size=3))
    reads = draw(st.lists(file_path_strategy(), min_size=0, max_size=3))
    criticality = draw(st.sampled_from([None, "standard", "complex", "security-sensitive"]))

    dispatch_unit = {
        "task_id": parent_id,
        "description": f"Parent task {parent_id}",
        "subtasks": shuffled_subtasks,
        "criticality": criticality,
        "writes": writes,
        "reads": reads,
    }

    return {
        "dispatch_unit": dispatch_unit,
        "all_tasks": all_tasks,
        "subtask_ids": subtask_ids,
    }


@st.composite
def dispatch_unit_standalone_strategy(draw):
    """Generate a standalone dispatch unit with no subtasks."""
    task_id = str(draw(st.integers(min_value=1, max_value=200)))
    details = draw(subtask_details_strategy())
    writes = draw(st.lists(file_path_strategy(), min_size=0, max_size=3))
    reads = draw(st.lists(file_path_strategy(), min_size=0, max_size=3))
    criticality = draw(st.sampled_from([None, "standard", "complex", "security-sensitive"]))

    dispatch_unit = {
        "task_id": task_id,
        "description": f"Standalone task {task_id}",
        "details": details,
        "criticality": criticality,
        "writes": writes,
        "reads": reads,
    }

    return {
        "dispatch_unit": dispatch_unit,
        "all_tasks": [dispatch_unit],
    }


@st.composite
def dispatch_unit_hierarchy_strategy(draw):
    """Generate tasks with parents, subtasks, and standalone units."""
    tasks = []
    dispatch_unit_ids = []

    num_parents = draw(st.integers(min_value=1, max_value=3))
    for p in range(1, num_parents + 1):
        parent_id = str(p)
        num_subtasks = draw(st.integers(min_value=1, max_value=4))
        subtask_ids = [f"{parent_id}.{i}" for i in range(1, num_subtasks + 1)]

        tasks.append({
            "task_id": parent_id,
            "description": f"Parent {parent_id}",
            "subtasks": subtask_ids,
            "parent_id": None,
        })
        dispatch_unit_ids.append(parent_id)

        for sid in subtask_ids:
            tasks.append({
                "task_id": sid,
                "description": f"Subtask {sid}",
                "subtasks": [],
                "parent_id": parent_id,
            })

    num_standalone = draw(st.integers(min_value=0, max_value=3))
    for i in range(num_standalone):
        task_id = str(100 + i)
        tasks.append({
            "task_id": task_id,
            "description": f"Standalone {task_id}",
            "subtasks": [],
            "parent_id": None,
        })
        dispatch_unit_ids.append(task_id)

    return {"tasks": tasks, "dispatch_unit_ids": dispatch_unit_ids}


def _sort_task_ids(task_ids: List[str]) -> List[str]:
    """Sort task IDs like '1.2.3' using numeric ordering."""
    def key(tid: str) -> List[Any]:
        parts: List[Any] = []
        for part in tid.split("."):
            if part.isdigit():
                parts.append(int(part))
            else:
                parts.append(part)
        return parts
    return sorted(task_ids, key=key)


# ============================================================================  
# Property Tests
# ============================================================================  

@given(data=conflicting_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_conflict_detection_finds_conflicts(data):
    """
    Property 5: Conflict Detection - Finds write-write conflicts
    
    For any two tasks that write to the same file, detect_file_conflicts
    SHALL return a conflict containing both task IDs and the shared file.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.3, 2.4
    """
    task_a = data["task_a"]
    task_b = data["task_b"]
    shared_file = data["shared_file"]
    
    conflicts = detect_file_conflicts([task_a, task_b])
    
    # Should find exactly one conflict
    assert len(conflicts) >= 1, "Should detect at least one conflict"
    
    # Find the conflict involving our shared file
    relevant_conflicts = [c for c in conflicts if shared_file in c.files]
    assert len(relevant_conflicts) >= 1, f"Should find conflict for {shared_file}"
    
    conflict = relevant_conflicts[0]
    
    # Verify conflict contains both task IDs
    conflict_task_ids = {conflict.task_a, conflict.task_b}
    assert task_a["task_id"] in conflict_task_ids, "Conflict should include task_a"
    assert task_b["task_id"] in conflict_task_ids, "Conflict should include task_b"
    
    # Verify conflict type
    assert conflict.conflict_type == "write-write", "Conflict type should be write-write"


@given(tasks=non_conflicting_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_no_conflicts_when_disjoint_writes(tasks):
    """
    Property 5: Conflict Detection - No conflicts for disjoint writes
    
    For any set of tasks with disjoint write sets, detect_file_conflicts
    SHALL return an empty list.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.3, 2.4
    """
    conflicts = detect_file_conflicts(tasks)
    
    assert len(conflicts) == 0, f"Should have no conflicts, but found: {conflicts}"


@given(data=mixed_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_partition_no_conflicts_within_batch(data):
    """
    Property 5: Conflict-Aware Batching - No conflicts within any batch
    
    For any set of tasks, partition_by_conflicts SHALL produce batches
    where no two tasks in the same batch have write-write conflicts.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.3, 2.4
    """
    all_tasks = data["all_tasks"]
    
    if not all_tasks:
        return
    
    batches = partition_by_conflicts(all_tasks)
    
    # Check each batch for internal conflicts
    for i, batch in enumerate(batches):
        if len(batch) <= 1:
            continue  # Single task batch can't have internal conflicts
        
        # Check for write-write conflicts within this batch
        conflicts = detect_file_conflicts(batch)
        
        assert len(conflicts) == 0, \
            f"Batch {i} has internal conflicts: {conflicts}"


@given(data=mixed_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_partition_preserves_all_tasks(data):
    """
    Property 5: Conflict-Aware Batching - All tasks preserved
    
    For any set of tasks, partition_by_conflicts SHALL include every
    task in exactly one batch.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.3, 2.4, 2.6
    """
    all_tasks = data["all_tasks"]
    
    if not all_tasks:
        return
    
    batches = partition_by_conflicts(all_tasks)
    
    # Collect all task IDs from batches
    batched_ids = []
    for batch in batches:
        for task in batch:
            batched_ids.append(task["task_id"])
    
    original_ids = [t["task_id"] for t in all_tasks]
    
    # Every original task should appear exactly once
    assert sorted(batched_ids) == sorted(original_ids), \
        f"Tasks not preserved: original={original_ids}, batched={batched_ids}"


@given(data=mixed_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_no_manifest_tasks_serial(data):
    """
    Property 5: Conflict-Aware Batching - No-manifest tasks run serially
    
    For any task without a file manifest (no writes AND no reads),
    partition_by_conflicts SHALL place it in its own batch.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.5
    """
    no_manifest_tasks = data["no_manifest_tasks"]
    all_tasks = data["all_tasks"]
    
    if not no_manifest_tasks:
        return
    
    batches = partition_by_conflicts(all_tasks)
    
    # Find batches containing no-manifest tasks
    no_manifest_ids = {t["task_id"] for t in no_manifest_tasks}
    
    for batch in batches:
        batch_ids = {t["task_id"] for t in batch}
        no_manifest_in_batch = batch_ids & no_manifest_ids
        
        if no_manifest_in_batch:
            # If batch contains a no-manifest task, it should be alone
            assert len(batch) == 1, \
                f"No-manifest task should be in its own batch, but batch has {len(batch)} tasks"


@given(data=conflicting_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_conflicting_tasks_in_different_batches(data):
    """
    Property 5: Conflict-Aware Batching - Conflicting tasks separated
    
    For any two tasks with write-write conflicts, partition_by_conflicts
    SHALL place them in different batches.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.3, 2.4
    """
    task_a = data["task_a"]
    task_b = data["task_b"]
    
    batches = partition_by_conflicts([task_a, task_b])
    
    # Find which batch each task is in
    task_a_batch = None
    task_b_batch = None
    
    for i, batch in enumerate(batches):
        batch_ids = {t["task_id"] for t in batch}
        if task_a["task_id"] in batch_ids:
            task_a_batch = i
        if task_b["task_id"] in batch_ids:
            task_b_batch = i
    
    assert task_a_batch is not None, "task_a should be in a batch"
    assert task_b_batch is not None, "task_b should be in a batch"
    assert task_a_batch != task_b_batch, \
        f"Conflicting tasks should be in different batches, both in batch {task_a_batch}"


@given(tasks=non_conflicting_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_non_conflicting_tasks_can_batch(tasks):
    """
    Property 5: Conflict-Aware Batching - Non-conflicting tasks can batch
    
    For any set of tasks with no write-write conflicts and all having
    file manifests, partition_by_conflicts MAY place them in the same batch.
    
    Feature: orchestration-fixes, Property 5
    Validates: Requirements 2.6
    """
    # All tasks have manifests and no conflicts
    batches = partition_by_conflicts(tasks)
    
    # Should have at least one batch
    assert len(batches) >= 1, "Should have at least one batch"
    
    # Total tasks across batches should equal input
    total_batched = sum(len(b) for b in batches)
    assert total_batched == len(tasks), "All tasks should be batched"
    
    # With no conflicts, ideally all tasks could be in one batch
    # (but implementation may choose otherwise for other reasons)
    # Just verify no unnecessary splitting due to false conflicts
    if len(tasks) > 0:
        # At minimum, we shouldn't have more batches than tasks
        assert len(batches) <= len(tasks), \
            f"Too many batches ({len(batches)}) for {len(tasks)} non-conflicting tasks"


@given(task=task_with_manifest_strategy())
@settings(max_examples=100, deadline=None)
def test_has_file_manifest_with_manifest(task):
    """
    Test has_file_manifest returns True for tasks with writes or reads.
    
    Validates: Requirements 2.5
    """
    if task.get("writes") or task.get("reads"):
        assert has_file_manifest(task), "Task with writes/reads should have manifest"


@given(task=task_without_manifest_strategy())
@settings(max_examples=100, deadline=None)
def test_has_file_manifest_without_manifest(task):
    """
    Test has_file_manifest returns False for tasks without writes or reads.     

    Validates: Requirements 2.5
    """
    assert not has_file_manifest(task), "Task without writes/reads should not have manifest"


# ============================================================================  
# Property Tests for Dispatch Payload Structure
# Feature: task-dispatch-granularity
# Property 4: Payload Structure Completeness
# Validates: Requirements 5.1, 5.2, 5.3
# ============================================================================  

@given(data=dispatch_unit_parent_strategy())
@settings(max_examples=100, deadline=None)
def test_property_4_payload_parent_includes_ordered_subtasks(data):
    """
    Property 4: Payload Structure Completeness - Parent tasks

    For any parent dispatch unit, build_dispatch_payload SHALL include all
    subtasks in sorted order with descriptions and details.

    Feature: task-dispatch-granularity, Property 4
    Validates: Requirements 5.1, 5.2, 5.3
    """
    dispatch_unit = data["dispatch_unit"]
    all_tasks = data["all_tasks"]
    spec_path = "specs/task-dispatch-granularity"

    payload = build_dispatch_payload(dispatch_unit, all_tasks, spec_path)

    assert isinstance(payload, DispatchPayload)
    assert payload.dispatch_unit_id == dispatch_unit["task_id"]
    assert payload.description == dispatch_unit["description"]
    assert payload.spec_path == spec_path

    expected_order = _sort_task_ids(data["subtask_ids"])
    actual_order = [s.task_id for s in payload.subtasks]
    assert actual_order == expected_order, \
        f"Expected subtask order {expected_order}, got {actual_order}"

    # Verify subtask details are preserved
    task_map = {t["task_id"]: t for t in all_tasks}
    for subtask in payload.subtasks:
        assert isinstance(subtask, SubtaskInfo)
        source = task_map[subtask.task_id]
        assert subtask.description == source["description"]
        assert subtask.details == source.get("details", [])

    # Verify metadata fields
    assert payload.metadata.get("criticality") == dispatch_unit.get("criticality")
    assert payload.metadata.get("writes") == dispatch_unit.get("writes", [])
    assert payload.metadata.get("reads") == dispatch_unit.get("reads", [])


@given(data=dispatch_unit_standalone_strategy())
@settings(max_examples=100, deadline=None)
def test_property_4_payload_standalone_single_item(data):
    """
    Property 4: Payload Structure Completeness - Standalone tasks

    For any standalone dispatch unit, build_dispatch_payload SHALL include
    the task as a single subtask work item.

    Feature: task-dispatch-granularity, Property 4
    Validates: Requirements 5.1, 5.2, 5.3
    """
    dispatch_unit = data["dispatch_unit"]
    all_tasks = data["all_tasks"]
    spec_path = "specs/task-dispatch-granularity"

    payload = build_dispatch_payload(dispatch_unit, all_tasks, spec_path)

    assert len(payload.subtasks) == 1
    subtask = payload.subtasks[0]
    assert subtask.task_id == dispatch_unit["task_id"]
    assert subtask.description == dispatch_unit["description"]
    assert subtask.details == dispatch_unit.get("details", [])

    assert payload.metadata.get("criticality") == dispatch_unit.get("criticality")
    assert payload.metadata.get("writes") == dispatch_unit.get("writes", [])
    assert payload.metadata.get("reads") == dispatch_unit.get("reads", [])


# ============================================================================
# Property Tests for Window Allocation (Dispatch Units)
# Feature: task-dispatch-granularity
# Property 5: Window Allocation Invariant
# Validates: Requirements 6.1, 6.3
# ============================================================================

@given(data=dispatch_unit_hierarchy_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_window_allocation_one_per_dispatch_unit(data):
    """
    Property 5: Window Allocation Invariant

    For any set of dispatch units, allocate_windows SHALL assign exactly one
    window per dispatch unit and not include subtasks.

    Feature: task-dispatch-granularity, Property 5
    Validates: Requirements 6.1, 6.3
    """
    tasks = data["tasks"]
    dispatch_unit_ids = data["dispatch_unit_ids"]
    dispatch_units = [t for t in tasks if t["task_id"] in dispatch_unit_ids]

    mapping = allocate_windows(dispatch_units, max_windows=len(dispatch_units) + 1)

    assert set(mapping.keys()) == set(dispatch_unit_ids), \
        f"Expected windows for {dispatch_unit_ids}, got {list(mapping.keys())}"
    assert len(set(mapping.values())) == len(mapping), \
        "Each dispatch unit should have a unique window"


@given(data=dispatch_unit_hierarchy_strategy())
@settings(max_examples=100, deadline=None)
def test_property_5_window_allocation_skips_subtasks(data):
    """
    Property 5: Window Allocation - Subtasks ignored

    apply_window_allocation SHALL set target_window only for dispatch units.
    """
    state = {"tasks": data["tasks"], "window_mapping": {}}
    dispatch_unit_ids = set(data["dispatch_unit_ids"])
    dispatch_units = [t for t in state["tasks"] if t["task_id"] in dispatch_unit_ids]

    apply_window_allocation(state, dispatch_units, max_windows=len(dispatch_units) + 1)

    for task in state["tasks"]:
        if task["task_id"] in dispatch_unit_ids:
            assert task.get("target_window"), \
                f"Dispatch unit {task['task_id']} should have target_window"
        else:
            assert not task.get("target_window"), \
                f"Subtask {task['task_id']} should not get target_window"


# ============================================================================
# Property Tests for Failure Isolation
# Feature: task-dispatch-granularity
# Property 8: Subtask Failure Isolation
# Validates: Requirements 8.2, 8.4
# ============================================================================

@st.composite
def partial_failure_state_strategy(draw):
    """Generate a state with a parent and subtasks for partial failure."""
    parent_id = "1"
    num_subtasks = draw(st.integers(min_value=2, max_value=5))
    subtask_ids = [f"{parent_id}.{i}" for i in range(1, num_subtasks + 1)]

    completed_count = draw(st.integers(min_value=0, max_value=num_subtasks - 1))
    completed_subtasks = draw(st.lists(
        st.sampled_from(subtask_ids),
        min_size=completed_count,
        max_size=completed_count,
        unique=True
    ))

    remaining = [sid for sid in subtask_ids if sid not in completed_subtasks]
    failed_subtask = draw(st.sampled_from(remaining))

    tasks = [{
        "task_id": parent_id,
        "description": "Parent task",
        "status": "not_started",
        "subtasks": subtask_ids,
    }]

    for sid in subtask_ids:
        tasks.append({
            "task_id": sid,
            "description": f"Subtask {sid}",
            "status": "not_started",
            "parent_id": parent_id,
            "subtasks": [],
        })

    return {
        "state": {"tasks": tasks},
        "parent_id": parent_id,
        "completed_subtasks": completed_subtasks,
        "failed_subtask": failed_subtask,
    }


@given(data=partial_failure_state_strategy())
@settings(max_examples=100, deadline=None)
def test_property_8_failure_isolation_preserves_completed(data):
    """
    Property 8: Subtask Failure Isolation

    Completed subtasks remain completed, failed subtask is blocked, and parent
    is blocked when a subtask fails.
    """
    state = data["state"]
    parent_id = data["parent_id"]
    completed_subtasks = data["completed_subtasks"]
    failed_subtask = data["failed_subtask"]
    error = "subtask failed"

    handle_partial_completion(
        state,
        dispatch_unit_id=parent_id,
        completed_subtasks=completed_subtasks,
        failed_subtask=failed_subtask,
        error=error
    )

    task_map = {t["task_id"]: t for t in state["tasks"]}
    for sid in completed_subtasks:
        assert task_map[sid]["status"] == "completed"

    assert task_map[failed_subtask]["status"] == "blocked"
    assert task_map[failed_subtask].get("blocked_reason") == error
    assert task_map[parent_id]["status"] == "blocked"
    assert task_map[parent_id].get("blocked_by") == failed_subtask


def test_resume_guidance_includes_first_incomplete_subtask():
    """Ensure resume guidance highlights the first incomplete subtask."""
    parent = {
        "task_id": "1",
        "description": "Parent task",
        "subtasks": ["1.1", "1.2"],
    }
    all_tasks = [
        parent,
        {"task_id": "1.1", "description": "Subtask 1.1", "status": "completed", "subtasks": [], "parent_id": "1"},
        {"task_id": "1.2", "description": "Subtask 1.2", "status": "not_started", "subtasks": [], "parent_id": "1"},
    ]

    content = _build_dispatch_unit_content(parent, "/spec", all_tasks)
    assert "Resume from Step 2: 1.2" in content
