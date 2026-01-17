---
description: Start multi-agent orchestration from a Kiro spec. Use when user says "start orchestration", "run orchestration", or "orchestrate spec".
argument-hint: <spec_path>
allowed-tools: Bash(*), Read, Write, Edit
---

# Multi-Agent Orchestration

Orchestrating spec at: $1

## Step 1: Initialize [MANDATORY]

!`python multi-agent-orchestration/skill/scripts/init_orchestration.py $1 --session orchestration --mode codex --json`

Parse the JSON output above. If `success` is false, STOP and report the error.

Extract from output:
- `state_file`: Path to AGENT_STATE.json
- `tasks_file`: Path to TASKS_PARSED.json  
- `pulse_file`: Path to PROJECT_PULSE.md

## Step 2: Codex Decision [MANDATORY - DO NOT SKIP]

Read the scaffolded state file and tasks file:

@${state_file}
@${tasks_file}

**YOU MUST NOW:**

1. For each task in AGENT_STATE.json, fill in:
   - `owner_agent`: Choose `kiro-cli` (code), `gemini` (UI), or `codex` (review)
   - `target_window`: Group related tasks (max 9 windows, e.g., "setup", "backend", "frontend")
   - `criticality`: Set to `standard`, `complex`, or `security-sensitive`

2. Use the Write tool to update AGENT_STATE.json with your decisions.

3. Update PROJECT_PULSE.md with Mental Model from design.md.

**Example task assignment:**
```json
{
  "task_id": "1.1",
  "owner_agent": "kiro-cli",
  "target_window": "setup",
  "criticality": "standard",
  ...
}
```

**Window grouping strategy:**
- Tasks 1.x → "setup" (initialization)
- Tasks 2.x → "backend" (API/services)
- Tasks 4.x-6.x → "frontend" (UI components)
- Checkpoints → "verify" (validation tasks)

After updating AGENT_STATE.json, verify with:

!`python -c "import json; d=json.load(open('${state_file}')); missing=[t['task_id'] for t in d['tasks'] if not t.get('owner_agent') or not t.get('target_window')]; print(f'Missing assignments: {len(missing)}'); [print(f'  - {tid}') for tid in missing[:5]]"`

If any tasks are missing assignments, fix them before proceeding.

## Step 3: Dispatch Loop [MANDATORY - REPEAT UNTIL COMPLETE]

!`python multi-agent-orchestration/skill/scripts/dispatch_batch.py ${state_file}`

If dispatch fails with "missing owner_agent", go back to Step 2.

After dispatch completes:

!`python multi-agent-orchestration/skill/scripts/dispatch_reviews.py ${state_file}`

!`python multi-agent-orchestration/skill/scripts/consolidate_reviews.py ${state_file}`

!`python multi-agent-orchestration/skill/scripts/sync_pulse.py ${state_file} ${pulse_file}`

Check completion:

!`python -c "import json; d=json.load(open('${state_file}')); tasks=d['tasks']; incomplete=[t['task_id'] for t in tasks if t.get('status')!='completed']; print(f'Incomplete: {len(incomplete)}/{len(tasks)}'); [print(f'  - {tid}: {t.get(\"status\")}') for tid,t in [(t['task_id'],t) for t in tasks if t.get('status')!='completed'][:5]]"`

**Decision:**
- If incomplete > 0: REPEAT Step 3
- If incomplete == 0: PROCEED to Step 4

## Step 4: Summary [MANDATORY]

Report orchestration results:

1. Total tasks completed
2. Key files changed
3. Any review findings or issues
4. Duration estimate

