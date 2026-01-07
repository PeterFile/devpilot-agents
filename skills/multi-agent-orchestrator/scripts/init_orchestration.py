#!/usr/bin/env python3
"""
Orchestration Initialization Script

Initializes multi-agent orchestration from a Kiro spec directory.
- Parses tasks.md and validates spec files
- Creates AGENT_STATE.json with tasks from tasks.md
- Creates PROJECT_PULSE.md with mental model from design.md

Requirements: 11.2, 11.4, 11.5, 11.6, 11.8
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

# Add script directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from spec_parser import (
    Task,
    TaskType,
    TaskStatus,
    parse_tasks,
    validate_spec_directory,
    extract_dependencies,
    load_tasks_from_spec,
)


# Agent assignment by task type (Requirement 1.3, 11.5)
AGENT_BY_TASK_TYPE = {
    TaskType.CODE: "kiro-cli",
    TaskType.UI: "gemini",
    TaskType.REVIEW: "codex-review",
}

# Keywords for criticality detection (Requirement 11.6)
SECURITY_KEYWORDS = ["security", "auth", "password", "token", "encrypt", "credential", "secret"]
COMPLEX_KEYWORDS = ["refactor", "migration", "integration", "architecture"]


@dataclass
class TaskEntry:
    """Task entry for AGENT_STATE.json"""
    task_id: str
    description: str
    type: str
    status: str
    owner_agent: str
    dependencies: List[str]
    criticality: str
    is_optional: bool
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentState:
    """Full AGENT_STATE.json structure"""
    spec_path: str
    session_name: str
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    review_findings: List[Dict[str, Any]] = field(default_factory=list)
    final_reports: List[Dict[str, Any]] = field(default_factory=list)
    blocked_items: List[Dict[str, Any]] = field(default_factory=list)
    pending_decisions: List[Dict[str, Any]] = field(default_factory=list)
    deferred_fixes: List[Dict[str, Any]] = field(default_factory=list)
    window_mapping: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InitResult:
    """Result of initialization"""
    success: bool
    message: str
    state_file: Optional[str] = None
    pulse_file: Optional[str] = None
    errors: List[str] = field(default_factory=list)


def determine_criticality(task: Task) -> str:
    """
    Determine task criticality based on description and details.
    
    Requirement 11.6: Set initial criticality based on task markers
    - * for optional
    - security keywords for security-sensitive
    - complex keywords for complex
    """
    text = (task.description + " " + " ".join(task.details)).lower()
    
    # Check for security-sensitive keywords
    for keyword in SECURITY_KEYWORDS:
        if keyword in text:
            return "security-sensitive"
    
    # Check for complex keywords
    for keyword in COMPLEX_KEYWORDS:
        if keyword in text:
            return "complex"
    
    return "standard"


def assign_owner_agent(task: Task) -> str:
    """
    Assign owner agent based on task type.
    
    Requirement 1.3, 11.5: Determine appropriate agent based on task type
    """
    return AGENT_BY_TASK_TYPE.get(task.task_type, "kiro-cli")


def convert_task_to_entry(task: Task) -> TaskEntry:
    """Convert parsed Task to TaskEntry for AGENT_STATE.json"""
    return TaskEntry(
        task_id=task.task_id,
        description=task.description,
        type=task.task_type.value,
        status=task.status.value,
        owner_agent=assign_owner_agent(task),
        dependencies=task.dependencies,
        criticality=determine_criticality(task),
        is_optional=task.is_optional,
        created_at=datetime.utcnow().isoformat() + "Z",
    )


def extract_mental_model_from_design(design_path: str) -> Dict[str, str]:
    """
    Extract mental model from design.md for PROJECT_PULSE.md.
    
    Requirement 11.8: Initialize PROJECT_PULSE.md with Mental Model from design.md
    """
    try:
        with open(design_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return {
            "description": "Multi-agent orchestration system",
            "diagram": ""
        }
    
    # Extract overview section for description
    description = ""
    overview_match = re.search(r'## Overview\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if overview_match:
        overview_text = overview_match.group(1).strip()
        # Get first paragraph
        paragraphs = overview_text.split('\n\n')
        if paragraphs:
            description = paragraphs[0].strip()
    
    # Extract first mermaid diagram
    diagram = ""
    mermaid_match = re.search(r'```mermaid\s*\n(.*?)```', content, re.DOTALL)
    if mermaid_match:
        diagram = mermaid_match.group(1).strip()
    
    return {
        "description": description or "Multi-agent orchestration system",
        "diagram": diagram
    }


def generate_pulse_document(
    spec_path: str,
    mental_model: Dict[str, str],
    tasks: List[TaskEntry]
) -> str:
    """
    Generate PROJECT_PULSE.md content.
    
    Requirement 11.8: Initialize PROJECT_PULSE.md with Mental Model from design.md
    """
    # Count tasks by status
    total_tasks = len(tasks)
    not_started = sum(1 for t in tasks if t.status == "not_started")
    
    pulse_content = f"""# PROJECT_PULSE.md

## 🟢 Mental Model

{mental_model['description']}

"""
    
    if mental_model['diagram']:
        pulse_content += f"""```mermaid
{mental_model['diagram']}
```

"""
    
    pulse_content += f"""## 🟡 Narrative Delta

**Orchestration initialized from spec:** `{spec_path}`

- Total tasks: {total_tasks}
- Ready to start: {not_started}

## 🔴 Risks & Debt

### Cognitive Load Warnings
- None identified

### Technical Debt
- None identified

### Pending Decisions
- None pending

## 🔗 Semantic Anchors

- [Spec] {spec_path}/requirements.md -> Requirements
- [Spec] {spec_path}/design.md -> Design
- [Spec] {spec_path}/tasks.md -> Tasks
"""
    
    return pulse_content


def initialize_orchestration(
    spec_path: str,
    session_name: Optional[str] = None,
    output_dir: Optional[str] = None
) -> InitResult:
    """
    Initialize orchestration from spec directory.
    
    Args:
        spec_path: Path to spec directory containing requirements.md, design.md, tasks.md
        session_name: Tmux session name (default: derived from spec path)
        output_dir: Output directory for state files (default: spec_path parent)
    
    Returns:
        InitResult with success status and file paths
    
    Requirements: 11.2, 11.4, 11.5, 11.6, 11.8
    """
    errors = []
    
    # Validate spec directory (Requirement 11.2)
    validation = validate_spec_directory(spec_path)
    if not validation.valid:
        return InitResult(
            success=False,
            message=f"Invalid spec directory: {spec_path}",
            errors=validation.errors
        )
    
    # Parse tasks.md (Requirement 11.3, 11.4)
    tasks_result, _ = load_tasks_from_spec(spec_path)
    if not tasks_result.success:
        return InitResult(
            success=False,
            message="Failed to parse tasks.md",
            errors=[str(e) for e in tasks_result.errors]
        )
    
    # Convert tasks to entries (Requirement 11.4, 11.5, 11.6)
    task_entries = [convert_task_to_entry(t) for t in tasks_result.tasks]
    
    # Determine session name
    if not session_name:
        spec_name = Path(spec_path).name
        session_name = f"orch-{spec_name}"
    
    # Create AGENT_STATE.json
    agent_state = AgentState(
        spec_path=os.path.abspath(spec_path),
        session_name=session_name,
        tasks=[t.to_dict() for t in task_entries],
    )
    
    # Determine output directory
    if output_dir:
        out_path = Path(output_dir)
    else:
        out_path = Path(spec_path).parent
    
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Write AGENT_STATE.json
    state_file = out_path / "AGENT_STATE.json"
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(agent_state.to_dict(), f, indent=2)
    except Exception as e:
        errors.append(f"Failed to write AGENT_STATE.json: {e}")
    
    # Extract mental model from design.md (Requirement 11.8)
    design_path = os.path.join(spec_path, "design.md")
    mental_model = extract_mental_model_from_design(design_path)
    
    # Generate and write PROJECT_PULSE.md
    pulse_content = generate_pulse_document(spec_path, mental_model, task_entries)
    pulse_file = out_path / "PROJECT_PULSE.md"
    try:
        with open(pulse_file, 'w', encoding='utf-8') as f:
            f.write(pulse_content)
    except Exception as e:
        errors.append(f"Failed to write PROJECT_PULSE.md: {e}")
    
    if errors:
        return InitResult(
            success=False,
            message="Initialization completed with errors",
            state_file=str(state_file),
            pulse_file=str(pulse_file),
            errors=errors
        )
    
    return InitResult(
        success=True,
        message=f"Orchestration initialized successfully",
        state_file=str(state_file),
        pulse_file=str(pulse_file)
    )


def main():
    """Command line entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Initialize multi-agent orchestration from spec directory"
    )
    parser.add_argument(
        "spec_path",
        help="Path to spec directory (containing requirements.md, design.md, tasks.md)"
    )
    parser.add_argument(
        "--session", "-s",
        help="Tmux session name (default: derived from spec path)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory for state files (default: spec parent directory)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    
    args = parser.parse_args()
    
    result = initialize_orchestration(
        args.spec_path,
        session_name=args.session,
        output_dir=args.output
    )
    
    if args.json:
        output = {
            "success": result.success,
            "message": result.message,
            "state_file": result.state_file,
            "pulse_file": result.pulse_file,
            "errors": result.errors
        }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"✅ {result.message}")
            print(f"   State file: {result.state_file}")
            print(f"   PULSE file: {result.pulse_file}")
        else:
            print(f"❌ {result.message}")
            for error in result.errors:
                print(f"   - {error}")
            sys.exit(1)


if __name__ == "__main__":
    main()
