#!/usr/bin/env python3
"""
Property-Based Tests for Spec Parser

Feature: multi-agent-orchestration
Property 1: Task Parsing Round-Trip Consistency
Validates: Requirements 1.2, 11.3, 11.4
"""

import string
from hypothesis import given, strategies as st, settings, assume
from spec_parser import Task, TaskType, TaskStatus, parse_tasks


@st.composite
def task_id_strategy(draw):
    """Generate valid task IDs like '1', '1.1', '2.3'"""
    major = draw(st.integers(min_value=1, max_value=20))
    if draw(st.booleans()):
        minor = draw(st.integers(min_value=1, max_value=10))
        return f"{major}.{minor}"
    return str(major)


@st.composite
def task_description_strategy(draw):
    """Generate valid task descriptions"""
    chars = string.ascii_letters + string.digits + " -_.,;:()"
    desc = draw(st.text(alphabet=chars, min_size=5, max_size=80)).strip()
    if not desc or desc[0] in "-*#":
        desc = "Task " + desc
    return desc


@st.composite
def task_status_strategy(draw):
    """Generate valid task status markers"""
    return draw(st.sampled_from([
        ("[ ]", TaskStatus.NOT_STARTED),
        ("[x]", TaskStatus.COMPLETED),
        ("[-]", TaskStatus.IN_PROGRESS),
        ("[~]", TaskStatus.BLOCKED),
    ]))


@st.composite
def single_task_strategy(draw):
    """Generate a single valid task"""
    task_id = draw(task_id_strategy())
    status_marker, expected_status = draw(task_status_strategy())
    is_optional = draw(st.booleans())
    description = draw(task_description_strategy())
    
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
def tasks_md_strategy(draw):
    """Generate valid tasks.md content"""
    num_tasks = draw(st.integers(min_value=1, max_value=8))
    
    lines = ["# Tasks", ""]
    expected_tasks = []
    used_ids = set()
    
    for _ in range(num_tasks):
        task_data = draw(single_task_strategy())
        
        # Ensure unique ID
        base_id = task_data["task_id"]
        task_id = base_id
        counter = 1
        while task_id in used_ids:
            task_id = f"{base_id}.{counter}" if "." not in base_id else f"{base_id.split('.')[0]}.{counter}"
            counter += 1
        used_ids.add(task_id)
        
        # Update task line with unique ID
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


@given(data=tasks_md_strategy())
@settings(max_examples=100, deadline=None)
def test_property_1_task_parsing_round_trip(data):
    """
    Property 1: Task Parsing Round-Trip Consistency
    
    For any valid tasks.md, parsing SHALL preserve task IDs, descriptions, and status.
    
    Feature: multi-agent-orchestration, Property 1
    Validates: Requirements 1.2, 11.3, 11.4
    """
    result = parse_tasks(data["content"])
    assert result.success
    
    parsed_by_id = {t.task_id: t for t in result.tasks}
    
    for expected in data["expected_tasks"]:
        task_id = expected["task_id"]
        assert task_id in parsed_by_id
        
        parsed = parsed_by_id[task_id]
        assert parsed.status == expected["status"]
        assert parsed.is_optional == expected["is_optional"]
        assert expected["description"] in parsed.description or parsed.description in expected["description"]


@given(task_id=task_id_strategy(), description=task_description_strategy())
@settings(max_examples=100, deadline=None)
def test_task_id_preservation(task_id, description):
    """Test task IDs are correctly preserved."""
    assume(len(description.strip()) > 0)
    
    content = f"# Tasks\n\n- [ ] {task_id} {description}\n"
    result = parse_tasks(content)
    
    assert result.success
    assert any(t.task_id == task_id for t in result.tasks)


@given(status_data=task_status_strategy())
@settings(max_examples=100, deadline=None)
def test_status_preservation(status_data):
    """Test status markers are correctly parsed."""
    marker, expected = status_data
    
    content = f"# Tasks\n\n- {marker} 1.1 Test task\n"
    result = parse_tasks(content)
    
    assert result.success
    assert result.tasks[0].status == expected


if __name__ == "__main__":
    import sys
    
    print("Running property tests...")
    print("=" * 50)
    
    tests = [
        ("Property 1: Round-Trip", test_property_1_task_parsing_round_trip),
        ("Task ID Preservation", test_task_id_preservation),
        ("Status Preservation", test_status_preservation),
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
    
    print("\n" + "=" * 50)
    if failed:
        print(f"❌ {len(failed)} failed")
        sys.exit(1)
    else:
        print(f"✅ All {len(tests)} tests passed!")


# ============================================================================
# Property Tests for Parent-Subtask Execution Model
# Feature: orchestration-fixes
# ============================================================================

from spec_parser import is_leaf_task, get_ready_tasks


@st.composite
def task_with_subtasks_strategy(draw):
    """Generate a parent task with subtasks."""
    parent_id = str(draw(st.integers(min_value=1, max_value=10)))
    num_subtasks = draw(st.integers(min_value=1, max_value=5))
    
    subtask_ids = [f"{parent_id}.{i}" for i in range(1, num_subtasks + 1)]
    
    parent = Task(
        task_id=parent_id,
        description=f"Parent task {parent_id}",
        subtasks=subtask_ids,
    )
    
    subtasks = [
        Task(
            task_id=sid,
            description=f"Subtask {sid}",
            parent_id=parent_id,
        )
        for sid in subtask_ids
    ]
    
    return {"parent": parent, "subtasks": subtasks}


@st.composite
def mixed_tasks_strategy(draw):
    """Generate a mix of parent tasks and leaf tasks."""
    num_parents = draw(st.integers(min_value=1, max_value=4))
    num_standalone = draw(st.integers(min_value=0, max_value=3))
    
    all_tasks = []
    parent_ids = set()
    leaf_ids = set()
    
    # Generate parent tasks with subtasks
    for i in range(1, num_parents + 1):
        parent_id = str(i * 10)  # Use 10, 20, 30... to avoid conflicts
        num_subtasks = draw(st.integers(min_value=1, max_value=3))
        subtask_ids = [f"{parent_id}.{j}" for j in range(1, num_subtasks + 1)]
        
        parent = Task(
            task_id=parent_id,
            description=f"Parent task {parent_id}",
            subtasks=subtask_ids,
        )
        parent_ids.add(parent_id)
        all_tasks.append(parent)
        
        for sid in subtask_ids:
            subtask = Task(
                task_id=sid,
                description=f"Subtask {sid}",
                parent_id=parent_id,
            )
            leaf_ids.add(sid)
            all_tasks.append(subtask)
    
    # Generate standalone leaf tasks
    for i in range(num_standalone):
        task_id = str(100 + i)  # Use 100, 101... to avoid conflicts
        task = Task(
            task_id=task_id,
            description=f"Standalone task {task_id}",
        )
        leaf_ids.add(task_id)
        all_tasks.append(task)
    
    return {
        "tasks": all_tasks,
        "parent_ids": parent_ids,
        "leaf_ids": leaf_ids,
    }


@given(data=task_with_subtasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_1_leaf_task_filtering_parent_excluded(data):
    """
    Property 1: Leaf Task Filtering - Parent tasks excluded
    
    For any parent task (task with subtasks), is_leaf_task SHALL return False
    and get_ready_tasks SHALL NOT include it in the ready list.
    
    Feature: orchestration-fixes, Property 1
    Validates: Requirements 1.1, 1.2
    """
    parent = data["parent"]
    subtasks = data["subtasks"]
    all_tasks = [parent] + subtasks
    
    # Parent task should NOT be a leaf task
    assert not is_leaf_task(parent), f"Parent task {parent.task_id} should not be a leaf task"
    
    # All subtasks should be leaf tasks
    for subtask in subtasks:
        assert is_leaf_task(subtask), f"Subtask {subtask.task_id} should be a leaf task"
    
    # get_ready_tasks should NOT include parent task
    ready = get_ready_tasks(all_tasks, set())
    ready_ids = {t.task_id for t in ready}
    
    assert parent.task_id not in ready_ids, f"Parent task {parent.task_id} should not be in ready tasks"
    
    # All subtasks should be in ready tasks (no dependencies)
    for subtask in subtasks:
        assert subtask.task_id in ready_ids, f"Subtask {subtask.task_id} should be in ready tasks"


@given(data=mixed_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_1_leaf_task_filtering_only_leaves_ready(data):
    """
    Property 1: Leaf Task Filtering - Only leaf tasks in ready list
    
    For any set of tasks, get_ready_tasks SHALL only return leaf tasks
    (tasks with no subtasks).
    
    Feature: orchestration-fixes, Property 1
    Validates: Requirements 1.1, 1.2
    """
    tasks = data["tasks"]
    parent_ids = data["parent_ids"]
    leaf_ids = data["leaf_ids"]
    
    # Get ready tasks with no completed tasks
    ready = get_ready_tasks(tasks, set())
    ready_ids = {t.task_id for t in ready}
    
    # No parent tasks should be in ready list
    for pid in parent_ids:
        assert pid not in ready_ids, f"Parent task {pid} should not be in ready tasks"
    
    # All ready tasks should be leaf tasks
    for task in ready:
        assert is_leaf_task(task), f"Ready task {task.task_id} should be a leaf task"
    
    # All leaf tasks (without dependencies) should be ready
    for lid in leaf_ids:
        assert lid in ready_ids, f"Leaf task {lid} should be in ready tasks"


@given(data=mixed_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_1_leaf_task_completed_excluded(data):
    """
    Property 1: Leaf Task Filtering - Completed tasks excluded
    
    For any set of tasks, get_ready_tasks SHALL exclude completed leaf tasks.
    
    Feature: orchestration-fixes, Property 1
    Validates: Requirements 1.1, 1.2
    """
    tasks = data["tasks"]
    leaf_ids = list(data["leaf_ids"])
    
    if not leaf_ids:
        return  # Skip if no leaf tasks
    
    # Mark some leaf tasks as completed
    completed_ids = set(leaf_ids[:len(leaf_ids)//2 + 1])
    
    ready = get_ready_tasks(tasks, completed_ids)
    ready_ids = {t.task_id for t in ready}
    
    # Completed tasks should not be in ready list
    for cid in completed_ids:
        assert cid not in ready_ids, f"Completed task {cid} should not be in ready tasks"
    
    # Non-completed leaf tasks should be in ready list
    for lid in leaf_ids:
        if lid not in completed_ids:
            assert lid in ready_ids, f"Non-completed leaf task {lid} should be in ready tasks"


# ============================================================================
# Property Tests for Dependency Expansion
# Feature: orchestration-fixes
# ============================================================================

from spec_parser import expand_dependencies


@st.composite
def nested_task_hierarchy_strategy(draw):
    """Generate a nested task hierarchy with parent-subtask relationships."""
    # Generate 1-3 top-level parent tasks
    num_parents = draw(st.integers(min_value=1, max_value=3))
    
    all_tasks = []
    task_map = {}
    parent_to_leaves = {}  # Maps parent_id to all leaf task IDs under it
    
    for p in range(1, num_parents + 1):
        parent_id = str(p)
        num_subtasks = draw(st.integers(min_value=1, max_value=3))
        subtask_ids = []
        leaf_ids = []
        
        for s in range(1, num_subtasks + 1):
            subtask_id = f"{parent_id}.{s}"
            
            # Optionally create nested subtasks (e.g., 1.1.1)
            if draw(st.booleans()) and draw(st.booleans()):
                # Create nested subtasks
                num_nested = draw(st.integers(min_value=1, max_value=2))
                nested_ids = [f"{subtask_id}.{n}" for n in range(1, num_nested + 1)]
                
                subtask = Task(
                    task_id=subtask_id,
                    description=f"Subtask {subtask_id}",
                    parent_id=parent_id,
                    subtasks=nested_ids,
                )
                all_tasks.append(subtask)
                task_map[subtask_id] = subtask
                subtask_ids.append(subtask_id)
                
                # Create nested leaf tasks
                for nid in nested_ids:
                    nested_task = Task(
                        task_id=nid,
                        description=f"Nested task {nid}",
                        parent_id=subtask_id,
                    )
                    all_tasks.append(nested_task)
                    task_map[nid] = nested_task
                    leaf_ids.append(nid)
            else:
                # Create leaf subtask
                subtask = Task(
                    task_id=subtask_id,
                    description=f"Subtask {subtask_id}",
                    parent_id=parent_id,
                )
                all_tasks.append(subtask)
                task_map[subtask_id] = subtask
                subtask_ids.append(subtask_id)
                leaf_ids.append(subtask_id)
        
        # Create parent task
        parent = Task(
            task_id=parent_id,
            description=f"Parent task {parent_id}",
            subtasks=subtask_ids,
        )
        all_tasks.append(parent)
        task_map[parent_id] = parent
        parent_to_leaves[parent_id] = leaf_ids
    
    return {
        "tasks": all_tasks,
        "task_map": task_map,
        "parent_to_leaves": parent_to_leaves,
    }


@st.composite
def task_with_parent_dependency_strategy(draw):
    """Generate a task that depends on a parent task."""
    hierarchy = draw(nested_task_hierarchy_strategy())
    task_map = hierarchy["task_map"]
    parent_to_leaves = hierarchy["parent_to_leaves"]
    
    # Pick a parent task to depend on
    parent_ids = list(parent_to_leaves.keys())
    if not parent_ids:
        return None
    
    dep_parent_id = draw(st.sampled_from(parent_ids))
    expected_leaves = parent_to_leaves[dep_parent_id]
    
    # Create a dependent task
    dependent = Task(
        task_id="99",
        description="Dependent task",
        dependencies=[dep_parent_id],
    )
    
    return {
        "task_map": task_map,
        "dependent": dependent,
        "dep_parent_id": dep_parent_id,
        "expected_leaves": expected_leaves,
    }


@given(data=task_with_parent_dependency_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_dependency_expansion_parent_to_leaves(data):
    """
    Property 3: Dependency Expansion - Parent expands to leaves
    
    For any task depending on a parent task, expand_dependencies SHALL
    return all leaf subtasks of that parent.
    
    Feature: orchestration-fixes, Property 3
    Validates: Requirements 1.6, 1.7, 5.1, 5.2
    """
    if data is None:
        return  # Skip if no valid data generated
    
    task_map = data["task_map"]
    dependent = data["dependent"]
    dep_parent_id = data["dep_parent_id"]
    expected_leaves = set(data["expected_leaves"])
    
    # Expand dependencies
    expanded = expand_dependencies(dependent.dependencies, task_map)
    expanded_set = set(expanded)
    
    # Parent ID should NOT be in expanded (it's replaced by leaves)
    assert dep_parent_id not in expanded_set, \
        f"Parent {dep_parent_id} should be expanded to leaves, not kept"
    
    # All expected leaves should be in expanded
    assert expected_leaves == expanded_set, \
        f"Expected leaves {expected_leaves}, got {expanded_set}"


@given(hierarchy=nested_task_hierarchy_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_dependency_expansion_leaf_unchanged(hierarchy):
    """
    Property 3: Dependency Expansion - Leaf tasks unchanged
    
    For any leaf task dependency, expand_dependencies SHALL return
    the same leaf task ID unchanged.
    
    Feature: orchestration-fixes, Property 3
    Validates: Requirements 5.3
    """
    task_map = hierarchy["task_map"]
    
    # Find all leaf tasks
    leaf_ids = [tid for tid, task in task_map.items() if is_leaf_task(task)]
    
    if not leaf_ids:
        return  # Skip if no leaf tasks
    
    # Expand each leaf task dependency
    for leaf_id in leaf_ids:
        expanded = expand_dependencies([leaf_id], task_map)
        assert expanded == [leaf_id], \
            f"Leaf task {leaf_id} should remain unchanged, got {expanded}"


@given(hierarchy=nested_task_hierarchy_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_dependency_expansion_no_duplicates(hierarchy):
    """
    Property 3: Dependency Expansion - No duplicates
    
    For any set of dependencies, expand_dependencies SHALL return
    a list with no duplicate task IDs.
    
    Feature: orchestration-fixes, Property 3
    Validates: Requirements 5.1, 5.2
    """
    task_map = hierarchy["task_map"]
    parent_to_leaves = hierarchy["parent_to_leaves"]
    
    # Create dependencies with potential duplicates
    # (e.g., depend on parent and one of its subtasks)
    all_ids = list(task_map.keys())
    if len(all_ids) < 2:
        return
    
    # Pick multiple dependencies that might overlap
    deps = list(set(all_ids[:min(3, len(all_ids))]))
    
    expanded = expand_dependencies(deps, task_map)
    
    # Check no duplicates
    assert len(expanded) == len(set(expanded)), \
        f"Expanded dependencies contain duplicates: {expanded}"


@given(hierarchy=nested_task_hierarchy_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_dependency_expansion_ready_waits_for_all_subtasks(hierarchy):
    """
    Property 3: Dependency Expansion - Ready waits for all subtasks
    
    For any task depending on a parent, get_ready_tasks SHALL NOT return
    that task until ALL subtasks of the parent are completed.
    
    Feature: orchestration-fixes, Property 3
    Validates: Requirements 1.6, 1.7, 5.4, 5.5
    """
    task_map = hierarchy["task_map"]
    parent_to_leaves = hierarchy["parent_to_leaves"]
    
    if not parent_to_leaves:
        return
    
    # Pick a parent to depend on
    parent_id = list(parent_to_leaves.keys())[0]
    expected_leaves = parent_to_leaves[parent_id]
    
    if not expected_leaves:
        return
    
    # Create a dependent task
    dependent = Task(
        task_id="99",
        description="Dependent task",
        dependencies=[parent_id],
    )
    
    all_tasks = list(task_map.values()) + [dependent]
    
    # With no completions, dependent should NOT be ready
    ready = get_ready_tasks(all_tasks, set())
    ready_ids = {t.task_id for t in ready}
    assert "99" not in ready_ids, "Dependent should not be ready with no completions"
    
    # With partial completions, dependent should NOT be ready
    if len(expected_leaves) > 1:
        partial = set(expected_leaves[:-1])  # All but one
        ready = get_ready_tasks(all_tasks, partial)
        ready_ids = {t.task_id for t in ready}
        assert "99" not in ready_ids, "Dependent should not be ready with partial completions"
    
    # With all subtasks completed, dependent SHOULD be ready
    all_completed = set(expected_leaves)
    ready = get_ready_tasks(all_tasks, all_completed)
    ready_ids = {t.task_id for t in ready}
    assert "99" in ready_ids, "Dependent should be ready when all subtasks completed"
