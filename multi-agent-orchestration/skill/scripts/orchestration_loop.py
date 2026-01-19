#!/usr/bin/env python3
"""
Orchestration Loop Runner

Runs a Ralph-style loop for the multi-agent orchestration workflow:
- Each iteration starts a fresh orchestrator (LLM) via codeagent-wrapper
- The orchestrator reads AGENT_STATE.json / PROJECT_PULSE.md (and optionally TASKS_PARSED.json)
- The orchestrator outputs a machine-readable decision: COMPLETE or CONTINUE
- The runner executes the decided actions (dispatch/review/fix/assign/sync)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ALLOWED_ACTION_TYPES = {
    "assign_dispatch",
    "dispatch_batch",
    "dispatch_reviews",
    "consolidate_reviews",
    "sync_pulse",
    "halt",
}


@dataclass(frozen=True)
class RunnerPaths:
    state_file: Path
    tasks_file: Optional[Path]
    pulse_file: Path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(_read_text(path))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _json_from_text(text: str) -> Any:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[i:])
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON object found in output")


def _run(cmd: List[str], *, input_text: Optional[str] = None, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def _infer_paths(state_file: Path, tasks_file: Optional[Path], pulse_file: Optional[Path]) -> RunnerPaths:
    base = state_file.parent
    inferred_tasks = tasks_file
    if inferred_tasks is None:
        candidate = base / "TASKS_PARSED.json"
        if candidate.exists():
            inferred_tasks = candidate

    inferred_pulse = pulse_file
    if inferred_pulse is None:
        candidate = base / "PROJECT_PULSE.md"
        if candidate.exists():
            inferred_pulse = candidate
    if inferred_pulse is None:
        raise FileNotFoundError("pulse_file is required (or PROJECT_PULSE.md must exist next to state_file)")

    return RunnerPaths(state_file=state_file, tasks_file=inferred_tasks, pulse_file=inferred_pulse)


def _is_dispatch_unit(task: Dict[str, Any]) -> bool:
    if task.get("subtasks"):
        return True
    return not task.get("parent_id") and not task.get("subtasks")


def _dispatch_unit_completion(state: Dict[str, Any]) -> Tuple[int, int]:
    tasks = state.get("tasks", [])
    units = [t for t in tasks if _is_dispatch_unit(t)]
    incomplete = [t for t in units if t.get("status") != "completed"]
    return len(incomplete), len(units)


def _build_orchestrator_prompt(
    paths: RunnerPaths,
    *,
    recent_events: List[Dict[str, Any]],
    max_actions: int,
) -> str:
    events_text = json.dumps(recent_events[-20:], indent=2, ensure_ascii=False) if recent_events else "[]"
    lines = [
        "You are the orchestration controller for a multi-agent workflow.",
        "This is a single-iteration tick. Your output MUST be JSON only.",
        "",
        "Inputs:",
        f"- @{paths.state_file.as_posix()}",
        f"- @{paths.pulse_file.as_posix()}",
    ]
    if paths.tasks_file:
        lines.append(f"- @{paths.tasks_file.as_posix()}")

    lines += [
        "",
        "Recent runner events (may be empty):",
        events_text,
        "",
        "You must decide which actions the runner should execute NEXT.",
        "",
        "Dispatch Unit definition:",
        "- A parent task with a non-empty subtasks array, OR",
        "- A standalone task with no parent_id and no subtasks.",
        "",
        "Allowed action types:",
        "- assign_dispatch: generate/repair dispatch assignments (owner_agent/target_window/criticality/writes/reads) for dispatch units only",
        "- dispatch_batch: run dispatch_batch.py to execute ready dispatch units",
        "- dispatch_reviews: dispatch reviews for completed dispatch units",
        "- consolidate_reviews: consolidate review findings; may enter fix loop (fix_required) for critical/major issues",
        "- sync_pulse: sync PROJECT_PULSE.md from AGENT_STATE.json",
        "- halt: stop the loop (use when pending_decisions requires human input, or unrecoverable error)",
        "",
        "Rules:",
        "- If pending_decisions is non-empty: choose decision COMPLETE and include a single halt action.",
        "- If any dispatch unit is not_started and missing owner_agent: include assign_dispatch before dispatch_batch.",
        "- If fix_required tasks exist: dispatch_batch may be used (it handles fix loop dispatch).",
        "- Always include sync_pulse after any action that changes AGENT_STATE.json.",
        f"- Return at most {max_actions} actions.",
        "",
        "Output JSON schema:",
        "{",
        '  "decision": "COMPLETE" | "CONTINUE",',
        '  "actions": [',
        '    {"type": "assign_dispatch" | "dispatch_batch" | "dispatch_reviews" | "consolidate_reviews" | "sync_pulse" | "halt"}',
        "  ],",
        '  "notes": "short reason"',
        "}",
    ]
    return "\n".join(lines) + "\n"


def _call_orchestrator(
    *,
    backend: str,
    paths: RunnerPaths,
    recent_events: List[Dict[str, Any]],
    max_actions: int,
    cwd: Path,
) -> Dict[str, Any]:
    prompt = _build_orchestrator_prompt(paths, recent_events=recent_events, max_actions=max_actions)
    code, stdout, stderr = _run(
        ["codeagent-wrapper", "--backend", backend, "-"],
        input_text=prompt,
        cwd=cwd,
    )
    if code != 0:
        raise RuntimeError(f"orchestrator failed (exit {code}): {stderr.strip() or stdout.strip()}")
    decision = _json_from_text(stdout)
    if not isinstance(decision, dict):
        raise ValueError("orchestrator output is not a JSON object")
    return decision


def _build_assignment_prompt(paths: RunnerPaths) -> str:
    if not paths.tasks_file:
        raise FileNotFoundError("tasks_file is required for assign_dispatch")
    return (
        "You are generating dispatch assignments for multi-agent orchestration.\n\n"
        "Inputs:\n"
        f"- @{paths.state_file.as_posix()}\n"
        f"- @{paths.tasks_file.as_posix()}\n\n"
        "Rules:\n"
        "- Only assign Dispatch Units (parent tasks or standalone tasks).\n"
        "- Do NOT assign leaf tasks with parents.\n"
        "- owner_agent: codex | gemini | codex-review\n"
        "- target_window: task-<task_id> or grouped names (max 9)\n"
        "- criticality: standard | complex | security-sensitive\n"
        "- writes/reads: list of files (best-effort)\n\n"
        "Output JSON only:\n"
        "{\n"
        '  "dispatch_units": [\n'
        "    {\n"
        '      "task_id": "1",\n'
        '      "owner_agent": "codex",\n'
        '      "target_window": "task-1",\n'
        '      "criticality": "standard",\n'
        '      "writes": ["src/example.py"],\n'
        '      "reads": ["src/config.py"]\n'
        "    }\n"
        "  ],\n"
        '  "window_mapping": {\n'
        '    "1": "task-1"\n'
        "  }\n"
        "}\n"
    )


def _apply_assignments(state_path: Path, assignments: Dict[str, Any]) -> Dict[str, Any]:
    state = _read_json(state_path)
    tasks = state.get("tasks", [])
    task_map = {t.get("task_id"): t for t in tasks if t.get("task_id")}

    for entry in assignments.get("dispatch_units", []) or []:
        task_id = entry.get("task_id")
        if not task_id or task_id not in task_map:
            continue
        task = task_map[task_id]
        if not _is_dispatch_unit(task):
            continue
        for key in ["owner_agent", "target_window", "criticality", "writes", "reads"]:
            if key in entry and entry[key] is not None:
                task[key] = entry[key]

    window_mapping = state.get("window_mapping") or {}
    incoming_mapping = assignments.get("window_mapping") or {}
    if isinstance(incoming_mapping, dict):
        window_mapping.update({str(k): str(v) for k, v in incoming_mapping.items()})
    state["window_mapping"] = window_mapping
    _write_json(state_path, state)
    return state


def _run_python_script(script: Path, args: List[str], *, cwd: Path) -> Dict[str, Any]:
    cmd = [sys.executable, str(script)] + args + ["--json"]
    code, stdout, stderr = _run(cmd, cwd=cwd)
    if code != 0:
        raise RuntimeError(f"{script.name} failed (exit {code}): {stderr.strip() or stdout.strip()}")
    payload = json.loads(stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"{script.name} did not return a JSON object")
    return payload


def _validate_decision(decision: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], str]:
    d = str(decision.get("decision", "")).strip().upper()
    if d not in {"COMPLETE", "CONTINUE"}:
        raise ValueError("decision must be COMPLETE or CONTINUE")
    actions = decision.get("actions") or []
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    normalized: List[Dict[str, Any]] = []
    for a in actions:
        if isinstance(a, str):
            a = {"type": a}
        if not isinstance(a, dict):
            raise ValueError("each action must be an object or string")
        t = str(a.get("type", "")).strip()
        if t not in ALLOWED_ACTION_TYPES:
            raise ValueError(f"unsupported action type: {t}")
        normalized.append({"type": t})
    notes = str(decision.get("notes", "")).strip()
    return d, normalized, notes


def run_loop(
    *,
    backend: str,
    assign_backend: str,
    paths: RunnerPaths,
    workdir: Path,
    max_iterations: int,
    sleep_seconds: float,
    max_actions: int,
) -> int:
    scripts_dir = Path(__file__).parent
    recent_events: List[Dict[str, Any]] = []

    print(f"[loop] state_file={paths.state_file}")
    print(f"[loop] pulse_file={paths.pulse_file}")
    if paths.tasks_file:
        print(f"[loop] tasks_file={paths.tasks_file}")
    print(f"[loop] workdir={workdir}")

    for iteration in range(1, max_iterations + 1):
        decision = _call_orchestrator(
            backend=backend,
            paths=paths,
            recent_events=recent_events,
            max_actions=max_actions,
            cwd=workdir,
        )

        d, actions, notes = _validate_decision(decision)
        recent_events.append({"iteration": iteration, "orchestrator": {"decision": d, "actions": actions, "notes": notes}})

        if d == "COMPLETE":
            state = _read_json(paths.state_file)
            incomplete, total = _dispatch_unit_completion(state)
            print(f"[loop] COMPLETE: {notes}")
            print(f"[loop] dispatch_units incomplete={incomplete}/{total}")
            return 0

        action_list = ", ".join(a["type"] for a in actions) if actions else "(none)"
        print(f"[loop] iteration={iteration} decision=CONTINUE actions={action_list}")
        if notes:
            print(f"[loop] notes: {notes}")

        for action in actions:
            t = action["type"]
            if t == "halt":
                recent_events.append({"iteration": iteration, "action": t, "success": True})
                print("[loop] HALT")
                return 0

            if t == "assign_dispatch":
                prompt = _build_assignment_prompt(paths)
                code, stdout, stderr = _run(
                    ["codeagent-wrapper", "--backend", assign_backend, "-"],
                    input_text=prompt,
                    cwd=workdir,
                )
                if code != 0:
                    raise RuntimeError(f"assign_dispatch failed (exit {code}): {stderr.strip() or stdout.strip()}")
                assignments = _json_from_text(stdout)
                if not isinstance(assignments, dict):
                    raise ValueError("assign_dispatch output is not a JSON object")
                _apply_assignments(paths.state_file, assignments)
                recent_events.append({"iteration": iteration, "action": t, "success": True})
                print("[loop] assign_dispatch: ok")
                continue

            if t == "dispatch_batch":
                payload = _run_python_script(
                    scripts_dir / "dispatch_batch.py",
                    [str(paths.state_file), "--workdir", str(workdir)],
                    cwd=workdir,
                )
                recent_events.append({"iteration": iteration, "action": t, "success": bool(payload.get("success")), "message": payload.get("message")})
                print(f"[loop] dispatch_batch: {payload.get('message')}")
                continue

            if t == "dispatch_reviews":
                payload = _run_python_script(
                    scripts_dir / "dispatch_reviews.py",
                    [str(paths.state_file), "--workdir", str(workdir)],
                    cwd=workdir,
                )
                recent_events.append({"iteration": iteration, "action": t, "success": bool(payload.get("success")), "message": payload.get("message")})
                print(f"[loop] dispatch_reviews: {payload.get('message')}")
                continue

            if t == "consolidate_reviews":
                payload = _run_python_script(
                    scripts_dir / "consolidate_reviews.py",
                    [str(paths.state_file)],
                    cwd=workdir,
                )
                recent_events.append({"iteration": iteration, "action": t, "success": bool(payload.get("success")), "message": payload.get("message")})
                print(f"[loop] consolidate_reviews: {payload.get('message')}")
                continue

            if t == "sync_pulse":
                payload = _run_python_script(
                    scripts_dir / "sync_pulse.py",
                    [str(paths.state_file), str(paths.pulse_file)],
                    cwd=workdir,
                )
                recent_events.append({"iteration": iteration, "action": t, "success": bool(payload.get("success")), "message": payload.get("message")})
                print(f"[loop] sync_pulse: {payload.get('message')}")
                continue

        state = _read_json(paths.state_file)
        incomplete, total = _dispatch_unit_completion(state)
        recent_events.append({"iteration": iteration, "dispatch_units": {"incomplete": incomplete, "total": total}})
        print(f"[loop] dispatch_units incomplete={incomplete}/{total}")

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return 1


def _init_from_spec(spec_path: Path, *, session_name: str, cwd: Path) -> RunnerPaths:
    scripts_dir = Path(__file__).parent
    payload = _run_python_script(
        scripts_dir / "init_orchestration.py",
        [str(spec_path), "--session", session_name, "--mode", "codex"],
        cwd=cwd,
    )
    if not payload.get("success"):
        raise RuntimeError(payload.get("message") or "init failed")
    return _infer_paths(Path(payload["state_file"]), Path(payload["tasks_file"]), Path(payload["pulse_file"]))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Ralph-style orchestration loop")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="Spec directory (requirements.md/design.md/tasks.md)", type=str)
    src.add_argument("--state", help="Path to AGENT_STATE.json", type=str)
    parser.add_argument("--tasks", help="Path to TASKS_PARSED.json (optional)", type=str)
    parser.add_argument("--pulse", help="Path to PROJECT_PULSE.md (optional)", type=str)
    parser.add_argument("--workdir", help="Working directory for dispatch/review scripts", default=".", type=str)
    parser.add_argument("--session", help="Session name for init_orchestration (when using --spec)", default="orchestration", type=str)
    parser.add_argument("--backend", help="Backend for orchestrator (codex/claude/gemini)", default="codex", type=str)
    parser.add_argument("--assign-backend", help="Backend for assign_dispatch (default: codex)", default="codex", type=str)
    parser.add_argument("--max-iterations", default=50, type=int)
    parser.add_argument("--sleep", default=1.0, type=float)
    parser.add_argument("--max-actions", default=6, type=int)

    args = parser.parse_args(argv)
    workdir = Path(args.workdir).resolve()

    if args.spec:
        paths = _init_from_spec(Path(args.spec), session_name=args.session, cwd=workdir)
    else:
        state_file = Path(args.state).resolve()
        tasks_file = Path(args.tasks).resolve() if args.tasks else None
        pulse_file = Path(args.pulse).resolve() if args.pulse else None
        paths = _infer_paths(state_file, tasks_file, pulse_file)

    return run_loop(
        backend=args.backend,
        assign_backend=args.assign_backend,
        paths=paths,
        workdir=workdir,
        max_iterations=args.max_iterations,
        sleep_seconds=args.sleep,
        max_actions=args.max_actions,
    )


if __name__ == "__main__":
    raise SystemExit(main())
