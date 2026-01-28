# Sequential Task Execution

You are executing tasks from a spec directory ONE at a time.

## Your Task

1. Read the spec files at `{{SPEC_PATH}}/`:
   - `requirements.md` - What to build
   - `design.md` - How to build it
   - `tasks.md` - Task breakdown

2. Read the state at `{{STATE_FILE}}`

3. Read the progress log at `{{PROGRESS_FILE}}`

4. Find the **next incomplete task** from `tasks.md`:
   - Parse the task list (numbered or bulleted items)
   - Skip tasks already in state's `completed` array
   - Pick the first incomplete task

5. Implement that **single task** completely:
   - Write the code
   - Run quality checks (typecheck, lint, test)
   - Fix any issues

6. **Add valuable learnings** - If you discovered something future developers/agents should know:
   - API patterns or conventions specific to that module
   - Gotchas or non-obvious requirements
   - Dependencies between files
   - Testing approaches for that area
   - Configuration or environment requirements

   **Examples of good AGENTS.md additions:**
   - "When modifying X, also update Y to keep them in sync"
   - "This module uses pattern Z for all API calls"
   - "Tests require the dev server running on PORT 3000"
   - "Field names must match the template exactly"

   **Do NOT add:**
   - Story-specific implementation details
   - Temporary debugging notes
   - Information already in progress.txt

   Only update AGENTS.md if you have **genuinely reusable knowledge** that would help future work in that directory.

7. If successful:
   - Commit with message: `feat: [task description]`
   - Update `{{STATE_FILE}}`: add task ID to `completed` array
   - Append progress to `{{PROGRESS_FILE}}`

## State File Format

```json
{
  "completed": ["1", "2", "3"]
}
```

Task IDs are the task numbers from `tasks.md`.

## Progress File Format

```
# Sequential Execution Progress

Spec: /path/to/spec
Started: 2026-01-28T10:00:00Z

## Iteration 1
- Task: 1 - Implement user authentication
- Status: Completed
- Files: src/auth.ts

## Iteration 2
- Task: 2 - Add login endpoint
- Status: Completed
- Files: src/routes/login.ts

Completed: 2026-01-28T11:30:00Z
```

## Stop Conditions

### All Complete

After completing your task, check if ALL tasks from `tasks.md` are in `completed` array.

If ALL tasks are complete, reply with:

```
<promise>COMPLETE</promise>
```

### Blocked

If you cannot proceed (missing dependency, unclear requirement), reply with:

```
<promise>HALT</promise>
```

### More Work

If there are still incomplete tasks, end your response normally.
Another iteration will pick up the next task.

## Critical Rules

- Work on **ONE** task per iteration
- Do NOT start multiple tasks
- Execute tasks in order (1, 2, 3, ...)
- Fresh context each iteration - always read state first
- Commit after each successful task
- Update both state file and progress file
