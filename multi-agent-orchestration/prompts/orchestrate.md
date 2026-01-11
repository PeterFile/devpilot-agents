---
description: Start multi-agent orchestration from a Kiro spec
argument-hint: SPEC_PATH=<path/to/spec>
---

# Multi-Agent Orchestration

You are orchestrating a multi-agent workflow from the spec at: $SPEC_PATH

## Step 1: Initialize

Run the initialization script:

```bash
python multi-agent-orchestration/skill/scripts/init_orchestration.py $SPEC_PATH --session orchestration --mode codex --json
```

Parse the JSON output. If `success` is false, STOP and report the error.

Extract these paths from output:
- `state_file`: Path to AGENT_STATE.json
- `tasks_file`: Path to TASKS_PARSED.json
- `pulse_file`: Path to PROJECT_PULSE.md

## Step 2: Task Assignment (YOUR DECISION)

Read the scaffolded files and make intelligent decisions:

1. Read AGENT_STATE.json and TASKS_PARSED.json
2. For EACH task, decide and fill in:
   - `owner_agent`: Choose based on task type
     - `codex` for code implementation, refactoring, bug fixes
     - `gemini` for UI components, frontend work
     - `claude` for reviews, documentation
   - `target_window`: Group related tasks (max 9 windows)
     - Example: "setup", "backend", "frontend", "api", "tests", "verify"
   - `criticality`: Assess complexity
     - `standard` for routine tasks
     - `complex` for multi-file changes
     - `security-sensitive` for auth, data handling

3. Write your decisions back to AGENT_STATE.json
4. Update PROJECT_PULSE.md with Mental Model section

**Window Grouping Strategy:**
- Initialization tasks → "setup"
- API/service tasks → "backend"
- UI component tasks → "frontend"
- Test tasks → "tests"
- Checkpoint/validation → "verify"

## Step 3: Verify Assignments

Before dispatch, verify all tasks have assignments:

```bash
python -c "import json; d=json.load(open('<state_file>')); missing=[t['task_id'] for t in d['tasks'] if not t.get('owner_agent') or not t.get('target_window')]; print(f'Missing: {len(missing)}'); [print(f'  - {tid}') for tid in missing]"
```

If any tasks are missing assignments, go back to Step 2.

## Step 4: Dispatch Loop

Dispatch ready tasks:

```bash
python multi-agent-orchestration/skill/scripts/dispatch_batch.py <state_file>
```

Dispatch reviews for completed tasks:

```bash
python multi-agent-orchestration/skill/scripts/dispatch_reviews.py <state_file>
```

Sync state to PULSE:

```bash
python multi-agent-orchestration/skill/scripts/sync_pulse.py <state_file> <pulse_file>
```

Check completion:

```bash
python -c "import json; d=json.load(open('<state_file>')); incomplete=[t for t in d['tasks'] if t.get('status')!='completed']; print(f'Incomplete: {len(incomplete)}/{len(d[\"tasks\"])}')"
```

**Decision:**
- If incomplete > 0: REPEAT Step 4
- If incomplete == 0: PROCEED to Step 5

## Step 5: Summary

Report orchestration results:
- Total tasks completed
- Key files changed
- Any review findings
- Duration estimate
