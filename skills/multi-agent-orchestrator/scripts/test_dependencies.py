#!/usr/bin/env python3
"""
Tests for task dependency extraction and circular dependency detection.
"""

import sys
from spec_parser import (
    Task,
    TaskStatus,
    TaskType,
    parse_tasks,
    extract_dependencies,
    get_ready_tasks,
    topological_sort,
    DependencyGraph,
    MissingDependencyError,
)


def test_extract_dependencies_from_details():
    """Test dependency extraction from task details."""
    print("Testing dependency extraction from details...")
    
    content = """# Tasks

- [ ] 1 First task
  - No dependencies

- [ ] 2 Second task
  - dependencies: 1

- [ ] 3 Third task
  - depends on: 1, 2

- [ ] 4 Fourth task
  - after: 3
"""
    
    result = parse_tasks(content)
    assert result.success
    extract_dependencies(result.tasks)
    
    task1 = next(t for t in result.tasks if t.task_id == "1")
    assert task1.dependencies == []
    
    task2 = next(t for t in result.tasks if t.task_id == "2")
    assert "1" in task2.dependencies
    
    task3 = next(t for t in result.tasks if t.task_id == "3")
    assert "1" in task3.dependencies and "2" in task3.dependencies
    
    print("  ✅ Passed")


def test_circular_dependency_detection():
    """Test circular dependency detection."""
    print("Testing circular dependency detection...")
    
    content = """# Tasks

- [ ] 1 First task
  - dependencies: 3

- [ ] 2 Second task
  - dependencies: 1

- [ ] 3 Third task
  - dependencies: 2
"""
    
    result = parse_tasks(content)
    dep_result = extract_dependencies(result.tasks)
    
    assert not dep_result.valid
    assert len(dep_result.circular_dependencies) > 0
    
    print(f"  ✅ Detected: {dep_result.circular_dependencies[0]}")


def test_no_circular_dependency():
    """Test valid DAG has no circular dependencies."""
    print("Testing valid DAG...")
    
    content = """# Tasks

- [ ] 1 First task
- [ ] 2 Second task
  - dependencies: 1
- [ ] 3 Third task
  - dependencies: 1
- [ ] 4 Fourth task
  - dependencies: 2, 3
"""
    
    result = parse_tasks(content)
    dep_result = extract_dependencies(result.tasks)
    
    assert dep_result.valid
    print("  ✅ Passed")


def test_topological_sort():
    """Test topological sorting."""
    print("Testing topological sort...")
    
    content = """# Tasks

- [ ] 4 Fourth task
  - dependencies: 2, 3
- [ ] 1 First task
- [ ] 3 Third task
  - dependencies: 1
- [ ] 2 Second task
  - dependencies: 1
"""
    
    result = parse_tasks(content)
    extract_dependencies(result.tasks)
    sorted_tasks, circular_errors, missing_errors = topological_sort(result.tasks)
    
    assert len(circular_errors) == 0
    assert len(missing_errors) == 0
    positions = {t.task_id: i for i, t in enumerate(sorted_tasks)}
    
    assert positions["1"] < positions["2"]
    assert positions["1"] < positions["3"]
    assert positions["2"] < positions["4"]
    assert positions["3"] < positions["4"]
    
    print(f"  ✅ Order: {[t.task_id for t in sorted_tasks]}")


def test_missing_dependency_detection():
    """Test that missing dependencies are detected and cause failure."""
    print("Testing missing dependency detection...")
    
    content = """# Tasks

- [ ] 1 First task
- [ ] 2 Second task
  - dependencies: 1, 99
- [ ] 3 Third task
  - dependencies: 100
"""
    
    result = parse_tasks(content)
    dep_result = extract_dependencies(result.tasks)
    
    # Should be invalid due to missing dependencies
    assert not dep_result.valid
    assert len(dep_result.missing_dependencies) > 0
    assert "2" in dep_result.missing_dependencies
    assert "99" in dep_result.missing_dependencies["2"]
    assert "3" in dep_result.missing_dependencies
    assert "100" in dep_result.missing_dependencies["3"]
    
    # topological_sort should fail fast
    sorted_tasks, circular_errors, missing_errors = topological_sort(result.tasks)
    assert len(sorted_tasks) == 0
    assert len(missing_errors) > 0
    
    print(f"  ✅ Detected missing deps: {dep_result.missing_dependencies}")


def test_get_ready_tasks():
    """Test getting ready tasks."""
    print("Testing get_ready_tasks...")
    
    content = """# Tasks

- [ ] 1 First task
- [ ] 2 Second task
  - dependencies: 1
- [ ] 3 Third task
  - dependencies: 1
- [ ] 4 Fourth task
  - dependencies: 2, 3
"""
    
    result = parse_tasks(content)
    extract_dependencies(result.tasks)
    
    ready = get_ready_tasks(result.tasks, set())
    assert {t.task_id for t in ready} == {"1"}
    
    ready = get_ready_tasks(result.tasks, {"1"})
    assert {t.task_id for t in ready} == {"2", "3"}
    
    ready = get_ready_tasks(result.tasks, {"1", "2", "3"})
    assert {t.task_id for t in ready} == {"4"}
    
    print("  ✅ Passed")


if __name__ == "__main__":
    print("Running dependency tests...")
    print("=" * 50)
    
    tests = [
        test_extract_dependencies_from_details,
        test_circular_dependency_detection,
        test_no_circular_dependency,
        test_topological_sort,
        test_missing_dependency_detection,
        test_get_ready_tasks,
    ]
    
    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed.append((test.__name__, e))
    
    print("=" * 50)
    if failed:
        print(f"❌ {len(failed)} failed")
        sys.exit(1)
    else:
        print(f"✅ All {len(tests)} tests passed!")
