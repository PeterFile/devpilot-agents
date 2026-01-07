#!/usr/bin/env python3
"""
End-to-End Integration Tests for Multi-Agent Orchestration

Tests the full orchestration flow:
- Initialize from sample spec directory
- Verify AGENT_STATE.json creation and structure
- Verify PROJECT_PULSE.md creation and updates
- Test dispatch batch (dry-run mode)
- Test sync_pulse updates

Requirements: All (Integration Testing)
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from spec_parser import parse_tasks, validate_spec_directory, TaskStatus, TaskType
from init_orchestration import initialize_orchestration, AGENT_BY_TASK_TYPE
from dispatch_batch import dispatch_batch, get_ready_tasks, build_task_configs, load_agent_state
from sync_pulse import sync_pulse_files, parse_pulse, generate_pulse
from fix_loop import (
    enter_fix_loop,
    evaluate_fix_loop_action,
    process_fix_loop,
    on_fix_task_complete,
    on_review_complete,
    handle_fix_loop_success,
    trigger_human_fallback,
    get_fix_required_tasks,
    FixLoopAction,
    MAX_FIX_ATTEMPTS,
    ESCALATION_THRESHOLD,
)
from consolidate_reviews import consolidate_single_task


# Sample spec content for testing
SAMPLE_REQUIREMENTS_MD = """# Requirements Document

## Introduction

A sample feature for end-to-end testing of multi-agent orchestration.

## Glossary

- **System**: The test system under development
- **User**: End user of the system

## Requirements

### Requirement 1: User Authentication

**User Story:** As a user, I want to authenticate securely, so that my data is protected.

#### Acceptance Criteria

1. WHEN a user provides valid credentials, THE System SHALL grant access
2. WHEN a user provides invalid credentials, THE System SHALL deny access
3. IF authentication fails 3 times, THEN THE System SHALL lock the account

### Requirement 2: User Interface

**User Story:** As a user, I want a clean login interface, so that I can easily access the system.

#### Acceptance Criteria

1. THE System SHALL display a login form with username and password fields
2. WHEN the form is submitted, THE System SHALL validate inputs
"""

SAMPLE_DESIGN_MD = """# Design Document

## Overview

This system implements user authentication with a clean UI interface.
The architecture uses a modular approach with separate components for auth and UI.

```mermaid
flowchart TB
    User([User]) --> UI[Login UI]
    UI --> Auth[Auth Service]
    Auth --> DB[(Database)]
```

## Components and Interfaces

### Auth Service
Handles user authentication logic.

### Login UI
Provides the user interface for login.

## Data Models

### User
- username: string
- password_hash: string
- locked: boolean

## Correctness Properties

### Property 1: Authentication Round-Trip
*For any* valid user credentials, authenticating and then checking session SHALL return the same user.

**Validates: Requirements 1.1**

### Property 2: Invalid Credentials Rejection
*For any* invalid credentials, authentication SHALL fail and return an error.

**Validates: Requirements 1.2**

## Error Handling

| Error | Handling |
|-------|----------|
| Invalid credentials | Return 401 Unauthorized |
| Account locked | Return 403 Forbidden |

## Testing Strategy

- Unit tests for auth logic
- Property tests for authentication properties
- Integration tests for full flow
"""

SAMPLE_TASKS_MD = """# Implementation Plan: User Authentication

## Overview

Implementation plan for user authentication feature.

## Tasks

- [ ] 1 Set up project structure
  - Create directory structure
  - Initialize dependencies
  - _Requirements: 1.1_

- [ ] 2 Implement authentication service
  - [ ] 2.1 Create auth module
    - Implement password hashing
    - Implement token generation
    - _Requirements: 1.1, 1.2_
  - [ ] 2.2 Add account locking
    - Track failed attempts
    - Lock after 3 failures
    - _Requirements: 1.3_

- [ ] 3 Create login UI
  - [ ] 3.1 Build login form component
    - Username and password fields
    - Submit button
    - _Requirements: 2.1_
  - [ ] 3.2 Add form validation
    - Client-side validation
    - Error display
    - _Requirements: 2.2_

- [ ] 4 Integration and testing
  - Wire components together
  - Write integration tests
  - _Requirements: 1.1, 2.1_
"""


def create_sample_spec_directory(base_dir: str) -> str:
    """Create a sample spec directory with all required files."""
    spec_dir = Path(base_dir) / "test-feature"
    spec_dir.mkdir(parents=True, exist_ok=True)
    
    (spec_dir / "requirements.md").write_text(SAMPLE_REQUIREMENTS_MD)
    (spec_dir / "design.md").write_text(SAMPLE_DESIGN_MD)
    (spec_dir / "tasks.md").write_text(SAMPLE_TASKS_MD)
    
    return str(spec_dir)


def verify_agent_state_structure(state: Dict[str, Any]) -> list:
    """Verify AGENT_STATE.json has all required fields."""
    errors = []
    
    required_fields = [
        "spec_path",
        "session_name",
        "tasks",
        "review_findings",
        "final_reports",
        "blocked_items",
        "pending_decisions",
        "deferred_fixes",
        "window_mapping",
    ]
    
    for field in required_fields:
        if field not in state:
            errors.append(f"Missing required field: {field}")
    
    # Verify types
    if "spec_path" in state and not isinstance(state["spec_path"], str):
        errors.append("spec_path must be string")
    if "session_name" in state and not isinstance(state["session_name"], str):
        errors.append("session_name must be string")
    if "tasks" in state and not isinstance(state["tasks"], list):
        errors.append("tasks must be array")
    if "window_mapping" in state and not isinstance(state["window_mapping"], dict):
        errors.append("window_mapping must be object")
    
    return errors


def verify_task_entry_structure(task: Dict[str, Any]) -> list:
    """Verify a task entry has all required fields."""
    errors = []
    
    required_fields = [
        "task_id",
        "description",
        "type",
        "status",
        "owner_agent",
        "dependencies",
        "criticality",
    ]
    
    for field in required_fields:
        if field not in task:
            errors.append(f"Task missing field: {field}")
    
    # Verify valid values
    valid_statuses = ["not_started", "in_progress", "pending_review", 
                     "under_review", "final_review", "completed", "blocked"]
    if task.get("status") not in valid_statuses:
        errors.append(f"Invalid status: {task.get('status')}")
    
    valid_criticalities = ["standard", "complex", "security-sensitive"]
    if task.get("criticality") not in valid_criticalities:
        errors.append(f"Invalid criticality: {task.get('criticality')}")
    
    valid_agents = ["kiro-cli", "gemini", "codex-review"]
    if task.get("owner_agent") not in valid_agents:
        errors.append(f"Invalid owner_agent: {task.get('owner_agent')}")
    
    return errors


def verify_pulse_structure(content: str) -> list:
    """Verify PROJECT_PULSE.md has all required sections."""
    errors = []
    
    required_sections = [
        "Mental Model",
        "Narrative Delta",
        "Risks & Debt",
        "Semantic Anchors",
    ]
    
    for section in required_sections:
        if section not in content:
            errors.append(f"Missing section: {section}")
    
    return errors


class TestE2EOrchestration:
    """End-to-end integration tests for orchestration."""
    
    def test_spec_directory_validation(self):
        """Test spec directory validation with valid spec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            
            result = validate_spec_directory(spec_path)
            
            assert result.valid, f"Validation failed: {result.errors}"
            assert result.spec_path == spec_path
            assert len(result.missing_files) == 0
    
    def test_spec_directory_validation_missing_files(self):
        """Test spec directory validation with missing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = Path(tmpdir) / "incomplete-spec"
            spec_path.mkdir()
            
            # Only create requirements.md
            (spec_path / "requirements.md").write_text("# Requirements")
            
            result = validate_spec_directory(str(spec_path))
            
            assert not result.valid
            assert len(result.errors) > 0
    
    def test_task_parsing(self):
        """Test parsing tasks from tasks.md."""
        result = parse_tasks(SAMPLE_TASKS_MD)
        
        assert result.success, f"Parsing failed: {result.errors}"
        assert len(result.tasks) > 0
        
        # Verify task IDs are extracted
        task_ids = [t.task_id for t in result.tasks]
        assert "1" in task_ids
        assert "2.1" in task_ids or "2" in task_ids
    
    def test_initialization_creates_state_file(self):
        """Test initialization creates AGENT_STATE.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert result.success, f"Initialization failed: {result.errors}"
            assert result.state_file is not None
            assert os.path.exists(result.state_file)
            
            # Verify state file structure
            with open(result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            errors = verify_agent_state_structure(state)
            assert len(errors) == 0, f"State structure errors: {errors}"
    
    def test_initialization_creates_pulse_file(self):
        """Test initialization creates PROJECT_PULSE.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert result.success, f"Initialization failed: {result.errors}"
            assert result.pulse_file is not None
            assert os.path.exists(result.pulse_file)
            
            # Verify PULSE structure
            with open(result.pulse_file, encoding='utf-8') as f:
                content = f.read()
            
            errors = verify_pulse_structure(content)
            assert len(errors) == 0, f"PULSE structure errors: {errors}"
    
    def test_initialization_task_entries(self):
        """Test initialization creates correct task entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            with open(result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            # Verify tasks were created
            assert len(state["tasks"]) > 0
            
            # Verify each task has correct structure
            for task in state["tasks"]:
                errors = verify_task_entry_structure(task)
                assert len(errors) == 0, f"Task {task.get('task_id')} errors: {errors}"
            
            # Verify all tasks start as not_started
            for task in state["tasks"]:
                assert task["status"] == "not_started"
    
    def test_get_ready_tasks(self):
        """Test getting ready tasks (no unmet dependencies)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            with open(result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            ready_tasks = get_ready_tasks(state)
            
            # Should have at least one ready task (tasks without dependencies)
            assert len(ready_tasks) > 0
            
            # Ready tasks should have no unmet dependencies
            completed_ids = set()  # Initially empty
            for task in ready_tasks:
                deps = task.get("dependencies", [])
                for dep in deps:
                    assert dep in completed_ids, f"Task {task['task_id']} has unmet dependency {dep}"
    
    def test_build_task_configs(self):
        """Test building task configs for codeagent-wrapper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            with open(result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            ready_tasks = get_ready_tasks(state)
            configs = build_task_configs(ready_tasks, spec_path)
            
            assert len(configs) == len(ready_tasks)
            
            for config in configs:
                assert config.task_id is not None
                assert config.backend in ["kiro-cli", "gemini", "codex"]
                assert config.content is not None
                
                # Verify heredoc format
                heredoc = config.to_heredoc()
                assert "---TASK---" in heredoc
                assert "---CONTENT---" in heredoc
                assert f"id: {config.task_id}" in heredoc
    
    def test_dispatch_batch_dry_run(self):
        """Test dispatch batch in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            init_result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert init_result.success
            
            # Dispatch in dry-run mode
            dispatch_result = dispatch_batch(
                init_result.state_file,
                workdir=".",
                dry_run=True
            )
            
            assert dispatch_result.success
            assert dispatch_result.tasks_dispatched > 0
    
    def test_sync_pulse_updates(self):
        """Test sync_pulse updates PROJECT_PULSE.md correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            init_result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert init_result.success
            
            # Modify state to simulate progress
            with open(init_result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            # Mark first task as completed
            if state["tasks"]:
                state["tasks"][0]["status"] = "completed"
                state["tasks"][0]["completed_at"] = "2026-01-06T10:00:00Z"
            
            # Add a blocked item
            state["blocked_items"].append({
                "task_id": "test-blocked",
                "blocking_reason": "Test blocking reason",
                "required_resolution": "Fix the issue",
                "created_at": "2026-01-06T10:00:00Z"
            })
            
            with open(init_result.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Sync PULSE
            sync_result = sync_pulse_files(
                init_result.state_file,
                init_result.pulse_file,
                update_mental_model=True
            )
            
            assert sync_result.success, f"Sync failed: {sync_result.errors}"
            assert sync_result.pulse_updated
            
            # Verify PULSE was updated
            with open(init_result.pulse_file, encoding='utf-8') as f:
                pulse_content = f.read()
            
            # Should contain progress info
            assert "Completed:" in pulse_content or "completed" in pulse_content.lower()
            
            # Should contain blocked item
            assert "BLOCKED" in pulse_content or "blocked" in pulse_content.lower()
    
    def test_full_orchestration_flow(self):
        """Test complete orchestration flow end-to-end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            # Step 1: Initialize
            init_result = initialize_orchestration(
                spec_path,
                session_name="e2e-test-session",
                output_dir=str(output_dir)
            )
            
            assert init_result.success, f"Init failed: {init_result.errors}"
            
            # Verify initial state
            state = load_agent_state(init_result.state_file)
            assert state["session_name"] == "e2e-test-session"
            assert len(state["tasks"]) > 0
            
            initial_task_count = len(state["tasks"])
            
            # Step 2: Get ready tasks
            ready_tasks = get_ready_tasks(state)
            assert len(ready_tasks) > 0, "Should have ready tasks"
            
            # Step 3: Dispatch (dry-run)
            dispatch_result = dispatch_batch(
                init_result.state_file,
                dry_run=True
            )
            
            assert dispatch_result.success
            assert dispatch_result.tasks_dispatched > 0
            
            # Step 4: Simulate task completion
            state = load_agent_state(init_result.state_file)
            completed_count = 0
            for task in state["tasks"]:
                if task["status"] == "not_started" and not task.get("dependencies"):
                    task["status"] = "completed"
                    task["completed_at"] = "2026-01-06T12:00:00Z"
                    task["files_changed"] = ["src/test.py"]
                    completed_count += 1
                    if completed_count >= 2:
                        break
            
            with open(init_result.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Step 5: Sync PULSE
            sync_result = sync_pulse_files(
                init_result.state_file,
                init_result.pulse_file,
                update_mental_model=True
            )
            
            assert sync_result.success
            
            # Step 6: Verify final state
            final_state = load_agent_state(init_result.state_file)
            
            # Task count should be unchanged
            assert len(final_state["tasks"]) == initial_task_count
            
            # Some tasks should be completed
            completed_tasks = [t for t in final_state["tasks"] if t["status"] == "completed"]
            assert len(completed_tasks) > 0
            
            # Verify PULSE reflects changes
            with open(init_result.pulse_file, encoding='utf-8') as f:
                pulse_content = f.read()
            
            # Should have all required sections
            errors = verify_pulse_structure(pulse_content)
            assert len(errors) == 0, f"Final PULSE errors: {errors}"
            
            print(f"✅ Full orchestration flow completed successfully")
            print(f"   - Tasks initialized: {initial_task_count}")
            print(f"   - Tasks dispatched (dry-run): {dispatch_result.tasks_dispatched}")
            print(f"   - Tasks completed: {len(completed_tasks)}")
    
    def test_agent_assignment_by_task_type(self):
        """Test that agents are correctly assigned based on task type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = create_sample_spec_directory(tmpdir)
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                spec_path,
                session_name="test-session",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            with open(result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            for task in state["tasks"]:
                task_type = task.get("type", "code")
                owner_agent = task.get("owner_agent")
                
                # Verify agent assignment matches task type
                if task_type == "code":
                    assert owner_agent == "kiro-cli", f"Code task should use kiro-cli, got {owner_agent}"
                elif task_type == "ui":
                    assert owner_agent == "gemini", f"UI task should use gemini, got {owner_agent}"
                elif task_type == "review":
                    assert owner_agent == "codex-review", f"Review task should use codex-review, got {owner_agent}"
    
    def test_dependency_tracking(self):
        """Test that task dependencies are correctly tracked."""
        # Create tasks.md with explicit dependencies
        tasks_with_deps = """# Tasks

- [ ] 1 First task
  - No dependencies
  
- [ ] 2 Second task
  - dependencies: 1
  
- [ ] 3 Third task
  - dependencies: 1, 2
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = Path(tmpdir) / "dep-test"
            spec_path.mkdir()
            
            (spec_path / "requirements.md").write_text(SAMPLE_REQUIREMENTS_MD)
            (spec_path / "design.md").write_text(SAMPLE_DESIGN_MD)
            (spec_path / "tasks.md").write_text(tasks_with_deps)
            
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            result = initialize_orchestration(
                str(spec_path),
                session_name="dep-test",
                output_dir=str(output_dir)
            )
            
            assert result.success
            
            with open(result.state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            # Get ready tasks - only task 1 should be ready
            ready = get_ready_tasks(state)
            ready_ids = [t["task_id"] for t in ready]
            
            assert "1" in ready_ids, "Task 1 should be ready (no dependencies)"
            # Tasks 2 and 3 should not be ready (have dependencies)
            assert "2" not in ready_ids, "Task 2 should not be ready (depends on task 1)"
            assert "3" not in ready_ids, "Task 3 should not be ready (depends on task 2)"

    # =========================================================================
    # Fix Loop Integration Tests
    # =========================================================================
    
    def test_fix_loop_initial_review_failure_to_fix_to_success(self):
        """
        Test fix loop workflow: initial review failure → fix → re-review → success.
        
        Requirements: 3.1, 3.5, 3.9, 4.6
        """
        # Create initial state with a task in final_review
        state = {
            "spec_path": "/test/spec",
            "session_name": "fix-loop-test",
            "tasks": [
                {
                    "task_id": "task-001",
                    "description": "Implement feature",
                    "status": "final_review",
                    "type": "code",
                    "owner_agent": "kiro-cli",
                    "dependencies": [],
                    "criticality": "standard",
                },
                {
                    "task_id": "task-002",
                    "description": "Dependent task",
                    "status": "not_started",
                    "type": "code",
                    "owner_agent": "kiro-cli",
                    "dependencies": ["task-001"],
                    "criticality": "standard",
                },
            ],
            "review_findings": [
                {
                    "task_id": "task-001",
                    "reviewer": "review-task-001-1",
                    "severity": "major",
                    "summary": "Found bug in implementation",
                    "details": "The function doesn't handle edge cases",
                    "created_at": "2026-01-07T10:00:00Z",
                },
            ],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        # Step 1: Consolidate review - should enter fix loop due to major severity
        report = consolidate_single_task(state, "task-001", auto_complete=True)
        
        assert report is not None
        assert report.overall_severity == "major"
        
        # Verify task entered fix loop
        task = next(t for t in state["tasks"] if t["task_id"] == "task-001")
        assert task["status"] == "fix_required", \
            f"Task should be in fix_required status, got {task['status']}"
        assert task.get("fix_attempts", 0) == 0, \
            "fix_attempts should be 0 (no fix completed yet)"
        assert len(task.get("review_history", [])) == 1, \
            "Should have 1 review history entry"
        
        # Verify dependent task is blocked
        dep_task = next(t for t in state["tasks"] if t["task_id"] == "task-002")
        assert dep_task["status"] == "blocked", \
            f"Dependent task should be blocked, got {dep_task['status']}"
        assert dep_task.get("blocked_by") == "task-001"
        
        # Step 2: Process fix loop - should create fix request
        fix_requests = process_fix_loop(state)
        
        assert len(fix_requests) == 1, "Should have 1 fix request"
        fix_req = fix_requests[0]
        assert fix_req["task_id"] == "task-001"
        assert not fix_req["use_escalation"], "Should not escalate on first attempt"
        
        # Verify task is now in_progress
        task = next(t for t in state["tasks"] if t["task_id"] == "task-001")
        assert task["status"] == "in_progress"
        
        # Step 3: Simulate fix completion
        on_fix_task_complete(state, "task-001")
        
        task = next(t for t in state["tasks"] if t["task_id"] == "task-001")
        assert task["fix_attempts"] == 1, "fix_attempts should be 1 after first fix"
        assert task["status"] == "pending_review"
        
        # Step 4: Simulate successful re-review
        on_review_complete(state, "task-001", [
            {"severity": "none", "summary": "All issues fixed"}
        ])
        
        task = next(t for t in state["tasks"] if t["task_id"] == "task-001")
        assert task["status"] == "final_review", \
            f"Task should be in final_review after passing review, got {task['status']}"
        
        # Verify dependent task is unblocked
        dep_task = next(t for t in state["tasks"] if t["task_id"] == "task-002")
        assert dep_task["status"] == "not_started", \
            f"Dependent task should be unblocked, got {dep_task['status']}"
        assert dep_task.get("blocked_by") is None
        
        print("✅ Fix loop: initial failure → fix → success workflow completed")
    
    def test_fix_loop_escalation_after_2_failures(self):
        """
        Test fix loop escalation after 2 failed fix attempts.
        
        Requirements: 3.3, 3.6
        """
        # Create state with task that has already had 2 failed fix attempts
        state = {
            "spec_path": "/test/spec",
            "session_name": "escalation-test",
            "tasks": [
                {
                    "task_id": "task-001",
                    "description": "Implement feature",
                    "status": "fix_required",
                    "type": "code",
                    "owner_agent": "kiro-cli",
                    "dependencies": [],
                    "criticality": "standard",
                    "fix_attempts": 2,  # 2 completed fix attempts
                    "last_review_severity": "major",
                    "review_history": [
                        {
                            "attempt": 0,
                            "severity": "major",
                            "findings": [{"severity": "major", "summary": "Initial bug"}],
                            "reviewed_at": "2026-01-07T10:00:00Z",
                        },
                        {
                            "attempt": 1,
                            "severity": "major",
                            "findings": [{"severity": "major", "summary": "Bug still present"}],
                            "reviewed_at": "2026-01-07T11:00:00Z",
                        },
                        {
                            "attempt": 2,
                            "severity": "major",
                            "findings": [{"severity": "major", "summary": "Bug persists"}],
                            "reviewed_at": "2026-01-07T12:00:00Z",
                        },
                    ],
                },
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        # Evaluate action - should escalate
        task = state["tasks"][0]
        action = evaluate_fix_loop_action(task, "major")
        
        assert action == FixLoopAction.ESCALATE, \
            f"Should escalate after 2 failed attempts, got {action}"
        
        # Process fix loop - should create escalated fix request
        fix_requests = process_fix_loop(state)
        
        assert len(fix_requests) == 1
        fix_req = fix_requests[0]
        assert fix_req["use_escalation"], "Should use escalation agent"
        assert fix_req["backend"] == "codex", "Should use codex backend for escalation"
        
        # Verify task is marked as escalated
        task = state["tasks"][0]
        assert task.get("escalated") is True
        assert task.get("escalated_at") is not None
        assert task.get("original_agent") == "kiro-cli"
        
        print("✅ Fix loop: escalation after 2 failures workflow completed")
    
    def test_fix_loop_human_fallback_after_3_failures(self):
        """
        Test fix loop human fallback after 3 failed fix attempts.
        
        Requirements: 3.7, 3.8
        """
        # Create state with task that has already had 3 failed fix attempts
        state = {
            "spec_path": "/test/spec",
            "session_name": "human-fallback-test",
            "tasks": [
                {
                    "task_id": "task-001",
                    "description": "Implement feature",
                    "status": "fix_required",
                    "type": "code",
                    "owner_agent": "kiro-cli",
                    "dependencies": [],
                    "criticality": "standard",
                    "fix_attempts": 3,  # 3 completed fix attempts (max)
                    "last_review_severity": "critical",
                    "escalated": True,
                    "review_history": [
                        {
                            "attempt": 0,
                            "severity": "critical",
                            "findings": [{"severity": "critical", "summary": "Security issue"}],
                            "reviewed_at": "2026-01-07T10:00:00Z",
                        },
                        {
                            "attempt": 1,
                            "severity": "critical",
                            "findings": [{"severity": "critical", "summary": "Issue not fixed"}],
                            "reviewed_at": "2026-01-07T11:00:00Z",
                        },
                        {
                            "attempt": 2,
                            "severity": "critical",
                            "findings": [{"severity": "critical", "summary": "Still broken"}],
                            "reviewed_at": "2026-01-07T12:00:00Z",
                        },
                        {
                            "attempt": 3,
                            "severity": "critical",
                            "findings": [{"severity": "critical", "summary": "Cannot fix"}],
                            "reviewed_at": "2026-01-07T13:00:00Z",
                        },
                    ],
                },
                {
                    "task_id": "task-002",
                    "description": "Dependent task",
                    "status": "not_started",
                    "type": "code",
                    "owner_agent": "kiro-cli",
                    "dependencies": ["task-001"],
                    "criticality": "standard",
                },
            ],
            "review_findings": [],
            "final_reports": [],
            "blocked_items": [],
            "pending_decisions": [],
            "deferred_fixes": [],
            "window_mapping": {},
        }
        
        # Evaluate action - should trigger human fallback
        task = state["tasks"][0]
        action = evaluate_fix_loop_action(task, "critical")
        
        assert action == FixLoopAction.HUMAN_FALLBACK, \
            f"Should trigger human fallback after 3 failed attempts, got {action}"
        
        # Process fix loop - should trigger human fallback
        fix_requests = process_fix_loop(state)
        
        # No fix requests should be created (human fallback instead)
        assert len(fix_requests) == 0, "Should not create fix request for human fallback"
        
        # Verify task is blocked with human intervention required
        task = state["tasks"][0]
        assert task["status"] == "blocked"
        assert task.get("blocked_reason") == "human_intervention_required"
        
        # Verify pending decision was created
        assert len(state["pending_decisions"]) == 1
        decision = state["pending_decisions"][0]
        assert decision["task_id"] == "task-001"
        assert decision["priority"] == "critical"
        assert "HUMAN INTERVENTION REQUIRED" in decision["context"]
        assert len(decision["options"]) == 3
        
        # Verify dependent task is blocked
        dep_task = next(t for t in state["tasks"] if t["task_id"] == "task-002")
        assert dep_task["status"] == "blocked"
        
        print("✅ Fix loop: human fallback after 3 failures workflow completed")
    
    def test_fix_loop_full_workflow_with_file_state(self):
        """
        Integration test: Full fix loop workflow with actual file operations.
        
        Requirements: All fix loop requirements
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "AGENT_STATE.json"
            
            # Create initial state
            state = {
                "spec_path": "/test/spec",
                "session_name": "full-fix-loop-test",
                "tasks": [
                    {
                        "task_id": "task-001",
                        "description": "Implement authentication",
                        "status": "final_review",
                        "type": "code",
                        "owner_agent": "kiro-cli",
                        "dependencies": [],
                        "criticality": "security-sensitive",
                    },
                    {
                        "task_id": "task-002",
                        "description": "Implement UI",
                        "status": "not_started",
                        "type": "ui",
                        "owner_agent": "gemini",
                        "dependencies": ["task-001"],
                        "criticality": "standard",
                    },
                ],
                "review_findings": [
                    {
                        "task_id": "task-001",
                        "reviewer": "review-task-001-1",
                        "severity": "critical",
                        "summary": "SQL injection vulnerability",
                        "details": "User input not sanitized",
                        "created_at": "2026-01-07T10:00:00Z",
                    },
                    {
                        "task_id": "task-001",
                        "reviewer": "review-task-001-2",
                        "severity": "major",
                        "summary": "Missing input validation",
                        "details": "Password requirements not enforced",
                        "created_at": "2026-01-07T10:00:00Z",
                    },
                ],
                "final_reports": [],
                "blocked_items": [],
                "pending_decisions": [],
                "deferred_fixes": [],
                "window_mapping": {},
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Step 1: Consolidate - should enter fix loop
            with open(state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            report = consolidate_single_task(state, "task-001", auto_complete=True)
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            assert report.overall_severity == "critical"
            
            # Verify state after consolidation
            with open(state_file, encoding='utf-8') as f:
                state = json.load(f)
            
            task = next(t for t in state["tasks"] if t["task_id"] == "task-001")
            assert task["status"] == "fix_required"
            
            dep_task = next(t for t in state["tasks"] if t["task_id"] == "task-002")
            assert dep_task["status"] == "blocked"
            
            # Step 2: Process fix loop
            fix_requests = process_fix_loop(state)
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            assert len(fix_requests) == 1
            
            # Step 3: Simulate fix completion
            on_fix_task_complete(state, "task-001")
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Step 4: Simulate successful review
            on_review_complete(state, "task-001", [
                {"severity": "none", "summary": "All security issues fixed"}
            ])
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Verify final state
            with open(state_file, encoding='utf-8') as f:
                final_state = json.load(f)
            
            task = next(t for t in final_state["tasks"] if t["task_id"] == "task-001")
            assert task["status"] == "final_review"
            assert task["fix_attempts"] == 1
            
            dep_task = next(t for t in final_state["tasks"] if t["task_id"] == "task-002")
            assert dep_task["status"] == "not_started", \
                f"Dependent task should be unblocked, got {dep_task['status']}"
            
            print("✅ Full fix loop workflow with file state completed")


def run_tests():
    """Run all end-to-end tests."""
    test_instance = TestE2EOrchestration()
    
    tests = [
        ("Spec Directory Validation", test_instance.test_spec_directory_validation),
        ("Spec Directory Validation (Missing Files)", test_instance.test_spec_directory_validation_missing_files),
        ("Task Parsing", test_instance.test_task_parsing),
        ("Initialization Creates State File", test_instance.test_initialization_creates_state_file),
        ("Initialization Creates PULSE File", test_instance.test_initialization_creates_pulse_file),
        ("Initialization Task Entries", test_instance.test_initialization_task_entries),
        ("Get Ready Tasks", test_instance.test_get_ready_tasks),
        ("Build Task Configs", test_instance.test_build_task_configs),
        ("Dispatch Batch (Dry Run)", test_instance.test_dispatch_batch_dry_run),
        ("Sync PULSE Updates", test_instance.test_sync_pulse_updates),
        ("Full Orchestration Flow", test_instance.test_full_orchestration_flow),
        ("Agent Assignment by Task Type", test_instance.test_agent_assignment_by_task_type),
        ("Dependency Tracking", test_instance.test_dependency_tracking),
        # Fix Loop Integration Tests
        ("Fix Loop: Initial Failure → Fix → Success", test_instance.test_fix_loop_initial_review_failure_to_fix_to_success),
        ("Fix Loop: Escalation After 2 Failures", test_instance.test_fix_loop_escalation_after_2_failures),
        ("Fix Loop: Human Fallback After 3 Failures", test_instance.test_fix_loop_human_fallback_after_3_failures),
        ("Fix Loop: Full Workflow with File State", test_instance.test_fix_loop_full_workflow_with_file_state),
    ]
    
    print("=" * 60)
    print("End-to-End Integration Tests for Multi-Agent Orchestration")
    print("=" * 60)
    
    passed = 0
    failed = []
    
    for name, test_fn in tests:
        try:
            print(f"\n{name}...")
            test_fn()
            print(f"  ✅ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed.append((name, str(e)))
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed.append((name, str(e)))
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if failed:
        print(f"\n❌ {len(failed)} test(s) failed:")
        for name, error in failed:
            print(f"   - {name}: {error}")
        return 1
    else:
        print(f"\n✅ All {len(tests)} tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
