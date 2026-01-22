#!/usr/bin/env python3

from pathlib import Path

import pytest

import orchestration_loop as loop


def test_json_from_text_extracts_first_object():
    text = "hello\n{\n  \"decision\": \"CONTINUE\",\n  \"actions\": []\n}\n---\nSESSION_ID: 123\n"
    obj = loop._json_from_text(text)
    assert obj["decision"] == "CONTINUE"
    assert obj["actions"] == []


def test_validate_decision_normalizes_actions():
    d, actions, notes = loop._validate_decision({"decision": "continue", "actions": ["sync_pulse"], "notes": "ok"})
    assert d == "CONTINUE"
    assert actions == [{"type": "sync_pulse"}]
    assert notes == "ok"


def test_infer_paths_from_state_directory(tmp_path: Path):
    state = tmp_path / "AGENT_STATE.json"
    tasks = tmp_path / "TASKS_PARSED.json"
    pulse = tmp_path / "PROJECT_PULSE.md"
    state.write_text("{}", encoding="utf-8")
    tasks.write_text("{}", encoding="utf-8")
    pulse.write_text("# pulse\n", encoding="utf-8")

    paths = loop._infer_paths(state, None, None)
    assert paths.state_file == state
    assert paths.tasks_file == tasks
    assert paths.pulse_file == pulse


def test_dispatch_unit_completion_counts_parent_and_standalone(tmp_path: Path):
    state_path = tmp_path / "AGENT_STATE.json"
    loop._write_json(
        state_path,
        {
            "tasks": [
                {"task_id": "1", "subtasks": ["1.1"], "status": "not_started"},
                {"task_id": "1.1", "parent_id": "1", "status": "not_started"},
                {"task_id": "2", "status": "not_started"},
            ],
            "window_mapping": {},
        },
    )

    state = loop._read_json(state_path)
    incomplete, total = loop._dispatch_unit_completion(state)
    assert (incomplete, total) == (2, 2)


def test_apply_assignments_updates_dispatch_units_only(tmp_path: Path):
    state_path = tmp_path / "AGENT_STATE.json"
    loop._write_json(
        state_path,
        {
            "tasks": [
                {"task_id": "1", "subtasks": ["1.1"], "status": "not_started"},
                {"task_id": "1.1", "parent_id": "1", "status": "not_started"},
            ],
            "window_mapping": {},
        },
    )

    loop._apply_assignments(
        state_path,
        {
            "dispatch_units": [
                {"task_id": "1", "owner_agent": "codex", "target_window": "task-1", "criticality": "standard"},
                {"task_id": "1.1", "owner_agent": "gemini", "target_window": "leaf"},
            ],
            "window_mapping": {"1": "task-1"},
        },
    )

    state = loop._read_json(state_path)
    task_map = {t["task_id"]: t for t in state["tasks"]}
    assert task_map["1"]["owner_agent"] == "codex"
    assert "owner_agent" not in task_map["1.1"]
    assert state["window_mapping"]["1"] == "task-1"


def test_validate_decision_rejects_unknown_action():
    with pytest.raises(ValueError):
        loop._validate_decision({"decision": "CONTINUE", "actions": [{"type": "rm_rf"}]})


def test_exit_code_from_state_returns_0_when_complete():
    assert loop._exit_code_from_state({"tasks": [{"task_id": "1", "status": "completed"}]}) == 0


def test_exit_code_from_state_returns_2_when_pending_decisions():
    assert loop._exit_code_from_state({"pending_decisions": [{"id": "d1"}], "tasks": []}) == 2


def test_run_loop_llm_returns_2_without_calling_orchestrator_when_pending_decisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    state_path = tmp_path / "AGENT_STATE.json"
    pulse_path = tmp_path / "PROJECT_PULSE.md"
    state_path.write_text('{"pending_decisions":[{"id":"d1","task_id":"1"}],"tasks":[{"task_id":"1","status":"not_started"}]}', encoding="utf-8")
    pulse_path.write_text("# pulse\n", encoding="utf-8")

    def _nope(*_args, **_kwargs):
        raise AssertionError("_call_orchestrator should not be called when pending_decisions exists")

    monkeypatch.setattr(loop, "_call_orchestrator", _nope)

    paths = loop.RunnerPaths(state_file=state_path, tasks_file=None, pulse_file=pulse_path)
    rc = loop.run_loop_llm(
        backend="codex",
        assign_backend="codex",
        paths=paths,
        workdir=tmp_path,
        max_iterations=1,
        sleep_seconds=0,
        max_actions=1,
    )
    assert rc == 2


def test_run_loop_llm_complete_requires_all_dispatch_units_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    state_path = tmp_path / "AGENT_STATE.json"
    pulse_path = tmp_path / "PROJECT_PULSE.md"
    loop._write_json(state_path, {"tasks": [{"task_id": "1", "status": "not_started"}]})
    pulse_path.write_text("# pulse\n", encoding="utf-8")

    monkeypatch.setattr(loop, "_call_orchestrator", lambda **_kwargs: {"decision": "COMPLETE", "actions": [], "notes": "stop"})

    paths = loop.RunnerPaths(state_file=state_path, tasks_file=None, pulse_file=pulse_path)
    rc = loop.run_loop_llm(
        backend="codex",
        assign_backend="codex",
        paths=paths,
        workdir=tmp_path,
        max_iterations=1,
        sleep_seconds=0,
        max_actions=1,
    )
    assert rc == 1


def test_run_loop_llm_halt_action_returns_1_when_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    state_path = tmp_path / "AGENT_STATE.json"
    pulse_path = tmp_path / "PROJECT_PULSE.md"
    loop._write_json(state_path, {"tasks": [{"task_id": "1", "status": "not_started"}]})
    pulse_path.write_text("# pulse\n", encoding="utf-8")

    monkeypatch.setattr(loop, "_call_orchestrator", lambda **_kwargs: {"decision": "CONTINUE", "actions": [{"type": "halt"}], "notes": "need human"})

    paths = loop.RunnerPaths(state_file=state_path, tasks_file=None, pulse_file=pulse_path)
    rc = loop.run_loop_llm(
        backend="codex",
        assign_backend="codex",
        paths=paths,
        workdir=tmp_path,
        max_iterations=1,
        sleep_seconds=0,
        max_actions=1,
    )
    assert rc == 1
