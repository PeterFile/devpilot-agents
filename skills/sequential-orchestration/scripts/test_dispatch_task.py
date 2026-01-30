import types
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_build_bulk_assignment_prompt_uses_at_file_reference():
    from dispatch_task import build_bulk_assignment_prompt

    prompt = build_bulk_assignment_prompt("specs/my-feature/tasks.md", ["1"])
    assert "Read the tasks file: @specs/my-feature/tasks.md" in prompt


def test_ensure_assignments_preserves_existing_and_fills_missing_without_wrapper(monkeypatch):
    import dispatch_task

    def fake_resolve():
        raise FileNotFoundError("no wrapper")

    monkeypatch.setattr(dispatch_task, "resolve_codeagent_wrapper", fake_resolve)

    state = {"assignments": {"1": {"type": "ui", "owner_agent": "gemini"}}}
    result = dispatch_task.ensure_assignments(
        tasks_md_path="tasks.md",
        dispatch_unit_ids=["1", "2"],
        state=state,
        assign_backend="codex",
        workdir=".",
    )

    assert result["1"]["owner_agent"] == "gemini"
    assert result["2"]["owner_agent"] == "codex"


def test_ensure_assignments_sets_opencode_agent_env(monkeypatch):
    import dispatch_task

    monkeypatch.setattr(dispatch_task, "resolve_codeagent_wrapper", lambda: "codeagent-wrapper")

    captured = {}

    def fake_run(args, input, capture_output, text, cwd, env, timeout):
        captured["env"] = env
        return types.SimpleNamespace(returncode=1, stdout="", stderr="opencode failed")

    monkeypatch.setattr(dispatch_task.subprocess, "run", fake_run)

    state = {}
    result = dispatch_task.ensure_assignments(
        tasks_md_path="tasks.md",
        dispatch_unit_ids=["1"],
        state=state,
        assign_backend="opencode",
        assign_opencode_agent="gawain",
        workdir=".",
    )

    assert captured["env"]["CODEAGENT_OPENCODE_AGENT"] == "gawain"
    assert result["1"]["owner_agent"] == "codex"
