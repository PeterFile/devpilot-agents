#!/usr/bin/env python3
"""
Batch Dispatch Script

Dispatches ready tasks to worker agents via codeagent-wrapper --parallel.
- Collects tasks with no unmet dependencies
- Builds task config for codeagent-wrapper
- Invokes codeagent-wrapper synchronously
- Processes Execution Report
- Detects file conflicts and partitions tasks into safe batches

Requirements: 1.3, 1.4, 2.3, 2.4, 2.5, 2.6, 2.7, 9.1, 9.3, 9.4, 9.10
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Set

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import update_parent_statuses for parent status aggregation (Req 1.3, 1.4, 1.5)
from init_orchestration import update_parent_statuses

# Configure logging
logger = logging.getLogger(__name__)


# Agent backend mapping
AGENT_TO_BACKEND = {
    "kiro-cli": "kiro-cli",
    "gemini": "gemini",
    "codex-review": "codex",
}


@dataclass
class FileConflict:
    """
    Represents a file conflict between two tasks.
    
    Requirements: 2.3, 2.4
    """
    task_a: str
    task_b: str
    files: List[str]
    conflict_type: str  # "write-write"
    
    def __str__(self) -> str:
        return f"FileConflict({self.task_a} <-> {self.task_b}: {', '.join(self.files)})"


def has_file_manifest(task: Dict[str, Any]) -> bool:
    """
    Check if task has a file manifest (writes or reads declared).
    
    Requirements: 2.5
    """
    return bool(task.get("writes")) or bool(task.get("reads"))


def detect_file_conflicts(tasks: List[Dict[str, Any]]) -> List[FileConflict]:
    """
    Detect file write conflicts between tasks.
    
    Returns list of conflicts that would occur if tasks run in parallel.
    Only detects write-write conflicts (two tasks writing to same file).
    
    Requirements: 2.3, 2.4
    
    Args:
        tasks: List of task dictionaries with optional 'writes' field
        
    Returns:
        List of FileConflict objects describing detected conflicts
    """
    conflicts = []
    
    for i, task_a in enumerate(tasks):
        writes_a = set(task_a.get("writes") or [])
        
        for task_b in tasks[i+1:]:
            writes_b = set(task_b.get("writes") or [])
            
            # Check write-write conflicts
            shared_writes = writes_a & writes_b
            if shared_writes:
                conflicts.append(FileConflict(
                    task_a=task_a["task_id"],
                    task_b=task_b["task_id"],
                    files=list(shared_writes),
                    conflict_type="write-write"
                ))
    
    return conflicts


def partition_by_conflicts(
    tasks: List[Dict[str, Any]],
    log: Optional[logging.Logger] = None
) -> List[List[Dict[str, Any]]]:
    """
    Partition tasks into conflict-free batches.
    
    Rules:
    - Tasks with write-write conflicts are placed in separate batches
    - Tasks without ANY file manifest (no writes AND no reads) are executed serially
    - Tasks with only reads (no writes) can be batched with non-conflicting write tasks
    - Tasks with non-conflicting writes can be batched together
    
    Batches are guaranteed to run sequentially (batch N completes before batch N+1 starts).
    
    Requirements: 2.3, 2.4, 2.5, 2.6, 2.7
    
    Args:
        tasks: List of task dictionaries
        log: Optional logger for warnings
        
    Returns:
        List of batches, where each batch is a list of tasks safe to run in parallel
    """
    if log is None:
        log = logger
    
    # Categorize tasks
    no_manifest_tasks = []      # No writes AND no reads - serial for safety
    safe_tasks = []             # Has reads only OR has writes - can check conflicts
    
    for task in tasks:
        if not task.get("writes") and not task.get("reads"):
            no_manifest_tasks.append(task)
        else:
            safe_tasks.append(task)
    
    batches: List[List[Dict[str, Any]]] = []
    
    # Safe tasks (with manifest): partition by write conflicts
    if safe_tasks:
        # Only tasks with writes can have conflicts
        write_tasks = [t for t in safe_tasks if t.get("writes")]
        read_only_tasks = [t for t in safe_tasks if not t.get("writes")]
        
        conflicts = detect_file_conflicts(write_tasks)
        conflict_pairs: Set[tuple] = {(c.task_a, c.task_b) for c in conflicts}
        conflict_pairs.update({(c.task_b, c.task_a) for c in conflicts})
        
        # Log warnings for conflicts (Req 2.7)
        if conflicts and log:
            for conflict in conflicts:
                log.warning(
                    f"File conflict detected between {conflict.task_a} and {conflict.task_b}: "
                    f"{', '.join(conflict.files)}. Tasks will be serialized."
                )
        
        # Greedy coloring to partition write tasks into non-conflicting batches
        assigned: Set[str] = set()
        
        for task in write_tasks:
            task_id = task["task_id"]
            if task_id in assigned:
                continue
            
            # Find a batch where this task has no conflicts
            placed = False
            for batch in batches:
                batch_ids = {t["task_id"] for t in batch}
                if not any((task_id, bid) in conflict_pairs for bid in batch_ids):
                    batch.append(task)
                    assigned.add(task_id)
                    placed = True
                    break
            
            if not placed:
                batches.append([task])
                assigned.add(task_id)
        
        # Read-only tasks can be added to any batch (no write conflicts)
        # Add them to the first batch for maximum parallelism (Req 2.6)
        if read_only_tasks:
            if batches:
                batches[0].extend(read_only_tasks)
            else:
                batches.append(read_only_tasks)
    
    # No-manifest tasks run serially (each in own batch) - conservative default (Req 2.5)
    for task in no_manifest_tasks:
        if log:
            log.info(f"Task {task['task_id']} has no file manifest, executing serially for safety.")
        batches.append([task])
    
    return batches


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
    Dispatch ready tasks to worker agents with file conflict detection.
    
    Tasks are partitioned into conflict-free batches and dispatched sequentially.
    Each batch completes before the next batch starts, ensuring no file conflicts.
    
    Args:
        state_file: Path to AGENT_STATE.json
        workdir: Working directory for tasks
        dry_run: If True, don't actually invoke codeagent-wrapper
    
    Returns:
        DispatchResult with execution details
    
    Requirements: 1.3, 1.4, 2.3, 2.4, 2.5, 2.6, 2.7, 9.1, 9.3, 9.4, 9.10
    
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
    
    # Partition tasks into conflict-free batches (Req 2.3, 2.4, 2.5, 2.6, 2.7)
    batches = partition_by_conflicts(ready_tasks, logger)
    
    if len(batches) > 1:
        logger.info(f"Partitioned {len(ready_tasks)} tasks into {len(batches)} conflict-free batches")
    
    spec_path = state.get("spec_path", ".")
    session_name = state.get("session_name", "orchestration")
    
    total_dispatched = 0
    total_completed = 0
    total_failed = 0
    all_errors: List[str] = []
    all_task_results: List[Dict[str, Any]] = []
    overall_success = True
    
    # Dispatch batches sequentially (Req 2.3, 2.4)
    for batch_idx, batch in enumerate(batches):
        batch_task_ids = [t["task_id"] for t in batch]
        
        if len(batches) > 1:
            logger.info(f"Dispatching batch {batch_idx + 1}/{len(batches)} with {len(batch)} tasks: {batch_task_ids}")
        
        # Build task configs for this batch
        configs = build_task_configs(batch, spec_path, workdir)
        
        # Invoke codeagent-wrapper for this batch
        report = invoke_codeagent_wrapper(
            configs,
            session_name,
            state_file,
            dry_run=dry_run
        )
        
        total_dispatched += len(configs)
        total_completed += report.tasks_completed
        total_failed += report.tasks_failed
        all_errors.extend(report.errors)
        all_task_results.extend(report.task_results)
        
        # Process results for this batch
        if not dry_run:
            if report.success:
                # Dispatch succeeded - update tasks to in_progress first
                update_task_statuses(state, batch_task_ids, "in_progress")
                # Then process individual task results
                process_execution_report(state, report)
            else:
                overall_success = False
                # Dispatch failed - ensure tasks remain in not_started for retry
                tasks_with_results = {r.get("task_id") for r in report.task_results if r.get("task_id")}
                
                # Process any partial results we did get
                if report.task_results:
                    update_task_statuses(state, list(tasks_with_results), "in_progress")
                    process_execution_report(state, report)
                
                # Log batch failure
                logger.error(f"Batch {batch_idx + 1} failed: {report.errors}")
            
            # Update parent statuses after each batch (Req 1.3, 1.4, 1.5)
            update_parent_statuses(state)
            
            # Save state after each batch
            save_agent_state(state_file, state)
        
        # If batch failed, we might want to stop (but continue for now to process all batches)
        # Future enhancement: add option to stop on first failure
    
    # Build combined execution report
    combined_report = ExecutionReport(
        success=overall_success,
        tasks_completed=total_completed,
        tasks_failed=total_failed,
        task_results=all_task_results,
        errors=all_errors
    )
    
    message = f"Dispatched {total_dispatched} tasks in {len(batches)} batch(es)"
    if not overall_success:
        message = f"Dispatch partially failed: {total_completed} completed, {total_failed} failed"
    
    return DispatchResult(
        success=overall_success,
        message=message,
        tasks_dispatched=total_dispatched,
        execution_report=combined_report,
        errors=all_errors
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
