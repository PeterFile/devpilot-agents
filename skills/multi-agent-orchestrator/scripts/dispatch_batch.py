#!/usr/bin/env python3
"""
Batch Dispatch Script

Dispatches ready tasks to worker agents via codeagent-wrapper --parallel.
- Collects tasks with no unmet dependencies
- Builds task config for codeagent-wrapper
- Invokes codeagent-wrapper synchronously
- Processes Execution Report

Requirements: 1.3, 1.4, 9.1, 9.3, 9.4, 9.10
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Set

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))


# Agent backend mapping
AGENT_TO_BACKEND = {
    "kiro-cli": "kiro-cli",
    "gemini": "gemini",
    "codex-review": "codex",
}


@dataclass
class TaskConfig:
    """Task configuration for codeagent-wrapper"""
    task_id: str
    backend: str
    workdir: str
    content: str
    dependencies: List[str] = field(default_factory=list)
    
    def to_heredoc(self) -> str:
        """Convert to heredoc format for codeagent-wrapper"""
        lines = [
            "---TASK---",
            f"id: {self.task_id}",
            f"backend: {self.backend}",
            f"workdir: {self.workdir}",
        ]
        if self.dependencies:
            lines.append(f"dependencies: {','.join(self.dependencies)}")
        lines.append("---CONTENT---")
        lines.append(self.content)
        return "\n".join(lines)


@dataclass
class ExecutionReport:
    """Execution report from codeagent-wrapper"""
    success: bool
    tasks_completed: int
    tasks_failed: int
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class DispatchResult:
    """Result of batch dispatch"""
    success: bool
    message: str
    tasks_dispatched: int = 0
    execution_report: Optional[ExecutionReport] = None
    errors: List[str] = field(default_factory=list)


def load_agent_state(state_file: str) -> Dict[str, Any]:
    """Load AGENT_STATE.json"""
    with open(state_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_agent_state(state_file: str, state: Dict[str, Any]) -> None:
    """Save AGENT_STATE.json atomically"""
    tmp_file = state_file + ".tmp"
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, state_file)


def get_completed_task_ids(state: Dict[str, Any]) -> Set[str]:
    """Get set of completed task IDs"""
    completed = set()
    for task in state.get("tasks", []):
        status = task.get("status", "")
        # Consider completed, pending_review, under_review, final_review as "done" for dependency purposes
        if status in ["completed", "pending_review", "under_review", "final_review"]:
            completed.add(task["task_id"])
    return completed


def get_ready_tasks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get tasks ready for execution (no unmet dependencies).
    
    Requirement 1.3: Collect ready tasks
    """
    completed = get_completed_task_ids(state)
    ready = []
    
    for task in state.get("tasks", []):
        # Skip non-startable tasks
        if task.get("status") != "not_started":
            continue
        
        # Skip optional tasks (marked with is_optional)
        if task.get("is_optional", False):
            continue
        
        # Check dependencies
        dependencies = task.get("dependencies", [])
        if all(dep in completed for dep in dependencies):
            ready.append(task)
    
    return ready


def build_task_content(task: Dict[str, Any], spec_path: str) -> str:
    """
    Build task content/prompt for the worker agent.
    
    Includes task description and references to spec files.
    """
    lines = [
        f"Task: {task['description']}",
        "",
        f"Task ID: {task['task_id']}",
        f"Type: {task.get('type', 'code')}",
        "",
        "Reference Documents:",
        f"- Requirements: {spec_path}/requirements.md",
        f"- Design: {spec_path}/design.md",
        "",
    ]
    
    # Add task details if available
    details = task.get("details", [])
    if details:
        lines.append("Details:")
        for detail in details:
            lines.append(f"- {detail}")
        lines.append("")
    
    return "\n".join(lines)


def build_task_configs(
    tasks: List[Dict[str, Any]],
    spec_path: str,
    workdir: str = "."
) -> List[TaskConfig]:
    """
    Build task configurations for codeagent-wrapper.
    
    Requirement 1.3, 1.4: Build task config for dispatch
    """
    configs = []
    
    for task in tasks:
        owner_agent = task.get("owner_agent", "kiro-cli")
        backend = AGENT_TO_BACKEND.get(owner_agent, "kiro-cli")
        
        config = TaskConfig(
            task_id=task["task_id"],
            backend=backend,
            workdir=workdir,
            content=build_task_content(task, spec_path),
            dependencies=task.get("dependencies", []),
        )
        configs.append(config)
    
    return configs


def build_heredoc_input(configs: List[TaskConfig]) -> str:
    """Build heredoc-style input for codeagent-wrapper --parallel"""
    return "\n\n".join(config.to_heredoc() for config in configs)


def invoke_codeagent_wrapper(
    configs: List[TaskConfig],
    session_name: str,
    state_file: str,
    dry_run: bool = False
) -> ExecutionReport:
    """
    Invoke codeagent-wrapper --parallel synchronously.
    
    Requirement 9.1, 9.3: Dispatch via codeagent-wrapper, wait for completion
    """
    heredoc_input = build_heredoc_input(configs)
    
    if dry_run:
        print("DRY RUN - Would invoke codeagent-wrapper with:")
        print("-" * 40)
        print(heredoc_input)
        print("-" * 40)
        return ExecutionReport(
            success=True,
            tasks_completed=len(configs),
            tasks_failed=0,
            task_results=[{"task_id": c.task_id, "status": "dry_run"} for c in configs]
        )
    
    # Build command
    cmd = [
        "codeagent-wrapper",
        "--parallel",
        "--tmux-session", session_name,
        "--state-file", state_file,
    ]
    
    try:
        result = subprocess.run(
            cmd,
            input=heredoc_input,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        # Parse output as JSON if possible
        try:
            report_data = json.loads(result.stdout)
            return ExecutionReport(
                success=result.returncode == 0,
                tasks_completed=report_data.get("tasks_completed", 0),
                tasks_failed=report_data.get("tasks_failed", 0),
                task_results=report_data.get("task_results", []),
                errors=report_data.get("errors", [])
            )
        except json.JSONDecodeError:
            # Non-JSON output
            return ExecutionReport(
                success=result.returncode == 0,
                tasks_completed=len(configs) if result.returncode == 0 else 0,
                tasks_failed=0 if result.returncode == 0 else len(configs),
                errors=[result.stderr] if result.stderr else []
            )
            
    except subprocess.TimeoutExpired:
        return ExecutionReport(
            success=False,
            tasks_completed=0,
            tasks_failed=len(configs),
            errors=["Execution timed out after 1 hour"]
        )
    except FileNotFoundError:
        return ExecutionReport(
            success=False,
            tasks_completed=0,
            tasks_failed=len(configs),
            errors=["codeagent-wrapper not found in PATH"]
        )
    except Exception as e:
        return ExecutionReport(
            success=False,
            tasks_completed=0,
            tasks_failed=len(configs),
            errors=[str(e)]
        )


def update_task_statuses(
    state: Dict[str, Any],
    task_ids: List[str],
    new_status: str
) -> None:
    """Update task statuses in state"""
    for task in state.get("tasks", []):
        if task["task_id"] in task_ids:
            task["status"] = new_status


def process_execution_report(
    state: Dict[str, Any],
    report: ExecutionReport
) -> None:
    """
    Process execution report and update state.
    
    Requirement 9.4: Process Execution Report
    """
    for result in report.task_results:
        task_id = result.get("task_id")
        if not task_id:
            continue
        
        # Find and update task
        for task in state.get("tasks", []):
            if task["task_id"] == task_id:
                # Update status based on result
                if result.get("status") == "completed" or result.get("exit_code", 1) == 0:
                    task["status"] = "pending_review"
                elif result.get("status") == "blocked":
                    task["status"] = "blocked"
                
                # Copy result fields
                for field in ["exit_code", "output", "error", "files_changed", 
                             "coverage", "coverage_num", "tests_passed", "tests_failed",
                             "window_id", "pane_id"]:
                    if field in result:
                        task[field] = result[field]
                
                task["completed_at"] = datetime.utcnow().isoformat() + "Z"
                break


def dispatch_batch(
    state_file: str,
    workdir: str = ".",
    dry_run: bool = False
) -> DispatchResult:
    """
    Dispatch ready tasks to worker agents.
    
    Args:
        state_file: Path to AGENT_STATE.json
        workdir: Working directory for tasks
        dry_run: If True, don't actually invoke codeagent-wrapper
    
    Returns:
        DispatchResult with execution details
    
    Requirements: 1.3, 1.4, 9.1, 9.3, 9.4, 9.10
    
    Note: Tasks are only marked in_progress after successful dispatch.
          On failure, tasks are rolled back to not_started to allow retry.
    """
    # Load state
    try:
        state = load_agent_state(state_file)
    except Exception as e:
        return DispatchResult(
            success=False,
            message=f"Failed to load state file: {e}",
            errors=[str(e)]
        )
    
    # Get ready tasks
    ready_tasks = get_ready_tasks(state)
    
    if not ready_tasks:
        return DispatchResult(
            success=True,
            message="No tasks ready for dispatch",
            tasks_dispatched=0
        )
    
    # Build task configs
    spec_path = state.get("spec_path", ".")
    session_name = state.get("session_name", "orchestration")
    configs = build_task_configs(ready_tasks, spec_path, workdir)
    task_ids = [t["task_id"] for t in ready_tasks]
    
    # Invoke codeagent-wrapper (don't update state until we know result)
    report = invoke_codeagent_wrapper(
        configs,
        session_name,
        state_file,
        dry_run=dry_run
    )
    
    # Process results based on success/failure
    if not dry_run:
        if report.success:
            # Dispatch succeeded - update tasks to in_progress first
            update_task_statuses(state, task_ids, "in_progress")
            # Then process individual task results
            process_execution_report(state, report)
        else:
            # Dispatch failed - ensure tasks remain in not_started for retry
            # Only rollback tasks that don't have results (complete failure)
            tasks_with_results = {r.get("task_id") for r in report.task_results if r.get("task_id")}
            tasks_to_rollback = [tid for tid in task_ids if tid not in tasks_with_results]
            
            # Process any partial results we did get
            if report.task_results:
                update_task_statuses(state, list(tasks_with_results), "in_progress")
                process_execution_report(state, report)
            
            # Tasks without results stay as not_started (no change needed since we
            # didn't update them yet)
        
        save_agent_state(state_file, state)
    
    return DispatchResult(
        success=report.success,
        message=f"Dispatched {len(configs)} tasks" if report.success else f"Dispatch failed for {len(configs)} tasks",
        tasks_dispatched=len(configs),
        execution_report=report,
        errors=report.errors
    )


def main():
    """Command line entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Dispatch ready tasks to worker agents"
    )
    parser.add_argument(
        "state_file",
        help="Path to AGENT_STATE.json"
    )
    parser.add_argument(
        "--workdir", "-w",
        default=".",
        help="Working directory for tasks (default: current directory)"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be dispatched without executing"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    
    args = parser.parse_args()
    
    result = dispatch_batch(
        args.state_file,
        workdir=args.workdir,
        dry_run=args.dry_run
    )
    
    if args.json:
        output = {
            "success": result.success,
            "message": result.message,
            "tasks_dispatched": result.tasks_dispatched,
            "errors": result.errors
        }
        if result.execution_report:
            output["execution_report"] = {
                "tasks_completed": result.execution_report.tasks_completed,
                "tasks_failed": result.execution_report.tasks_failed,
            }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"✅ {result.message}")
            if result.execution_report:
                print(f"   Completed: {result.execution_report.tasks_completed}")
                print(f"   Failed: {result.execution_report.tasks_failed}")
        else:
            print(f"❌ {result.message}")
            for error in result.errors:
                print(f"   - {error}")
            sys.exit(1)


if __name__ == "__main__":
    main()
