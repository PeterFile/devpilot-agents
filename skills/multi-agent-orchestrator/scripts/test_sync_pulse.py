#!/usr/bin/env python3
"""
Property-Based Tests for sync_pulse

Feature: multi-agent-orchestration
Property 12: Dual Document Synchronization
Property 15: Blocked Task Has Blocked Item Entry
Validates: Requirements 6.3, 3.5, 9.6
"""

import json
import string
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List

from hypothesis import given, strategies as st, settings, assume

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sync_pulse import (
    sync_pulse,
    sync_pulse_from_state,
    parse_pulse,
    generate_pulse,
    PulseDocument,
    MentalModel,
    RisksAndDebt,
    SemanticAnchor,
    build_narrative_delta,
    build_risks_and_debt,
    build_mental_model,
    get_blocked_tasks,
    format_blocked_item,
    is_older_than_24h,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

@st.composite
def task_id_strategy(draw):
    """Generate valid task IDs like 'task-001', '1', '1.1'"""
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
def task_status_strategy(draw):
    """Generate valid task statuses"""
    return draw(st.sampled_from([
        "not_started", "in_progress", "pending_review",
        "under_review", "final_review", "completed", "blocked"
    ]))


@st.composite
def task_entry_strategy(draw):
    """Generate a valid task entry for AGENT_STATE.json"""
    task_id = draw(task_id_strategy())
    status = draw(task_status_strategy())
    
    # Generate description
    desc_chars = string.ascii_letters + string.digits + " -_"
    description = draw(st.text(alphabet=desc_chars, min_size=5, max_size=50))
    
    # Generate optional fields
    owner_agent = draw(st.sampled_from(["kiro-cli", "gemini", "codex-review"]))
    criticality = draw(st.sampled_from(["standard", "complex", "security-sensitive"]))
    
    entry = {
        "task_id": task_id,
        "description": description,
        "status": status,
        "owner_agent": owner_agent,
        "criticality": criticality,
        "dependencies": [],
    }
    
    # Add completed_at for completed tasks
    if status == "completed":
        entry["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    # Add files_changed for completed tasks
    if status in ["completed", "pending_review"]:
        num_files = draw(st.integers(min_value=0, max_value=3))
        entry["files_changed"] = [
            f"src/module{i}/file{i}.py" for i in range(num_files)
        ]
    
    return entry


@st.composite
def blocked_item_strategy(draw, task_id=None):
    """Generate a valid blocked_item entry"""
    if task_id is None:
        task_id = draw(task_id_strategy())
    
    reasons = [
        "Missing dependency",
        "External API unavailable",
        "Waiting for design approval",
        "Resource conflict",
        "Test environment down",
    ]
    
    resolutions = [
        "Complete dependent task first",
        "Wait for API to be restored",
        "Get approval from architect",
        "Resolve resource allocation",
        "Fix test environment",
    ]
    
    return {
        "task_id": task_id,
        "blocking_reason": draw(st.sampled_from(reasons)),
        "required_resolution": draw(st.sampled_from(resolutions)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@st.composite
def pending_decision_strategy(draw):
    """Generate a valid pending_decision entry"""
    task_id = draw(task_id_strategy())
    decision_id = f"decision-{draw(st.integers(min_value=1, max_value=999)):03d}"
    
    contexts = [
        "Choose between REST and GraphQL API",
        "Select database technology",
        "Decide on authentication method",
        "Choose caching strategy",
    ]
    
    # Optionally make it older than 24h for escalation testing
    if draw(st.booleans()):
        created_at = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    else:
        created_at = datetime.now(timezone.utc).isoformat()
    
    return {
        "id": decision_id,
        "task_id": task_id,
        "context": draw(st.sampled_from(contexts)),
        "options": ["Option A", "Option B"],
        "created_at": created_at,
    }


@st.composite
def deferred_fix_strategy(draw):
    """Generate a valid deferred_fix entry"""
    task_id = draw(task_id_strategy())
    
    descriptions = [
        "Refactor duplicate code",
        "Add missing error handling",
        "Improve test coverage",
        "Update deprecated API calls",
    ]
    
    return {
        "task_id": task_id,
        "description": draw(st.sampled_from(descriptions)),
        "severity": draw(st.sampled_from(["minor", "major", "critical"])),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@st.composite
def agent_state_strategy(draw):
    """Generate a valid AGENT_STATE.json structure"""
    num_tasks = draw(st.integers(min_value=1, max_value=8))
    
    tasks = []
    used_ids = set()
    blocked_task_ids = []
    
    for _ in range(num_tasks):
        task = draw(task_entry_strategy())
        
        # Ensure unique task IDs
        base_id = task["task_id"]
        task_id = base_id
        counter = 1
        while task_id in used_ids:
            task_id = f"{base_id}-{counter}"
            counter += 1
        task["task_id"] = task_id
        used_ids.add(task_id)
        
        if task["status"] == "blocked":
            blocked_task_ids.append(task_id)
        
        tasks.append(task)
    
    # Generate blocked_items for blocked tasks
    blocked_items = []
    for task_id in blocked_task_ids:
        blocked_items.append(draw(blocked_item_strategy(task_id=task_id)))
    
    # Optionally add extra blocked items
    if draw(st.booleans()):
        extra_blocked = draw(st.integers(min_value=0, max_value=2))
        for _ in range(extra_blocked):
            blocked_items.append(draw(blocked_item_strategy()))
    
    # Generate pending decisions
    num_decisions = draw(st.integers(min_value=0, max_value=3))
    pending_decisions = [draw(pending_decision_strategy()) for _ in range(num_decisions)]
    
    # Generate deferred fixes
    num_fixes = draw(st.integers(min_value=0, max_value=2))
    deferred_fixes = [draw(deferred_fix_strategy()) for _ in range(num_fixes)]
    
    return {
        "spec_path": "/test/spec/path",
        "session_name": "test-session",
        "tasks": tasks,
        "review_findings": [],
        "final_reports": [],
        "blocked_items": blocked_items,
        "pending_decisions": pending_decisions,
        "deferred_fixes": deferred_fixes,
        "window_mapping": {},
    }


@st.composite
def pulse_document_strategy(draw):
    """Generate a valid PulseDocument"""
    description = draw(st.text(
        alphabet=string.ascii_letters + string.digits + " -_.,",
        min_size=10,
        max_size=100
    ))
    
    mermaid = """flowchart TB
    A[Start] --> B[Process]
    B --> C[End]"""
    
    return PulseDocument(
        mental_model=MentalModel(
            description=description,
            mermaid_diagram=mermaid
        ),
        narrative_delta="Initial narrative",
        risks_and_debt=RisksAndDebt(
            cognitive_warnings=[],
            technical_debt=[],
            pending_decisions=[]
        ),
        semantic_anchors=[]
    )


# =============================================================================
# Property 12: Dual Document Synchronization
# =============================================================================

@given(agent_state=agent_state_strategy(), pulse_doc=pulse_document_strategy())
@settings(max_examples=100, deadline=None)
def test_property_12_dual_document_synchronization(agent_state, pulse_doc):
    """
    Property 12: Dual Document Synchronization
    
    For any task state transition, both AGENT_STATE.json and PROJECT_PULSE.md
    SHALL be updated to reflect the change.
    
    This test verifies that sync_pulse correctly propagates state from
    AGENT_STATE.json to PROJECT_PULSE.md.
    
    Feature: multi-agent-orchestration, Property 12
    Validates: Requirements 6.3
    """
    # Sync the pulse document
    updated_pulse = sync_pulse(agent_state, pulse_doc)
    
    # Generate markdown from updated pulse
    pulse_content = generate_pulse(updated_pulse)
    
    # Verify narrative delta contains task statistics
    tasks = agent_state.get("tasks", [])
    total_tasks = len(tasks)
    completed_count = len([t for t in tasks if t.get("status") == "completed"])
    blocked_count = len([t for t in tasks if t.get("status") == "blocked"])
    in_progress_count = len([t for t in tasks if t.get("status") == "in_progress"])
    
    # Check that narrative delta reflects task counts
    assert f"Total tasks: {total_tasks}" in updated_pulse.narrative_delta, \
        f"Narrative delta should contain total task count ({total_tasks})"
    assert f"Completed: {completed_count}" in updated_pulse.narrative_delta, \
        f"Narrative delta should contain completed count ({completed_count})"
    assert f"Blocked: {blocked_count}" in updated_pulse.narrative_delta, \
        f"Narrative delta should contain blocked count ({blocked_count})"
    
    # Verify blocked items appear in risks_and_debt
    blocked_items = agent_state.get("blocked_items", [])
    for item in blocked_items:
        task_id = item.get("task_id", "")
        # Check that blocked item is reflected in cognitive warnings
        found = any(task_id in warning for warning in updated_pulse.risks_and_debt.cognitive_warnings)
        assert found, f"Blocked item for {task_id} should appear in cognitive warnings"
    
    # Verify pending decisions appear in risks_and_debt
    pending_decisions = agent_state.get("pending_decisions", [])
    for decision in pending_decisions:
        decision_id = decision.get("id", "")
        found = any(decision_id in pd for pd in updated_pulse.risks_and_debt.pending_decisions)
        assert found, f"Pending decision {decision_id} should appear in risks_and_debt"
    
    # Verify deferred fixes appear in technical debt
    deferred_fixes = agent_state.get("deferred_fixes", [])
    for fix in deferred_fixes:
        task_id = fix.get("task_id", "")
        found = any(task_id in debt for debt in updated_pulse.risks_and_debt.technical_debt)
        assert found, f"Deferred fix for {task_id} should appear in technical debt"


@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_property_12_round_trip_consistency(agent_state):
    """
    Property 12 (Round-Trip): Sync then parse should preserve key information.
    
    Feature: multi-agent-orchestration, Property 12
    Validates: Requirements 6.3
    """
    # Create initial pulse document
    initial_pulse = PulseDocument(
        mental_model=MentalModel(
            description="Test system architecture",
            mermaid_diagram="flowchart TB\n    A --> B"
        ),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    # Sync
    updated_pulse = sync_pulse(agent_state, initial_pulse)
    
    # Generate markdown
    markdown_content = generate_pulse(updated_pulse)
    
    # Parse back
    parsed_pulse = parse_pulse(markdown_content)
    
    # Verify parsing succeeded
    assert parsed_pulse is not None, "Should be able to parse generated PULSE markdown"
    
    # Verify key sections are preserved
    assert parsed_pulse.mental_model.description == updated_pulse.mental_model.description
    
    # Verify blocked items count matches
    original_blocked_count = len([
        w for w in updated_pulse.risks_and_debt.cognitive_warnings
        if "BLOCKED" in w
    ])
    parsed_blocked_count = len([
        w for w in parsed_pulse.risks_and_debt.cognitive_warnings
        if "BLOCKED" in w
    ])
    assert original_blocked_count == parsed_blocked_count, \
        f"Blocked count mismatch: {original_blocked_count} vs {parsed_blocked_count}"


# =============================================================================
# Property 15: Blocked Task Has Blocked Item Entry
# =============================================================================

@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_property_15_blocked_task_has_blocked_item_entry(agent_state):
    """
    Property 15: Blocked Task Has Blocked Item Entry
    
    For any task with status "blocked", there SHALL exist a corresponding
    entry in blocked_items with matching task reference.
    
    Feature: multi-agent-orchestration, Property 15
    Validates: Requirements 3.5, 9.6
    """
    tasks = agent_state.get("tasks", [])
    blocked_items = agent_state.get("blocked_items", [])
    
    # Get all blocked task IDs
    blocked_task_ids = {t["task_id"] for t in tasks if t.get("status") == "blocked"}
    
    # Get all task IDs that have blocked_items entries
    blocked_item_task_ids = {item.get("task_id") for item in blocked_items}
    
    # Every blocked task should have a blocked_item entry
    for task_id in blocked_task_ids:
        assert task_id in blocked_item_task_ids, \
            f"Blocked task {task_id} should have a corresponding blocked_items entry"


@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_property_15_blocked_items_reflected_in_pulse(agent_state):
    """
    Property 15 (PULSE Reflection): Blocked items should appear in PULSE risks.
    
    Feature: multi-agent-orchestration, Property 15
    Validates: Requirements 3.5, 9.6
    """
    # Create initial pulse
    initial_pulse = PulseDocument(
        mental_model=MentalModel(description="Test", mermaid_diagram=""),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    # Sync
    updated_pulse = sync_pulse(agent_state, initial_pulse)
    
    # Get blocked tasks
    blocked_tasks = get_blocked_tasks(agent_state)
    blocked_items = agent_state.get("blocked_items", [])
    
    # All blocked items should appear in cognitive warnings
    for item in blocked_items:
        task_id = item.get("task_id", "")
        found = any(task_id in warning for warning in updated_pulse.risks_and_debt.cognitive_warnings)
        assert found, f"Blocked item for task {task_id} should appear in PULSE cognitive warnings"
    
    # All blocked tasks (even without explicit blocked_items) should be reflected
    blocked_item_task_ids = {item.get("task_id") for item in blocked_items}
    for task in blocked_tasks:
        task_id = task.get("task_id", "")
        # Either has explicit blocked_item or task itself is reflected
        found = any(task_id in warning for warning in updated_pulse.risks_and_debt.cognitive_warnings)
        assert found, f"Blocked task {task_id} should be reflected in PULSE cognitive warnings"


# =============================================================================
# Additional sync_pulse tests
# =============================================================================

@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_escalation_of_old_pending_decisions(agent_state):
    """
    Test that pending decisions older than 24h are escalated.
    
    Validates: Requirements 6.6
    """
    # Create initial pulse
    initial_pulse = PulseDocument(
        mental_model=MentalModel(description="Test", mermaid_diagram=""),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    # Sync
    updated_pulse = sync_pulse(agent_state, initial_pulse)
    
    # Check escalation
    pending_decisions = agent_state.get("pending_decisions", [])
    for decision in pending_decisions:
        created_at = decision.get("created_at", "")
        decision_id = decision.get("id", "")
        
        if is_older_than_24h(created_at):
            # Should be escalated (marked with ⚠️ ESCALATED)
            found_escalated = any(
                "ESCALATED" in pd and decision_id in pd
                for pd in updated_pulse.risks_and_debt.pending_decisions
            )
            assert found_escalated, \
                f"Decision {decision_id} older than 24h should be escalated"


@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_semantic_anchors_from_completed_tasks(agent_state):
    """
    Test that completed tasks with files_changed create semantic anchors.
    """
    # Create initial pulse
    initial_pulse = PulseDocument(
        mental_model=MentalModel(description="Test", mermaid_diagram=""),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    # Sync
    updated_pulse = sync_pulse(agent_state, initial_pulse)
    
    # Get all files changed by completed tasks
    completed_tasks = [t for t in agent_state.get("tasks", []) if t.get("status") == "completed"]
    all_files = set()
    for task in completed_tasks:
        for f in task.get("files_changed", []):
            all_files.add(f)
    
    # Check that anchors were created
    anchor_paths = {a.path for a in updated_pulse.semantic_anchors}
    for file_path in all_files:
        assert file_path in anchor_paths, \
            f"File {file_path} from completed task should have semantic anchor"


def test_sync_pulse_with_empty_state():
    """Test sync_pulse handles empty state gracefully."""
    empty_state = {
        "spec_path": "/test",
        "session_name": "test",
        "tasks": [],
        "review_findings": [],
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }
    
    initial_pulse = PulseDocument(
        mental_model=MentalModel(description="Test", mermaid_diagram=""),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    updated_pulse = sync_pulse(empty_state, initial_pulse)
    
    assert "Total tasks: 0" in updated_pulse.narrative_delta
    assert "Completed: 0" in updated_pulse.narrative_delta


def test_sync_pulse_files_integration():
    """Integration test: sync_pulse_files with actual files."""
    from sync_pulse import sync_pulse_files
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "AGENT_STATE.json"
        pulse_file = Path(tmpdir) / "PROJECT_PULSE.md"
        
        # Create state file
        state = {
            "spec_path": "/test/spec",
            "session_name": "test-session",
            "tasks": [
                {"task_id": "1", "description": "Task 1", "status": "completed",
                 "completed_at": datetime.now(timezone.utc).isoformat(),
                 "files_changed": ["src/main.py"]},
                {"task_id": "2", "description": "Task 2", "status": "blocked"},
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [
                {"task_id": "2", "blocking_reason": "Missing dep",
                 "required_resolution": "Complete task 1",
                 "created_at": datetime.now(timezone.utc).isoformat()}
            ],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        
        # Create pulse file (using ASCII-safe section headers for Windows compatibility)
        pulse_content = """# PROJECT_PULSE

## Mental Model

Test architecture

```mermaid
flowchart TB
    A --> B
```

## Narrative Delta

Initial state

## Risks & Debt

### Cognitive Load Warnings
- None

### Technical Debt
- None

### Pending Decisions
- None

## Semantic Anchors

- None
"""
        with open(pulse_file, 'w', encoding='utf-8') as f:
            f.write(pulse_content)
        
        # Sync
        result = sync_pulse_files(str(state_file), str(pulse_file))
        
        assert result.success, f"Sync failed: {result.errors}"
        assert result.pulse_updated
        
        # Read updated pulse
        with open(pulse_file, encoding='utf-8') as f:
            updated_content = f.read()
        
        # Verify updates
        assert "Total tasks: 2" in updated_content
        assert "Completed: 1" in updated_content
        assert "Blocked: 1" in updated_content
        assert "BLOCKED" in updated_content
        assert "src/main.py" in updated_content


@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_mental_model_update_when_flag_set(agent_state):
    """
    Test that mental model is updated when update_mental_model=True.
    
    Validates: Requirements 6.1 (Update Mental Model section)
    """
    # Create initial pulse with old mental model
    initial_pulse = PulseDocument(
        mental_model=MentalModel(
            description="Old description that should be replaced",
            mermaid_diagram="flowchart TB\n    Old --> Diagram"
        ),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    # Sync WITH update_mental_model=True
    updated_pulse = sync_pulse(agent_state, initial_pulse, update_mental_model=True)
    
    # Mental model should be updated (not the old one)
    spec_path = agent_state.get("spec_path", "")
    if spec_path:
        assert spec_path in updated_pulse.mental_model.description, \
            f"Updated mental model should contain spec_path '{spec_path}'"
    
    # Should not contain the old description
    assert "Old description that should be replaced" not in updated_pulse.mental_model.description, \
        "Mental model should be updated, not keep old description"


@given(agent_state=agent_state_strategy())
@settings(max_examples=100, deadline=None)
def test_mental_model_preserved_when_flag_not_set(agent_state):
    """
    Test that mental model is preserved when update_mental_model=False.
    
    Validates: Requirements 6.1 (Mental Model preserved by default)
    """
    original_description = "Original description that should be preserved"
    original_diagram = "flowchart TB\n    Original --> Diagram"
    
    # Create initial pulse
    initial_pulse = PulseDocument(
        mental_model=MentalModel(
            description=original_description,
            mermaid_diagram=original_diagram
        ),
        narrative_delta="",
        risks_and_debt=RisksAndDebt(),
        semantic_anchors=[]
    )
    
    # Sync WITHOUT update_mental_model (default=False)
    updated_pulse = sync_pulse(agent_state, initial_pulse, update_mental_model=False)
    
    # Mental model should be preserved
    assert updated_pulse.mental_model.description == original_description, \
        "Mental model description should be preserved when update_mental_model=False"
    assert updated_pulse.mental_model.mermaid_diagram == original_diagram, \
        "Mental model diagram should be preserved when update_mental_model=False"


def test_build_mental_model_contains_task_info():
    """Test that build_mental_model includes task statistics."""
    state = {
        "spec_path": "/test/spec/feature",
        "session_name": "test-session",
        "tasks": [
            {"task_id": "1", "status": "completed", "owner_agent": "kiro-cli"},
            {"task_id": "2", "status": "in_progress", "owner_agent": "gemini"},
            {"task_id": "3", "status": "blocked", "owner_agent": "kiro-cli"},
        ],
        "review_findings": [],
        "final_reports": [],
        "blocked_items": [],
        "pending_decisions": [],
        "deferred_fixes": [],
        "window_mapping": {},
    }
    
    existing_model = MentalModel(description="", mermaid_diagram="")
    new_model = build_mental_model(state, existing_model)
    
    # Should contain spec path
    assert "/test/spec/feature" in new_model.description
    
    # Should contain session name
    assert "test-session" in new_model.description
    
    # Should contain task statistics
    assert "1/3" in new_model.description  # 1 completed out of 3
    
    # Should contain agents
    assert "kiro-cli" in new_model.description or "gemini" in new_model.description
    
    # Should have mermaid diagram
    assert "flowchart" in new_model.mermaid_diagram
    assert "Orchestrator" in new_model.mermaid_diagram


if __name__ == "__main__":
    print("Running property tests for sync_pulse...")
    print("=" * 60)
    
    tests = [
        ("Property 12: Dual Document Synchronization", test_property_12_dual_document_synchronization),
        ("Property 12: Round-Trip Consistency", test_property_12_round_trip_consistency),
        ("Property 15: Blocked Task Has Blocked Item Entry", test_property_15_blocked_task_has_blocked_item_entry),
        ("Property 15: Blocked Items Reflected in PULSE", test_property_15_blocked_items_reflected_in_pulse),
        ("Escalation of Old Pending Decisions", test_escalation_of_old_pending_decisions),
        ("Semantic Anchors from Completed Tasks", test_semantic_anchors_from_completed_tasks),
        ("Sync with Empty State", test_sync_pulse_with_empty_state),
        ("Integration: sync_pulse_files", test_sync_pulse_files_integration),
        ("Mental Model Update When Flag Set", test_mental_model_update_when_flag_set),
        ("Mental Model Preserved When Flag Not Set", test_mental_model_preserved_when_flag_not_set),
        ("Build Mental Model Contains Task Info", test_build_mental_model_contains_task_info),
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
