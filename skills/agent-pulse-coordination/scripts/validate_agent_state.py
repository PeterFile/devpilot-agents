#!/usr/bin/env python3
"""
Agent State Validation Script

Validates AGENT_STATE.json against the defined JSON schema.
Returns structured error information for invalid states.
Also validates business rules like review count matching criticality.

Requirements: 10.1, 10.2, 10.3, 10.4, 3.2, 3.3, 3.4, 5.3, 5.4
"""

import json
import sys
from pathlib import Path
from typing import Any, List, Dict
from collections import defaultdict

try:
    from jsonschema import Draft7Validator, ValidationError
except ImportError:
    print("Error: jsonschema library required. Install with: pip install jsonschema")
    sys.exit(1)


# Get schema file path
SCHEMA_PATH = Path(__file__).parent.parent / "references" / "agent-state-schema.json"


def load_schema() -> dict:
    """Load Agent State JSON Schema"""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def format_error_path(error: ValidationError) -> str:
    """Format error path as readable string"""
    path_parts = list(error.absolute_path)
    if not path_parts:
        return "(root)"
    return ".".join(str(p) for p in path_parts)


# Define valid state transitions (state machine)
# Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 4.3
VALID_STATE_TRANSITIONS: Dict[str, set] = {
    # Initial state can be in-progress or blocked
    None: {"in-progress", "blocked"},
    # in-progress can transition to pending_review or blocked
    "in-progress": {"pending_review", "blocked"},
    # pending_review can transition to under_review or blocked
    "pending_review": {"under_review", "blocked"},
    # under_review can transition to final_review or blocked
    "under_review": {"final_review", "blocked"},
    # final_review can transition to completed or blocked
    "final_review": {"completed", "blocked"},
    # completed is terminal state, no further transitions
    "completed": set(),
    # blocked can transition back to in-progress (blocker resolved)
    "blocked": {"in-progress"},
}


def is_valid_state_transition(from_state: str, to_state: str) -> bool:
    """
    Check if state transition is valid
    
    Args:
        from_state: Source state (can be None for initial state)
        to_state: Target state
        
    Returns:
        Whether the state transition is valid
    """
    valid_next_states = VALID_STATE_TRANSITIONS.get(from_state, set())
    return to_state in valid_next_states


def validate_state_machine_transitions(transitions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Validate a series of state transitions against state machine definition
    
    Args:
        transitions: List of state transitions, each containing:
            - task_id: Task ID
            - from_state: Source state
            - to_state: Target state
            
    Returns:
        List of errors
        
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 4.3
    """
    errors = []
    
    for i, transition in enumerate(transitions):
        task_id = transition.get("task_id", f"unknown-{i}")
        from_state = transition.get("from_state")
        to_state = transition.get("to_state")
        
        if not is_valid_state_transition(from_state, to_state):
            from_display = from_state if from_state else "(initial)"
            errors.append({
                "field": f"transition[{i}]",
                "message": f"Invalid state transition for task '{task_id}': '{from_display}' -> '{to_state}'. "
                          f"Valid transitions from '{from_display}' are: {VALID_STATE_TRANSITIONS.get(from_state, set())}"
            })
    
    return errors


def validate_review_phase_state_machine(data: dict) -> List[Dict[str, str]]:
    """
    Validate that review_phase of tasks in Agent State conforms to state machine definition
    
    This function checks if each task's current review_phase is a valid state value.
    Note: Since Agent State only stores current state, not transition history,
    we can only validate that the current state is a valid state value.
    
    For complete state transition validation, use validate_state_machine_transitions
    function with transition history.
    
    Args:
        data: Agent State JSON data
        
    Returns:
        List of errors
        
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 4.3
    """
    errors = []
    
    tasks = data.get("tasks", [])
    valid_phases = set(VALID_STATE_TRANSITIONS.keys()) - {None}
    
    for i, task in enumerate(tasks):
        task_id = task.get("task_id", f"unknown-{i}")
        review_phase = task.get("review_phase")
        
        if review_phase and review_phase not in valid_phases:
            errors.append({
                "field": f"tasks[{i}].review_phase",
                "message": f"Task '{task_id}' has invalid review_phase '{review_phase}'. "
                          f"Valid phases are: {valid_phases}"
            })
    
    return errors


def validate_review_count_by_criticality(data: dict) -> List[Dict[str, str]]:
    """
    Validate that review count matches criticality requirements
    
    Rules:
    - standard tasks: require exactly 1 review
    - complex tasks: require ≥2 reviews
    - security-sensitive tasks: require ≥2 reviews
    
    Requirements: 3.2, 3.3, 3.4, 5.3, 5.4
    
    Args:
        data: Agent State JSON data
        
    Returns:
        List of errors
    """
    errors = []
    
    tasks = data.get("tasks", [])
    review_findings = data.get("review_findings", [])
    
    # Count reviews per task_id
    review_count_by_task: Dict[str, int] = defaultdict(int)
    for finding in review_findings:
        task_id = finding.get("task_id")
        if task_id:
            review_count_by_task[task_id] += 1
    
    # Validate review count for each task
    for i, task in enumerate(tasks):
        task_id = task.get("task_id")
        criticality = task.get("criticality")
        review_phase = task.get("review_phase")
        
        if not task_id or not criticality:
            continue
        
        # Only validate tasks that have completed review phase
        # i.e., tasks with review_phase of final_review or completed
        if review_phase not in ("final_review", "completed"):
            continue
        
        review_count = review_count_by_task.get(task_id, 0)
        
        if criticality == "standard":
            # standard tasks require exactly 1 review
            if review_count != 1:
                errors.append({
                    "field": f"tasks.{i}.criticality",
                    "message": f"Task '{task_id}' with criticality 'standard' requires exactly 1 review, but has {review_count}"
                })
        elif criticality in ("complex", "security-sensitive"):
            # complex and security-sensitive tasks require ≥2 reviews
            if review_count < 2:
                errors.append({
                    "field": f"tasks.{i}.criticality",
                    "message": f"Task '{task_id}' with criticality '{criticality}' requires at least 2 reviews, but has {review_count}"
                })
    
    return errors


def validate_agent_state(data: dict, validate_criticality: bool = True, validate_state_machine: bool = True) -> dict:
    """
    Validate Agent State data
    
    Args:
        data: Agent State JSON data
        validate_criticality: Whether to validate review count matches criticality
        validate_state_machine: Whether to validate review_phase state machine
        
    Returns:
        Validation result dict containing:
        - valid: bool - Whether valid
        - errors: list - List of errors (if invalid)
    """
    schema = load_schema()
    validator = Draft7Validator(schema)
    
    errors = []
    
    # Schema validation
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        field_path = format_error_path(error)
        errors.append({
            "field": field_path,
            "message": error.message
        })
    
    # If schema validation passes, perform business rule validation
    if not errors:
        if validate_state_machine:
            state_machine_errors = validate_review_phase_state_machine(data)
            errors.extend(state_machine_errors)
        
        if validate_criticality:
            criticality_errors = validate_review_count_by_criticality(data)
            errors.extend(criticality_errors)
    
    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": []}


def validate_agent_state_file(file_path: str) -> dict:
    """
    Validate Agent State JSON file
    
    Args:
        file_path: JSON file path
        
    Returns:
        Validation result dict
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "errors": [{"field": "(file)", "message": f"Invalid JSON: {e}"}]
        }
    except FileNotFoundError:
        return {
            "valid": False,
            "errors": [{"field": "(file)", "message": f"File not found: {file_path}"}]
        }
    
    return validate_agent_state(data)


def main():
    """Command line entry point"""
    if len(sys.argv) < 2:
        print("Usage: python validate_agent_state.py <agent_state.json>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    result = validate_agent_state_file(file_path)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
