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
2. Identify **Dispatch Units** (tasks that get dispatched independently):
   - **Parent tasks**: Tasks with `subtasks` array (e.g., task "1" with subtasks ["1.1", "1.2", "1.3"])
   - **Standalone tasks**: Tasks with no parent AND no subtasks
   - **NOT dispatch units**: Leaf tasks with parents (e.g., "1.1" belongs to parent "1")

3. For EACH **Dispatch Unit only**, decide and fill in:
   - `owner_agent`: Choose based on task type
     - `kiro-cli` for code implementation, refactoring, bug fixes
     - `gemini` for UI components, frontend work
     - `codex` for reviews, documentation
   - `target_window`: One window per dispatch unit (max 9 windows)
     - Format: `task-{task_id}` (e.g., "task-1", "task-2")
   - `criticality`: Assess complexity
     - `standard` for routine tasks
     - `complex` for multi-file changes
     - `security-sensitive` for auth, data handling
   - `writes`: Files the task will create or modify
     - Example: `["src/components/Dashboard.tsx", "src/api/dashboard.py"]`
     - Be specific about file paths based on task description
   - `reads`: Files the task will read but not modify
     - Example: `["src/config.py", "src/types/index.ts"]`
     - Include shared dependencies

**Parallel Execution Rules:**
- Tasks with non-overlapping `writes` arrays can run in parallel
- Tasks WITHOUT `writes`/`reads` will be executed serially (conservative default)
- Accurate file manifests enable maximum parallelism

4. **DO NOT** assign `owner_agent` or `target_window` to leaf tasks with parents - they inherit from their parent dispatch unit

5. Write your decisions back to AGENT_STATE.json
6. Update PROJECT_PULSE.md with Mental Model section

**Dispatch Unit Concept:**
- Parent task "1" with subtasks ["1.1", "1.2", "1.3"] = 1 dispatch unit = 1 window
- Agent executes 1.1 → 1.2 → 1.3 sequentially in same window
- One review dispatched for entire parent task, not per subtask

## Step 3: Verify Assignments

Before dispatch, verify all **dispatch units** have assignments:

```bash
python -c "
import json
d = json.load(open('<state_file>'))
# Only check dispatch units: parent tasks (have subtasks) OR standalone tasks (no parent, no subtasks)
dispatch_units = [t for t in d['tasks'] if t.get('subtasks') or (not t.get('parent_id') and not t.get('subtasks'))]
missing = [t['task_id'] for t in dispatch_units if not t.get('owner_agent') or not t.get('target_window')]
print(f'Missing dispatch unit assignments: {len(missing)}')
[print(f'  - {tid}') for tid in missing]
"
```

If any dispatch units are missing assignments, go back to Step 2.

**Note:** Leaf tasks with parents (e.g., "1.1", "1.2") do NOT need `owner_agent` or `target_window` - they inherit from their parent dispatch unit.

## Step 4: Dispatch Loop

The dispatch system automatically handles **Dispatch Units**:
- Parent tasks dispatch with all subtasks bundled together
- Agent executes subtasks sequentially in same window
- One review per dispatch unit (not per subtask)

Dispatch ready dispatch units:

```bash
python multi-agent-orchestration/skill/scripts/dispatch_batch.py <state_file>
```

Dispatch reviews for completed dispatch units:

```bash
python multi-agent-orchestration/skill/scripts/dispatch_reviews.py <state_file>
```

Consolidate review findings into final reports, and advance tasks to `completed` (or `fix_required` for the fix loop):

```bash
python multi-agent-orchestration/skill/scripts/consolidate_reviews.py <state_file>
```

Sync state to PULSE:

```bash
python multi-agent-orchestration/skill/scripts/sync_pulse.py <state_file> <pulse_file>
```

Check completion (count incomplete dispatch units, not leaf tasks):

```bash
python -c "
import json
d = json.load(open('<state_file>'))
# Check dispatch units only
dispatch_units = [t for t in d['tasks'] if t.get('subtasks') or (not t.get('parent_id') and not t.get('subtasks'))]
incomplete = [t for t in dispatch_units if t.get('status') != 'completed']
print(f'Incomplete dispatch units: {len(incomplete)}/{len(dispatch_units)}')
"
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
