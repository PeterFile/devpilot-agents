#!/usr/bin/env python3
"""
Property-Based Tests for Review Consolidation

Feature: multi-agent-orchestration
Property 10: Review Completion Triggers Consolidation
Validates: Requirements 8.9
"""

import json
import string
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from hypothesis import given, strategies as st, settings, assume

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from consolidate_reviews import (
    consolidate_reviews,
    consolidate_single_task,
    consolidate_findings,
    determine_overall_severity,
    generate_summary,
    get_review_findings_for_task,
    get_tasks_in_final_review,
    has_existing_final_report,
    FinalReport,
    SEVERITY_ORDER,
)
from dispatch_reviews import REVIEW_COUNT_BY_CRITICALITY


# =============================================================================
# Strategies for generating test data
# =============================================================================

@st.composite
def task_id_strategy(draw):
    """Generate valid task IDs"""
    style = draw(st.sampled_from(["prefixed", "numeric", "dotted"]))
    if style == "prefixed":
        num = draw(st.integers(min_value=1, max_value=999))
        return f"task-{num:03d}"
    elif style == "numeric":
        return str(draw(st.integers(min_value=1, max_value=99)))
    else:
        major = draw(st.integers(min_value=1, max_value=20))
        minor = draw(st.integers(min_value=1, max_value=10))
        return f"{major}.{minor}"


@st.composite
def severity_strategy(draw):
    """Generate valid severity levels"""
    return draw(st.sampled_from(["critical", "major", "minor", "none"]))


@st.composite
def criticality_strategy(draw):
    """Generate valid criticality levels"""
    return draw(st.sampled_from(["standard", "complex", "security-sensitive"]))


@st.composite
def review_finding_strategy(draw, task_id=None):
    """Generate a valid review finding"""
    if task_id is None:
        task_id = draw(task_id_strategy())
    
    reviewer_index = draw(st.integers(min_value=1, max_value=3))
    severity = draw(severity_strategy())
    
    summaries = [
        "Code looks good",
        "Found potential issue",
        "Security concern identified",
        "Minor style improvements needed",
        "LGTM",
    ]
    
    return {
        "task_id": task_id,
        "reviewer": f"review-{task_id}-{reviewer_index}",
        "severity": severity,
        "summary": draw(st.sampled_from(summaries)),
        "details": "Detailed review notes",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@st.composite
def task_in_final_review_strategy(draw):
    """Generate a task in final_review status with complete reviews"""
    task_id = draw(task_id_strategy())
    criticality = draw(criticality_strategy())
    required_reviews = REVIEW_COUNT_BY_CRITICALITY.get(criticality, 1)
    
    # Generate the required number of review findings
    findings = []
    for i in range(required_reviews):
        finding = draw(review_finding_strategy(task_id=task_id))
        finding["reviewer"] = f"review-{task_id}-{i+1}"
        findings.append(finding)
    
    task = {
        "task_id": task_id,
        "description": f"Task {task_id} description",
        "status": "final_review",
        "criticality": criticality,
        "owner_agent": "kiro-cli",
        "dependencies": [],
    }
    
    return {"task": task, "findings": findings, "required_reviews": required_reviews}


@st.composite
def agent_state_with_final_review_tasks_strategy(draw):
    """Generate AGENT_STATE with tasks ready for consolidation"""
    num_tasks = draw(st.integers(min_value=1, max_value=5))
    
    tasks = []
    all_findings = []
    used_ids = set()
    
    for _ in range(num_tasks):
        task_data = draw(task_in_final_review_strategy())
        task = task_data["task"]
        findings = task_data["findings"]
        
        # Ensure unique task IDs
        base_id = task["task_id"]
        task_id = base_id
        counter = 1
        while task_id in used_ids:
            task_id = f"{base_id}-{counter}"
            counter += 1
        
        task["task_id"] = task_id
        for finding in findings:
            finding["task_id"] = task_id
            finding["reviewer"] = finding["reviewer"].replace(base_id, task_id)
        
        used_ids.add(task_id)
        tasks.append(task)
        all_findings.extend(findings)
    
    return {
        "spec_path": "/test/spec",
        "session_name": "test-session",
        "tasks": tasks,
        "review_findings": all_findings,
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }


# =============================================================================
# Property 10: Review Completion Triggers Consolidation
# =============================================================================

@given(state=agent_state_with_final_review_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_property_10_review_completion_triggers_consolidation(state):
    """
    Property 10: Review Completion Triggers Consolidation
    
    For any task where all required Review_Codex instances have completed,
    the system SHALL produce a FinalReport in AGENT_STATE.json containing
    consolidated findings.
    
    Feature: multi-agent-orchestration, Property 10
    Validates: Requirements 8.9
    """
    # Get tasks in final_review (these have all reviews complete)
    tasks_in_final_review = get_tasks_in_final_review(state)
    
    # Consolidate each task
    for task in tasks_in_final_review:
        task_id = task["task_id"]
        
        # Get findings for this task
        findings = get_review_findings_for_task(state, task_id)
        
        # Verify we have the required number of findings
        criticality = task.get("criticality", "standard")
        required_count = REVIEW_COUNT_BY_CRITICALITY.get(criticality, 1)
        assert len(findings) >= required_count, \
            f"Task {task_id} should have at least {required_count} findings, got {len(findings)}"
        
        # Consolidate
        report = consolidate_single_task(state, task_id, auto_complete=False)
        
        # Verify final report was created
        assert report is not None, \
            f"FinalReport should be created for task {task_id} with complete reviews"
        
        # Verify report contains correct task_id
        assert report.task_id == task_id, \
            f"FinalReport task_id should be {task_id}, got {report.task_id}"
        
        # Verify finding count matches
        assert report.finding_count == len(findings), \
            f"FinalReport finding_count should be {len(findings)}, got {report.finding_count}"
        
        # Verify overall severity is valid
        assert report.overall_severity in SEVERITY_ORDER, \
            f"FinalReport overall_severity should be valid, got {report.overall_severity}"
        
        # Verify report is in state
        assert has_existing_final_report(state, task_id), \
            f"FinalReport should be added to state for task {task_id}"


@given(findings=st.lists(review_finding_strategy(), min_size=1, max_size=5))
@settings(max_examples=100, deadline=None)
def test_overall_severity_is_highest(findings):
    """
    Test that overall severity is the highest severity among findings.
    
    Feature: multi-agent-orchestration, Property 10
    Validates: Requirements 8.9
    """
    overall = determine_overall_severity(findings)
    
    # Get all severities
    severities = [f.get("severity", "none") for f in findings]
    
    # Overall should be the highest (earliest in SEVERITY_ORDER)
    for severity in SEVERITY_ORDER:
        if severity in severities:
            assert overall == severity, \
                f"Overall severity should be {severity} (highest), got {overall}"
            break


@given(state=agent_state_with_final_review_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_consolidation_marks_task_completed(state):
    """
    Test that consolidation with auto_complete marks task as completed
    when severity is minor or none. Tasks with critical/major severity
    enter the fix loop instead.
    
    Feature: multi-agent-orchestration, Property 10
    Validates: Requirements 8.9, 3.1, 4.6
    """
    tasks_in_final_review = get_tasks_in_final_review(state)
    assume(len(tasks_in_final_review) > 0)
    
    task = tasks_in_final_review[0]
    task_id = task["task_id"]
    
    # Get findings to determine expected outcome
    findings = get_review_findings_for_task(state, task_id)
    severities = [f.get("severity", "none") for f in findings]
    has_critical_or_major = "critical" in severities or "major" in severities
    
    # Consolidate with auto_complete=True
    report = consolidate_single_task(state, task_id, auto_complete=True)
    
    assert report is not None
    
    # Find task in state
    updated_task = next(
        (t for t in state["tasks"] if t["task_id"] == task_id),
        None
    )
    
    assert updated_task is not None
    
    if has_critical_or_major:
        # Tasks with critical/major severity enter fix loop (Req 3.1, 4.6)
        assert updated_task["status"] == "fix_required", \
            f"Task with critical/major severity should enter fix_required, got {updated_task['status']}"
    else:
        # Tasks with minor/none severity are completed
        assert updated_task["status"] == "completed", \
            f"Task with minor/none severity should be completed, got {updated_task['status']}"
        assert "completed_at" in updated_task, \
            "Task should have completed_at timestamp"


@given(state=agent_state_with_final_review_tasks_strategy())
@settings(max_examples=100, deadline=None)
def test_consolidation_idempotent(state):
    """
    Test that consolidation is idempotent - running twice doesn't create duplicates.
    
    Feature: multi-agent-orchestration, Property 10
    Validates: Requirements 8.9
    """
    tasks_in_final_review = get_tasks_in_final_review(state)
    assume(len(tasks_in_final_review) > 0)
    
    task = tasks_in_final_review[0]
    task_id = task["task_id"]
    
    # First consolidation
    report1 = consolidate_single_task(state, task_id, auto_complete=False)
    assert report1 is not None
    
    initial_report_count = len(state.get("final_reports", []))
    
    # Second consolidation (should be no-op)
    report2 = consolidate_single_task(state, task_id, auto_complete=False)
    assert report2 is None, "Second consolidation should return None (already exists)"
    
    final_report_count = len(state.get("final_reports", []))
    assert final_report_count == initial_report_count, \
        "Report count should not increase on second consolidation"


@given(severity=severity_strategy())
@settings(max_examples=100, deadline=None)
def test_single_finding_severity_preserved(severity):
    """
    Test that a single finding's severity becomes the overall severity.
    """
    findings = [{
        "task_id": "test-1",
        "reviewer": "review-test-1-1",
        "severity": severity,
        "summary": "Test finding",
    }]
    
    overall = determine_overall_severity(findings)
    assert overall == severity, \
        f"Single finding severity {severity} should be overall severity, got {overall}"


def test_empty_findings_returns_none():
    """Test that empty findings returns 'none' severity."""
    overall = determine_overall_severity([])
    assert overall == "none"


def test_consolidate_reviews_file_integration():
    """Integration test: consolidate_reviews with actual files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        
        # Create state with tasks in final_review
        state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {
                    "task_id": "task-001",
                    "description": "Implement feature",
                    "status": "final_review",
                    "criticality": "standard",
                    "owner_agent": "kiro-cli",
                },
                {
                    "task_id": "task-002",
                    "description": "Implement UI",
                    "status": "final_review",
                    "criticality": "complex",
                    "owner_agent": "gemini",
                },
            ],
            "review_findings": [
                {
                    "task_id": "task-001",
                    "reviewer": "review-task-001-1",
                    "severity": "minor",
                    "summary": "Minor style issue",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "task_id": "task-002",
                    "reviewer": "review-task-002-1",
                    "severity": "none",
                    "summary": "LGTM",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "task_id": "task-002",
                    "reviewer": "review-task-002-2",
                    "severity": "major",
                    "summary": "Found bug",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            ],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        
        # Consolidate
        result = consolidate_reviews(str(state_file), auto_complete=True)
        
        assert result.success, f"Consolidation failed: {result.errors}"
        assert result.reports_created == 2, \
            f"Should create 2 reports, got {result.reports_created}"
        
        # Read updated state
        with open(state_file, encoding='utf-8') as f:
            updated_state = json.load(f)
        
        # Verify final reports
        assert len(updated_state["final_reports"]) == 2
        
        # Check task-001 report (minor severity - should be completed)
        report1 = next(
            (r for r in updated_state["final_reports"] if r["task_id"] == "task-001"),
            None
        )
        assert report1 is not None
        assert report1["overall_severity"] == "minor"
        assert report1["finding_count"] == 1
        
        # Check task-002 report (should be major - highest severity)
        report2 = next(
            (r for r in updated_state["final_reports"] if r["task_id"] == "task-002"),
            None
        )
        assert report2 is not None
        assert report2["overall_severity"] == "major"
        assert report2["finding_count"] == 2
        
        # Verify task statuses based on severity (Req 3.1, 4.6)
        task1 = next(t for t in updated_state["tasks"] if t["task_id"] == "task-001")
        task2 = next(t for t in updated_state["tasks"] if t["task_id"] == "task-002")
        
        # task-001 has minor severity - should be completed
        assert task1["status"] == "completed", \
            f"Task task-001 with minor severity should be completed, got {task1['status']}"
        
        # task-002 has major severity - should enter fix loop
        assert task2["status"] == "fix_required", \
            f"Task task-002 with major severity should enter fix_required, got {task2['status']}"


def test_consolidate_no_tasks():
    """Test consolidation with no tasks in final_review."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        
        state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {"task_id": "1", "status": "in_progress"},
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        
        result = consolidate_reviews(str(state_file))
        
        assert result.success
        assert result.reports_created == 0
        assert "No tasks to consolidate" in result.message


def test_summary_generation():
    """Test summary generation for different severity combinations."""
    # All none
    findings_none = [
        {"severity": "none", "task_id": "1"},
        {"severity": "none", "task_id": "1"},
    ]
    summary = generate_summary(findings_none, "1")
    assert "passed" in summary.lower() or "no issues" in summary.lower()
    
    # Has critical
    findings_critical = [
        {"severity": "critical", "task_id": "2"},
        {"severity": "minor", "task_id": "2"},
    ]
    summary = generate_summary(findings_critical, "2")
    assert "CRITICAL" in summary
    
    # Has major
    findings_major = [
        {"severity": "major", "task_id": "3"},
        {"severity": "none", "task_id": "3"},
    ]
    summary = generate_summary(findings_major, "3")
    assert "major" in summary.lower()


if __name__ == "__main__":
    print("Running property tests for review consolidation...")
    print("=" * 60)
    
    tests = [
        ("Property 10: Review Completion Triggers Consolidation", 
         test_property_10_review_completion_triggers_consolidation),
        ("Overall Severity is Highest", test_overall_severity_is_highest),
        ("Consolidation Marks Task Completed", test_consolidation_marks_task_completed),
        ("Consolidation is Idempotent", test_consolidation_idempotent),
        ("Single Finding Severity Preserved", test_single_finding_severity_preserved),
        ("Empty Findings Returns None", test_empty_findings_returns_none),
        ("Integration: consolidate_reviews File", test_consolidate_reviews_file_integration),
        ("No Tasks to Consolidate", test_consolidate_no_tasks),
        ("Summary Generation", test_summary_generation),
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
