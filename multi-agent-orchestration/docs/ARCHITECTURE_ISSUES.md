# Architecture Issues

This document captures fundamental architecture issues discovered during implementation review.

## Issue: Script-Driven vs AI-Driven Orchestration

**Severity:** Critical  
**Status:** Open  
**Impact:** Core system design

### Problem Statement

The current implementation delegates intelligent decision-making to Python scripts instead of the Codex orchestrator. This defeats the purpose of having an AI orchestrator.

### Current (Incorrect) Architecture

```
Kiro Spec Phase              Script-Driven Execution
     │                              │
     ▼                              ▼
tasks.md ──────────────► init_orchestration.py
design.md                    (hardcoded logic)
requirements.md                     │
                                    ▼
                            AGENT_STATE.json
                            (script-generated)
                                    │
                                    ▼
                            dispatch_batch.py
                            (hardcoded window assignment)
                                    │
                                    ▼
                            codeagent-wrapper
```

**Problems:**
1. `init_orchestration.py` generates AGENT_STATE with hardcoded logic
2. `dispatch_batch.py` assigns `target_window` by agent type (not intelligent)
3. Codex only "calls scripts" - no decision-making authority
4. Cannot leverage AI capabilities for:
   - Smart task grouping
   - Load balancing across windows
   - Dynamic priority adjustment
   - Context-aware batch planning

### Expected (Correct) Architecture

```
Kiro Spec Phase              Codex Orchestrator Phase
     │                              │
     ▼                              ▼
tasks.md ──────────────► Codex reads + analyzes
design.md                           │
requirements.md                     ▼
                            Codex generates AGENT_STATE.json
                            (using template + AI reasoning)
                                    │
                                    ▼
                            Codex generates PROJECT_PULSE.md
                            (using template + context)
                                    │
                                    ▼
                            Codex calls codeagent-wrapper
                            (with intelligent task config)
                                    │
                                    ▼
                            Codex monitors + adjusts
                            (dynamic re-planning)
```

### Role Separation

| Component | Current Role | Expected Role |
|-----------|--------------|---------------|
| Python Scripts | Generate state, make decisions | Parse, validate, execute |
| Codex Orchestrator | Call scripts | Analyze, decide, generate, monitor |
| codeagent-wrapper | Execute tasks | Execute tasks (unchanged) |

### Scripts Should Only Handle

1. **Parsing & Validation**
   - Validate spec directory structure
   - Parse tasks.md syntax
   - Validate against JSON schema

2. **Execution Tools**
   - Invoke codeagent-wrapper with Codex-provided config
   - Sync state files after execution
   - Report execution results

3. **Templates & Schema**
   - Provide AGENT_STATE.json schema
   - Provide PROJECT_PULSE.md template
   - Provide example configurations

### Codex Should Handle

1. **Intelligent Analysis**
   - Analyze task dependencies
   - Identify parallelization opportunities
   - Detect potential conflicts

2. **Smart Generation**
   - Generate AGENT_STATE.json with intelligent `target_window` assignment
   - Group related tasks into same window
   - Balance load across windows (max 9)
   - Set task priorities based on critical path

3. **Dynamic Orchestration**
   - Monitor execution progress
   - Re-plan on failures
   - Adjust priorities based on results

4. **Context-Aware Decisions**
   - Consider task descriptions for grouping
   - Use design.md context for architectural decisions
   - Apply domain knowledge for optimization

### Example: Window Assignment

**Current (Script-Driven):**
```python
# dispatch_batch.py - hardcoded
def assign_target_window(task):
    return task["owner_agent"]  # Always "gemini" or "kiro-cli"
```

**Expected (Codex-Driven):**
```
Codex analyzes tasks and decides:
- Tasks 1.1, 1.2, 1.3 → window "setup" (project initialization)
- Tasks 2.1-2.7 → window "backend-api" (related backend work)
- Tasks 4.1-4.4 → window "layout" (UI layout components)
- Tasks 5.1-5.7 → window "task-ui" (task display components)
- Task 3, 7, 13 → window "checkpoints" (verification tasks)
...
```

### Migration Path

1. **Phase 1: Refactor Scripts**
   - Remove decision logic from `init_orchestration.py`
   - Make it a pure parser/validator
   - Output parsed tasks as JSON for Codex to consume

2. **Phase 2: Create Templates**
   - AGENT_STATE.json template with placeholders
   - Instructions for Codex on how to fill placeholders
   - Examples of good window assignments

3. **Phase 3: Update Skill Instructions**
   - SKILL.md should instruct Codex to generate state files
   - Provide decision criteria for window assignment
   - Include examples of intelligent grouping

4. **Phase 4: Simplify dispatch_batch.py**
   - Accept Codex-generated config directly
   - Remove `target_window` assignment logic
   - Focus on execution and reporting

### References

- Requirements: 1.3, 11.4, 11.5 (orchestrator decision-making)
- `multi-agent-orchestration/skill/scripts/init_orchestration.py`
- `multi-agent-orchestration/skill/scripts/dispatch_batch.py`
- `multi-agent-orchestration/skill/SKILL.md`
