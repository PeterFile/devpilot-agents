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
