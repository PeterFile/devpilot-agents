---
name: sequential-orchestration
description: "Execute spec tasks one at a time with configurable delays. Fully self-contained, no external dependencies. Triggers on: rate limit, overnight run, throttled execution, avoid quota exhaustion, sequential mode, slow execution."
---

# Sequential Orchestration

Ralph-style single-task execution loop. Fully self-contained.

## Usage

```bash
./runner.sh --spec <spec_path> [--delay 30] [--max-iterations 50]
```

## Parameters

| Parameter          | Default  | Description                |
| ------------------ | -------- | -------------------------- |
| `--spec`           | required | Path to spec directory     |
| `--delay`          | 5        | Seconds between iterations |
| `--max-iterations` | 50       | Maximum loop iterations    |

## Required Spec Files

Your spec directory must contain:

- `requirements.md` - What to build
- `design.md` - How to build it
- `tasks.md` - Task breakdown (numbered list)

## How It Works

```
for i in 1..MAX_ITERATIONS:
    1. Agent reads spec files directly
    2. Agent finds next incomplete task
    3. Agent implements ONE task
    4. Agent updates state and progress
    5. Check for <promise>COMPLETE</promise>
    6. Sleep DELAY seconds
    7. Repeat with fresh context
```

## State Files

Generated in **parent** of spec directory:

```
.kiro/specs/
├── my-feature/           # Spec directory
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
├── sequential_state.json # State (in parent)
└── sequential_progress.txt
```

## Exit Codes

| Code | Meaning                |
| ---- | ---------------------- |
| 0    | All tasks completed    |
| 1    | Max iterations reached |
| 2    | Halted (blocked)       |
