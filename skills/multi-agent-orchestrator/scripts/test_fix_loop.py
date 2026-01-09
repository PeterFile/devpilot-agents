#!/usr/bin/env python3
"""
Property-Based Tests for Fix Loop Module

Feature: orchestration-fixes
Property 6: Fix Loop Entry
Property 7: Fix Loop Retry Budget
Property 9: Fix Prompt Content
Validates: Requirements 3.1, 3.2, 3.3, 3.6, 3.7, 3.8, 3.9, 6.1, 6.2, 6.3, 6.4, 6.5
"""

import string
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Set

from fix_loop import (
    should_enter_fix_loop,
    get_all_dependent_task_ids,
    block_dependent_tasks,
    enter_fix_loop,
    MAX_FIX_ATTEMPTS,
    ESCALATION_THRESHOLD,
)


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def task_id_strategy(draw):
    """Generate valid task IDs."""
    major = draw(st.integers(min_value=1, max_value=20))
    if draw(st.booleans()):
        minor = draw(st.integers(min_value=1, max_value=10))
        return f"{major}.{minor}"
    return str(major)


@st.composite
def severity_strategy(draw):
    """Generate review severities."""
    return draw(st.sampled_from(["critical", "major", "minor", "none"]))


@st.composite
def review_finding_strategy(draw):
    """Generate a single review finding."""
    severity = draw(severity_strategy())
    summary = draw(st.text(alphabet=string.ascii_letters + string.digits + " -_.,", min_size=5, max_size=50))
    details = draw(st.text(alphabet=string.ascii_letters + string.digits + " -_.,", min_size=0, max_size=100))
    
    return {
        "severity": severity,
        "summary": summary.strip() or "Issue found",
        "details": details.strip() if details.strip() else None,
    }


@st.composite
def review_findings_strategy(draw, min_findings=1, max_findings=5):
    """Generate a list of review findings."""
    num_findings = draw(st.integers(min_value=min_findings, max_value=max_findings))
    return [draw(review_finding_strategy()) for _ in range(num_findings)]


@st.composite
def task_dict_strategy(draw, task_id=None, status="not_started"):
    """Generate a task dictionary."""
    if task_id is None:
        task_id = draw(task_id_strategy())
    
    return {
        "task_id": task_id,
        "description": f"Task {task_id}",
        "status": status,
        "dependencies": [],
        "subtasks": [],
        "fix_attempts": 0,
        "review_history": [],
    }


@st.composite
def state_with_dependencies_strategy(draw):
    """Generate a state with tasks that have dependencies."""
    # Create 3-6 tasks
    num_tasks = draw(st.integers(min_value=3, max_value=6))
    
    tasks = []
    task_ids = []
    
    for i in range(num_tasks):
        task_id = str(i + 1)
        task_ids.append(task_id)
        
        # First task has no dependencies, others may depend on earlier tasks
        deps = []
        if i > 0:
            # Randomly depend on some earlier tasks
            num_deps = draw(st.integers(min_value=0, max_value=min(2, i)))
            if num_deps > 0:
                dep_indices = draw(st.lists(
                    st.integers(min_value=0, max_value=i-1),
                    min_size=num_deps,
                    max_size=num_deps,
                    unique=True
                ))
                deps = [task_ids[idx] for idx in dep_indices]
        
        task = {
            "task_id": task_id,
            "description": f"Task {task_id}",
            "status": "not_started",
            "dependencies": deps,
            "subtasks": [],
            "fix_attempts": 0,
            "review_history": [],
        }
        tasks.append(task)
    
    return {
        "tasks": tasks,
        "blocked_items": [],
    }


@st.composite
def state_with_chain_dependencies_strategy(draw):
    """Generate a state with a chain of dependencies: 1 -> 2 -> 3 -> 4."""
    chain_length = draw(st.integers(min_value=3, max_value=5))
    
    tasks = []
    for i in range(chain_length):
        task_id = str(i + 1)
        deps = [str(i)] if i > 0 else []
        
        task = {
            "task_id": task_id,
            "description": f"Task {task_id}",
            "status": "not_started",
            "dependencies": deps,
            "subtasks": [],
            "fix_attempts": 0,
            "review_history": [],
        }
        tasks.append(task)
    
    return {
        "tasks": tasks,
        "blocked_items": [],
        "chain_length": chain_length,
    }


# ============================================================================
# Property Tests for Fix Loop Entry (Property 6)
# ============================================================================

@given(severity=st.sampled_from(["critical", "major"]))
@settings(max_examples=100, deadline=None)
def test_property_6_critical_major_enters_fix_loop(severity):
    """
    Property 6: Fix Loop Entry - Critical/major severity enters fix loop
    
    For any review with severity "critical" or "major", should_enter_fix_loop
    SHALL return True.
    
    Feature: orchestration-fixes, Property 6
    Validates: Requirements 3.1
    """
    assert should_enter_fix_loop(severity) is True, \
        f"Severity {severity} should enter fix loop"


@given(severity=st.sampled_from(["minor", "none", ""]))
@settings(max_examples=100, deadline=None)
def test_property_6_minor_none_skips_fix_loop(severity):
    """
    Property 6: Fix Loop Entry - Minor/none severity skips fix loop
    
    For any review with severity "minor" or "none", should_enter_fix_loop
    SHALL return False.
    
    Feature: orchestration-fixes, Property 6
    Validates: Requirements 3.1
    """
    assert should_enter_fix_loop(severity) is False, \
        f"Severity {severity} should not enter fix loop"


@given(state=state_with_chain_dependencies_strategy())
@settings(max_examples=100, deadline=None)
def test_property_6_enter_fix_loop_blocks_dependents(state):
    """
    Property 6: Fix Loop Entry - Entering fix loop blocks dependent tasks
    
    For any task entering the fix loop, all tasks that depend on it
    (directly or transitively) SHALL be blocked.
    
    Feature: orchestration-fixes, Property 6
    Validates: Requirements 3.1, 3.2
    """
    chain_length = state["chain_length"]
    
    # Task 1 fails review - should block all downstream tasks (2, 3, 4, ...)
    failed_task_id = "1"
    findings = [{"severity": "critical", "summary": "Test failure", "details": None}]
    
    enter_fix_loop(state, failed_task_id, findings)
    
    # Check task 1 is in fix_required status
    task_1 = next(t for t in state["tasks"] if t["task_id"] == "1")
    assert task_1["status"] == "fix_required", "Failed task should be in fix_required status"
    
    # Check all downstream tasks are blocked
    for i in range(2, chain_length + 1):
        task = next(t for t in state["tasks"] if t["task_id"] == str(i))
        assert task["status"] == "blocked", f"Task {i} should be blocked"
        assert task["blocked_by"] == "1", f"Task {i} should be blocked by task 1"


@given(state=state_with_dependencies_strategy(), findings=review_findings_strategy())
@settings(max_examples=100, deadline=None)
def test_property_6_enter_fix_loop_stores_history(state, findings):
    """
    Property 6: Fix Loop Entry - Review history is stored
    
    When entering the fix loop, the review findings SHALL be stored
    in the task's review_history.
    
    Feature: orchestration-fixes, Property 6
    Validates: Requirements 3.1
    """
    # Ensure at least one critical/major finding
    findings[0]["severity"] = "critical"
    
    task_id = state["tasks"][0]["task_id"]
    
    enter_fix_loop(state, task_id, findings)
    
    task = next(t for t in state["tasks"] if t["task_id"] == task_id)
    
    # Check review history was added
    assert len(task["review_history"]) == 1, "Should have one review history entry"
    
    history_entry = task["review_history"][0]
    assert history_entry["attempt"] == 0, "First entry should be attempt 0 (initial review)"
    assert history_entry["severity"] in ["critical", "major"], "Severity should be recorded"
    assert history_entry["findings"] == findings, "Findings should be stored"
    assert "reviewed_at" in history_entry, "Timestamp should be recorded"


@given(state=state_with_dependencies_strategy())
@settings(max_examples=100, deadline=None)
def test_property_6_get_all_dependent_task_ids_transitive(state):
    """
    Property 6: Fix Loop Entry - Transitive dependents found
    
    get_all_dependent_task_ids SHALL return all tasks that depend on
    the given task, including transitive dependents.
    
    Feature: orchestration-fixes, Property 6
    Validates: Requirements 3.2
    """
    # Find a task that has dependents
    task_ids = [t["task_id"] for t in state["tasks"]]
    
    for task_id in task_ids:
        dependents = get_all_dependent_task_ids(state, task_id)
        
        # Verify all returned dependents actually depend on task_id (directly or transitively)
        for dep_id in dependents:
            dep_task = next(t for t in state["tasks"] if t["task_id"] == dep_id)
            
            # Check if dep_task depends on task_id directly or transitively
            # by checking if task_id is reachable from dep_task's dependencies
            visited = set()
            queue = list(dep_task.get("dependencies", []))
            found = False
            
            while queue and not found:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                
                if current == task_id:
                    found = True
                    break
                
                # Add dependencies of current
                current_task = next((t for t in state["tasks"] if t["task_id"] == current), None)
                if current_task:
                    queue.extend(current_task.get("dependencies", []))
            
            assert found, f"Task {dep_id} should depend on {task_id} (directly or transitively)"


@given(state=state_with_chain_dependencies_strategy())
@settings(max_examples=100, deadline=None)
def test_property_6_block_dependent_tasks_sets_reason(state):
    """
    Property 6: Fix Loop Entry - Blocked tasks have reason set
    
    When blocking dependent tasks, each blocked task SHALL have
    blocked_reason and blocked_by fields set.
    
    Feature: orchestration-fixes, Property 6
    Validates: Requirements 3.2
    """
    failed_task_id = "1"
    reason = "Test blocking reason"
    
    block_dependent_tasks(state, failed_task_id, reason)
    
    # Check all blocked tasks have reason and blocked_by set
    for task in state["tasks"]:
        if task["status"] == "blocked":
            assert task.get("blocked_reason") == reason, "Blocked reason should be set"
            assert task.get("blocked_by") == failed_task_id, "Blocked by should be set"
    
    # Check blocked_items was updated
    assert len(state["blocked_items"]) == 1, "Should have one blocked_items entry"
    blocked_item = state["blocked_items"][0]
    assert blocked_item["task_id"] == failed_task_id
    assert blocked_item["blocking_reason"] == reason


if __name__ == "__main__":
    import sys
    
    print("Running Property 6 tests...")
    print("=" * 50)
    
    tests = [
        ("Critical/major enters fix loop", test_property_6_critical_major_enters_fix_loop),
        ("Minor/none skips fix loop", test_property_6_minor_none_skips_fix_loop),
        ("Enter fix loop blocks dependents", test_property_6_enter_fix_loop_blocks_dependents),
        ("Enter fix loop stores history", test_property_6_enter_fix_loop_stores_history),
        ("Transitive dependents found", test_property_6_get_all_dependent_task_ids_transitive),
        ("Block sets reason", test_property_6_block_dependent_tasks_sets_reason),
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
# Property Tests for Fix Loop Retry Budget (Property 7)
# ============================================================================

from fix_loop import (
    evaluate_fix_loop_action,
    FixLoopAction,
)


@st.composite
def task_with_fix_attempts_strategy(draw, min_attempts=0, max_attempts=5):
    """Generate a task with a specific number of fix attempts."""
    task_id = draw(task_id_strategy())
    fix_attempts = draw(st.integers(min_value=min_attempts, max_value=max_attempts))
    
    return {
        "task_id": task_id,
        "description": f"Task {task_id}",
        "status": "fix_required",
        "fix_attempts": fix_attempts,
        "review_history": [],
    }


@given(task=task_with_fix_attempts_strategy(min_attempts=0, max_attempts=1))
@settings(max_examples=100, deadline=None)
def test_property_7_retry_before_escalation(task):
    """
    Property 7: Fix Loop Retry Budget - Retry before escalation threshold
    
    For any task with fewer than 2 completed fix attempts and critical/major
    severity, evaluate_fix_loop_action SHALL return RETRY.
    
    Feature: orchestration-fixes, Property 7
    Validates: Requirements 3.3
    """
    assume(task["fix_attempts"] < ESCALATION_THRESHOLD)
    
    action = evaluate_fix_loop_action(task, "critical")
    assert action == FixLoopAction.RETRY, \
        f"With {task['fix_attempts']} attempts, should RETRY, got {action}"
    
    action = evaluate_fix_loop_action(task, "major")
    assert action == FixLoopAction.RETRY, \
        f"With {task['fix_attempts']} attempts, should RETRY, got {action}"


@given(task=task_with_fix_attempts_strategy(min_attempts=2, max_attempts=2))
@settings(max_examples=100, deadline=None)
def test_property_7_escalate_at_threshold(task):
    """
    Property 7: Fix Loop Retry Budget - Escalate at threshold
    
    For any task with exactly 2 completed fix attempts and critical/major
    severity, evaluate_fix_loop_action SHALL return ESCALATE.
    
    Feature: orchestration-fixes, Property 7
    Validates: Requirements 3.6
    """
    assume(task["fix_attempts"] == ESCALATION_THRESHOLD)
    
    action = evaluate_fix_loop_action(task, "critical")
    assert action == FixLoopAction.ESCALATE, \
        f"With {task['fix_attempts']} attempts, should ESCALATE, got {action}"
    
    action = evaluate_fix_loop_action(task, "major")
    assert action == FixLoopAction.ESCALATE, \
        f"With {task['fix_attempts']} attempts, should ESCALATE, got {action}"


@given(task=task_with_fix_attempts_strategy(min_attempts=3, max_attempts=5))
@settings(max_examples=100, deadline=None)
def test_property_7_human_fallback_at_max(task):
    """
    Property 7: Fix Loop Retry Budget - Human fallback at max attempts
    
    For any task with 3 or more completed fix attempts and critical/major
    severity, evaluate_fix_loop_action SHALL return HUMAN_FALLBACK.
    
    Feature: orchestration-fixes, Property 7
    Validates: Requirements 3.7
    """
    assume(task["fix_attempts"] >= MAX_FIX_ATTEMPTS)
    
    action = evaluate_fix_loop_action(task, "critical")
    assert action == FixLoopAction.HUMAN_FALLBACK, \
        f"With {task['fix_attempts']} attempts, should HUMAN_FALLBACK, got {action}"
    
    action = evaluate_fix_loop_action(task, "major")
    assert action == FixLoopAction.HUMAN_FALLBACK, \
        f"With {task['fix_attempts']} attempts, should HUMAN_FALLBACK, got {action}"


@given(task=task_with_fix_attempts_strategy(), severity=st.sampled_from(["minor", "none"]))
@settings(max_examples=100, deadline=None)
def test_property_7_pass_on_minor_none(task, severity):
    """
    Property 7: Fix Loop Retry Budget - Pass on minor/none severity
    
    For any task with any number of fix attempts and minor/none severity,
    evaluate_fix_loop_action SHALL return PASS.
    
    Feature: orchestration-fixes, Property 7
    Validates: Requirements 3.3
    """
    action = evaluate_fix_loop_action(task, severity)
    assert action == FixLoopAction.PASS, \
        f"With severity {severity}, should PASS, got {action}"


@given(fix_attempts=st.integers(min_value=0, max_value=10))
@settings(max_examples=100, deadline=None)
def test_property_7_action_progression(fix_attempts):
    """
    Property 7: Fix Loop Retry Budget - Action progression
    
    For any number of fix attempts, the action SHALL follow this progression:
    - 0-1 attempts: RETRY
    - 2 attempts: ESCALATE
    - 3+ attempts: HUMAN_FALLBACK
    
    Feature: orchestration-fixes, Property 7
    Validates: Requirements 3.3, 3.6, 3.7
    """
    task = {"fix_attempts": fix_attempts}
    
    action = evaluate_fix_loop_action(task, "critical")
    
    if fix_attempts < ESCALATION_THRESHOLD:
        assert action == FixLoopAction.RETRY, \
            f"With {fix_attempts} attempts, expected RETRY, got {action}"
    elif fix_attempts < MAX_FIX_ATTEMPTS:
        assert action == FixLoopAction.ESCALATE, \
            f"With {fix_attempts} attempts, expected ESCALATE, got {action}"
    else:
        assert action == FixLoopAction.HUMAN_FALLBACK, \
            f"With {fix_attempts} attempts, expected HUMAN_FALLBACK, got {action}"


@settings(max_examples=1, deadline=None)
@given(st.just(None))
def test_property_7_specific_thresholds(_):
    """
    Property 7: Fix Loop Retry Budget - Specific threshold values
    
    Verify the exact threshold values:
    - ESCALATION_THRESHOLD = 2
    - MAX_FIX_ATTEMPTS = 3
    
    Feature: orchestration-fixes, Property 7
    Validates: Requirements 3.3, 3.6, 3.7
    """
    assert ESCALATION_THRESHOLD == 2, "Escalation threshold should be 2"
    assert MAX_FIX_ATTEMPTS == 3, "Max fix attempts should be 3"
    
    # Test boundary conditions
    task_0 = {"fix_attempts": 0}
    task_1 = {"fix_attempts": 1}
    task_2 = {"fix_attempts": 2}
    task_3 = {"fix_attempts": 3}
    
    assert evaluate_fix_loop_action(task_0, "critical") == FixLoopAction.RETRY
    assert evaluate_fix_loop_action(task_1, "critical") == FixLoopAction.RETRY
    assert evaluate_fix_loop_action(task_2, "critical") == FixLoopAction.ESCALATE
    assert evaluate_fix_loop_action(task_3, "critical") == FixLoopAction.HUMAN_FALLBACK



# ============================================================================
# Property Tests for Fix Prompt Content (Property 9)
# ============================================================================

from fix_loop import (
    create_fix_request,
    build_fix_prompt,
    format_review_history,
    FixRequest,
)


@st.composite
def state_with_task_for_fix_strategy(draw):
    """Generate a state with a task ready for fix request creation."""
    task_id = draw(task_id_strategy())
    fix_attempts = draw(st.integers(min_value=0, max_value=2))
    
    # Generate some review history
    num_history = draw(st.integers(min_value=0, max_value=fix_attempts))
    review_history = []
    for i in range(num_history):
        findings = draw(review_findings_strategy(min_findings=1, max_findings=3))
        review_history.append({
            "attempt": i,
            "severity": "critical" if any(f["severity"] == "critical" for f in findings) else "major",
            "findings": findings,
            "reviewed_at": "2024-01-01T00:00:00Z",
        })
    
    task = {
        "task_id": task_id,
        "description": f"Task {task_id} description",
        "status": "fix_required",
        "fix_attempts": fix_attempts,
        "review_history": review_history,
        "output": draw(st.text(min_size=10, max_size=500)),
    }
    
    state = {
        "tasks": [task],
        "blocked_items": [],
    }
    
    return {
        "state": state,
        "task_id": task_id,
        "task": task,
    }


@given(data=state_with_task_for_fix_strategy(), findings=review_findings_strategy())
@settings(max_examples=100, deadline=None)
def test_property_9_fix_prompt_includes_findings(data, findings):
    """
    Property 9: Fix Prompt Content - Includes critical/major findings
    
    For any fix prompt, the prompt SHALL include all critical and major
    findings from the review.
    
    Feature: orchestration-fixes, Property 9
    Validates: Requirements 6.1
    """
    # Ensure at least one critical/major finding
    findings[0]["severity"] = "critical"
    
    state = data["state"]
    task_id = data["task_id"]
    task = data["task"]
    
    fix_request = create_fix_request(state, task_id, findings)
    prompt = build_fix_prompt(fix_request, task)
    
    # Check that critical/major findings are in the prompt
    for finding in findings:
        if finding["severity"] in ["critical", "major"]:
            assert finding["summary"] in prompt, \
                f"Finding summary '{finding['summary']}' should be in prompt"


@given(data=state_with_task_for_fix_strategy())
@settings(max_examples=100, deadline=None)
def test_property_9_fix_prompt_includes_original_output(data):
    """
    Property 9: Fix Prompt Content - Includes original output
    
    For any fix prompt, the prompt SHALL include the original task output.
    
    Feature: orchestration-fixes, Property 9
    Validates: Requirements 6.2
    """
    state = data["state"]
    task_id = data["task_id"]
    task = data["task"]
    
    findings = [{"severity": "critical", "summary": "Test issue", "details": None}]
    
    fix_request = create_fix_request(state, task_id, findings)
    prompt = build_fix_prompt(fix_request, task)
    
    # Check that original output is in the prompt (possibly truncated)
    original_output = task.get("output", "")
    if len(original_output) > 2000:
        # Should be truncated
        assert original_output[:100] in prompt or "..." in prompt, \
            "Truncated output should be in prompt"
    else:
        assert original_output in prompt, \
            "Original output should be in prompt"


@given(data=state_with_task_for_fix_strategy())
@settings(max_examples=100, deadline=None)
def test_property_9_fix_prompt_includes_attempt_number(data):
    """
    Property 9: Fix Prompt Content - Includes attempt number
    
    For any fix prompt, the prompt SHALL clearly indicate the attempt
    number (e.g., "Attempt 2/3").
    
    Feature: orchestration-fixes, Property 9
    Validates: Requirements 6.3
    """
    state = data["state"]
    task_id = data["task_id"]
    task = data["task"]
    
    findings = [{"severity": "critical", "summary": "Test issue", "details": None}]
    
    fix_request = create_fix_request(state, task_id, findings)
    prompt = build_fix_prompt(fix_request, task)
    
    # Check that attempt number is in the prompt
    expected_attempt = task["fix_attempts"] + 1
    assert f"Attempt {expected_attempt}/{MAX_FIX_ATTEMPTS}" in prompt, \
        f"Attempt number should be in prompt as 'Attempt {expected_attempt}/{MAX_FIX_ATTEMPTS}'"


@st.composite
def state_with_escalation_task_strategy(draw):
    """Generate a state with a task that requires escalation (2+ attempts)."""
    task_id = draw(task_id_strategy())
    
    # Generate review history with 2+ entries
    review_history = []
    for i in range(2):
        findings = draw(review_findings_strategy(min_findings=1, max_findings=2))
        findings[0]["severity"] = "critical"  # Ensure critical
        review_history.append({
            "attempt": i,
            "severity": "critical",
            "findings": findings,
            "reviewed_at": f"2024-01-0{i+1}T00:00:00Z",
        })
    
    task = {
        "task_id": task_id,
        "description": f"Task {task_id} description",
        "status": "fix_required",
        "fix_attempts": 2,  # At escalation threshold
        "review_history": review_history,
        "output": draw(st.text(min_size=10, max_size=200)),
    }
    
    state = {
        "tasks": [task],
        "blocked_items": [],
    }
    
    return {
        "state": state,
        "task_id": task_id,
        "task": task,
        "review_history": review_history,
    }


@given(data=state_with_escalation_task_strategy())
@settings(max_examples=100, deadline=None)
def test_property_9_escalation_includes_full_history(data):
    """
    Property 9: Fix Prompt Content - Escalation includes full history
    
    When escalating to a different agent, the prompt SHALL include
    the full fix history.
    
    Feature: orchestration-fixes, Property 9
    Validates: Requirements 6.5
    """
    state = data["state"]
    task_id = data["task_id"]
    task = data["task"]
    review_history = data["review_history"]
    
    findings = [{"severity": "critical", "summary": "Latest issue", "details": None}]
    
    fix_request = create_fix_request(state, task_id, findings)
    
    # Should be escalation (2 completed attempts)
    assert fix_request.use_escalation_agent, "Should be escalation at 2 attempts"
    
    prompt = build_fix_prompt(fix_request, task)
    
    # Check that history section is included
    assert "Previous Fix Attempts History" in prompt, \
        "Escalation prompt should include history section"
    
    # Check that previous findings are mentioned
    for entry in review_history:
        for finding in entry.get("findings", []):
            if finding["severity"] in ["critical", "major"]:
                # The summary should appear somewhere in the history
                assert finding["summary"] in prompt, \
                    f"Previous finding '{finding['summary']}' should be in history"


@given(data=state_with_task_for_fix_strategy())
@settings(max_examples=100, deadline=None)
def test_property_9_non_escalation_no_history(data):
    """
    Property 9: Fix Prompt Content - Non-escalation excludes history
    
    When not escalating (< 2 attempts), the prompt SHALL NOT include
    the full fix history section.
    
    Feature: orchestration-fixes, Property 9
    Validates: Requirements 6.5
    """
    state = data["state"]
    task_id = data["task_id"]
    task = data["task"]
    
    # Ensure not at escalation threshold
    task["fix_attempts"] = 0
    
    findings = [{"severity": "critical", "summary": "Test issue", "details": None}]
    
    fix_request = create_fix_request(state, task_id, findings)
    
    # Should not be escalation
    assert not fix_request.use_escalation_agent, "Should not be escalation at 0 attempts"
    
    prompt = build_fix_prompt(fix_request, task)
    
    # Check that history section is NOT included
    assert "Previous Fix Attempts History" not in prompt, \
        "Non-escalation prompt should not include history section"


@given(history=st.lists(
    st.fixed_dictionaries({
        "attempt": st.integers(min_value=0, max_value=3),
        "severity": st.sampled_from(["critical", "major", "minor"]),
        "findings": review_findings_strategy(min_findings=1, max_findings=2),
        "reviewed_at": st.just("2024-01-01T00:00:00Z"),
    }),
    min_size=0,
    max_size=3
))
@settings(max_examples=100, deadline=None)
def test_property_9_format_review_history_structure(history):
    """
    Property 9: Fix Prompt Content - Review history formatting
    
    format_review_history SHALL produce a structured string with
    attempt headers and findings.
    
    Feature: orchestration-fixes, Property 9
    Validates: Requirements 6.5
    """
    formatted = format_review_history(history)
    
    if not history:
        assert formatted == "No previous attempts.", \
            "Empty history should return 'No previous attempts.'"
    else:
        # Check that each entry has a header
        for entry in history:
            attempt = entry["attempt"]
            if attempt == 0:
                assert "Initial Implementation Review" in formatted, \
                    "Should have initial review header"
            else:
                assert f"Fix Attempt {attempt} Review" in formatted, \
                    f"Should have attempt {attempt} header"
        
        # Check that severity is mentioned
        for entry in history:
            assert entry["severity"] in formatted.lower(), \
                f"Severity {entry['severity']} should be in formatted history"


# ============================================================================
# Property 11: Fix Attempts Increment
# Feature: orchestration-fixes, Property 11
# Validates: Requirements 7.1, 7.4, 7.5, 7.6
# ============================================================================

from fix_loop import on_fix_task_complete, rollback_fix_dispatch


@st.composite
def state_with_in_progress_fix_task_strategy(draw):
    """Generate state with a task in in_progress status (simulating fix dispatch)."""
    task_id = draw(task_id_strategy())
    initial_fix_attempts = draw(st.integers(min_value=0, max_value=2))
    
    task = {
        "task_id": task_id,
        "description": f"Task {task_id}",
        "status": "in_progress",  # Set by process_fix_loop before dispatch
        "fix_attempts": initial_fix_attempts,
        "review_history": [],
    }
    
    state = {
        "tasks": [task],
        "blocked_items": [],
        "pending_decisions": [],
    }
    
    return state, task_id, initial_fix_attempts


@given(data=state_with_in_progress_fix_task_strategy())
@settings(max_examples=100, deadline=None)
def test_property_11_fix_attempts_increments_on_complete(data):
    """
    Property 11: Fix Attempts Increment - Increments on successful completion
    
    *For any* fix task that completes successfully, the system shall increment
    fix_attempts by exactly 1.
    
    Feature: orchestration-fixes, Property 11
    Validates: Requirements 7.1, 7.6
    """
    state, task_id, initial_attempts = data
    
    # Call on_fix_task_complete (simulating successful fix)
    on_fix_task_complete(state, task_id)
    
    task = next(t for t in state["tasks"] if t["task_id"] == task_id)
    
    # fix_attempts should be incremented by exactly 1
    assert task["fix_attempts"] == initial_attempts + 1, \
        f"fix_attempts should be {initial_attempts + 1}, got {task['fix_attempts']}"
    
    # Status should transition to pending_review
    assert task["status"] == "pending_review", \
        f"Status should be pending_review, got {task['status']}"


@given(data=state_with_in_progress_fix_task_strategy())
@settings(max_examples=100, deadline=None)
def test_property_11_fix_attempts_unchanged_on_rollback(data):
    """
    Property 11: Fix Attempts Increment - Unchanged on dispatch failure
    
    *For any* fix task dispatch that fails, the system shall NOT increment
    fix_attempts and shall rollback the task status to fix_required.
    
    Feature: orchestration-fixes, Property 11
    Validates: Requirements 7.4, 7.5
    """
    state, task_id, initial_attempts = data
    
    # Call rollback_fix_dispatch (simulating dispatch failure)
    rollback_fix_dispatch(state, task_id)
    
    task = next(t for t in state["tasks"] if t["task_id"] == task_id)
    
    # fix_attempts should NOT be incremented
    assert task["fix_attempts"] == initial_attempts, \
        f"fix_attempts should remain {initial_attempts}, got {task['fix_attempts']}"
    
    # Status should be rolled back to fix_required
    assert task["status"] == "fix_required", \
        f"Status should be fix_required, got {task['status']}"


@given(initial_attempts=st.integers(min_value=0, max_value=5))
@settings(max_examples=100, deadline=None)
def test_property_11_rollback_only_from_in_progress(initial_attempts):
    """
    Property 11: Fix Attempts Increment - Rollback only from in_progress
    
    rollback_fix_dispatch should only change status if currently in_progress.
    
    Feature: orchestration-fixes, Property 11
    Validates: Requirements 7.4, 7.5
    """
    # Test with fix_required status (should not change)
    state = {
        "tasks": [{
            "task_id": "1",
            "description": "Task 1",
            "status": "fix_required",
            "fix_attempts": initial_attempts,
        }],
    }
    
    rollback_fix_dispatch(state, "1")
    
    task = state["tasks"][0]
    # Status should remain fix_required (no change)
    assert task["status"] == "fix_required", \
        "Status should remain fix_required when already fix_required"
    assert task["fix_attempts"] == initial_attempts, \
        "fix_attempts should not change"


@given(num_completions=st.integers(min_value=1, max_value=5))
@settings(max_examples=100, deadline=None)
def test_property_11_multiple_completions_accumulate(num_completions):
    """
    Property 11: Fix Attempts Increment - Multiple completions accumulate
    
    *For any* sequence of fix completions, fix_attempts should equal the
    number of completed fix attempts.
    
    Feature: orchestration-fixes, Property 11
    Validates: Requirements 7.3, 7.6
    """
    state = {
        "tasks": [{
            "task_id": "1",
            "description": "Task 1",
            "status": "in_progress",
            "fix_attempts": 0,
        }],
    }
    
    # Simulate multiple fix completions
    for i in range(num_completions):
        # Reset status to in_progress (simulating re-dispatch after review failure)
        state["tasks"][0]["status"] = "in_progress"
        on_fix_task_complete(state, "1")
    
    task = state["tasks"][0]
    assert task["fix_attempts"] == num_completions, \
        f"fix_attempts should be {num_completions} after {num_completions} completions"
