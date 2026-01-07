# Requirements Document

## Introduction

A multi-agent orchestration system with two distinct phases:
1. **Spec Phase (Kiro)**: User interacts with Kiro IDE to create requirements.md, design.md, and tasks.md
2. **Execution Phase (Codex + Workers)**: Codex orchestrates kiro-cli (code) and Gemini (UI) to implement the tasks

The system extends the existing agent-pulse-coordination skill with a dual-document architecture (PROJECT_PULSE.md + AGENT_STATE.json). Codex replaces Claude Code as the central orchestrator for the execution phase only.

## Glossary

- **Spec_Phase**: The initial phase where user interacts with Kiro IDE to produce specs (requirements.md, design.md, tasks.md)
- **Execution_Phase**: The phase where Codex orchestrates worker agents to implement tasks from the approved spec
- **Orchestrator**: The Codex agent responsible for task planning, coordination, and dispatching work to specialized agents during Execution_Phase
- **Kiro**: The Kiro IDE used for writing requirement specs during Spec_Phase (independent of Codex orchestration)
- **Kiro_CLI**: The command-line version of Kiro IDE, used as the primary code implementation agent
- **Gemini**: Google's AI model used as the primary UI/frontend development agent
- **PULSE_Document**: Human-readable project status dashboard (PROJECT_PULSE.md)
- **Agent_State**: Machine-readable coordination state file (AGENT_STATE.json)
- **State_Manager**: Component responsible for maintaining AGENT_STATE.json and PROJECT_PULSE.md, including sync_pulse() for synchronization
- **codeagent-wrapper**: Go binary that handles task execution, JSON stream parsing, and state file updates
- **Tmux_Session**: A tmux session containing multiple panes for different agents
- **Agent_Pane**: A dedicated tmux pane where a specific agent runs
- **Task_Dispatch**: The process of Codex assigning tasks to specialized agents
- **Skill**: A Codex capability package containing instructions, resources, and optional scripts
- **Review_Codex**: A separate Codex instance spawned specifically to review completed tasks
- **Task_Window**: A tmux window dedicated to a task and its dependent tasks

## Requirements

### Requirement 1: Codex Orchestrator Setup (Execution Phase)

**User Story:** As a developer, I want Codex to act as the central orchestrator during execution phase, so that I can coordinate multiple AI agents without using Claude Code.

#### Acceptance Criteria

1. WHEN Execution_Phase starts, THE Orchestrator SHALL read the approved tasks.md from the spec directory
2. THE Orchestrator SHALL parse tasks.md and create corresponding entries in AGENT_STATE.json
3. WHEN a task is ready for execution, THE Orchestrator SHALL determine the appropriate agent (Kiro_CLI or Gemini) based on task type
4. WHEN dispatching a task, THE Orchestrator SHALL update the task status to "in_progress" in AGENT_STATE.json
5. THE Orchestrator SHALL use Codex custom prompts to define reusable orchestration commands
6. THE Orchestrator SHALL use Codex skills to package agent-specific capabilities
7. IF a task has unresolved dependencies, THEN THE Orchestrator SHALL mark it as "blocked" and record the blocking reason

### Requirement 2: Kiro Spec Phase (Pre-Orchestration)

**User Story:** As a developer, I want to complete spec writing in Kiro before starting orchestration, so that I have a clear plan before implementation begins.

#### Acceptance Criteria

1. THE Spec_Phase SHALL be completed entirely within Kiro IDE before Execution_Phase begins
2. WHEN a feature request is received, THE User SHALL interact with Kiro to generate requirements.md following EARS patterns
3. WHEN requirements are approved by user, THE User SHALL interact with Kiro to generate design.md with architecture and correctness properties
4. WHEN design is approved by user, THE User SHALL interact with Kiro to generate tasks.md with implementation checklist
5. THE Spec_Phase SHALL produce three files: requirements.md, design.md, and tasks.md in .kiro/specs/{feature_name}/
6. WHEN all three spec files are approved, THE User SHALL trigger the Execution_Phase by invoking Codex with the spec path

### Requirement 3: Kiro-CLI Code Implementation

**User Story:** As a developer, I want kiro-cli to handle code implementation tasks, so that I have a dedicated agent for writing and modifying code.

#### Acceptance Criteria

1. WHEN the Orchestrator dispatches a code task, THE Kiro_CLI SHALL receive the task via tmux pane
2. THE Kiro_CLI SHALL execute code modifications in the target repository
3. WHEN code changes are complete, THE Kiro_CLI SHALL update task status to "pending_review" in AGENT_STATE.json
4. THE Kiro_CLI SHALL support MCP (Model Context Protocol) for tool integration
5. IF an error occurs during implementation, THEN THE Kiro_CLI SHALL report the error and mark the task as "blocked"

### Requirement 4: Gemini UI Frontend

**User Story:** As a developer, I want Gemini to handle UI/frontend tasks, so that I have a specialized agent for visual components.

#### Acceptance Criteria

1. WHEN the Orchestrator dispatches a UI task, THE Gemini SHALL receive the task via tmux pane
2. THE Gemini SHALL generate or modify frontend code (HTML, CSS, JavaScript, React, etc.)
3. WHEN UI changes are complete, THE Gemini SHALL update task status to "pending_review" in AGENT_STATE.json
4. THE Gemini SHALL follow design specifications from the design.md file
5. IF the UI task requires backend integration, THEN THE Gemini SHALL create a dependency on the relevant Kiro_CLI task

### Requirement 5: Tmux Window/Pane Management

**User Story:** As a developer, I want tasks organized in tmux windows with dependency-aware pane grouping, so that I can monitor related tasks together.

#### Acceptance Criteria

1. WHEN the orchestration system starts, THE System SHALL create a tmux session with a main window containing Orchestrator pane and Status pane
2. WHEN a task without dependencies starts, THE System SHALL create a new tmux window for that task's agent (Kiro_CLI or Gemini)
3. WHEN a task with dependencies starts, THE System SHALL create a new pane in the same window as its dependency task
4. THE System SHALL name each window with the primary task identifier (e.g., "task-001")
5. WHEN an agent completes a task, THE System SHALL trigger a tmux hook to notify the Orchestrator
6. THE System SHALL use tmux hooks (pane-focus-in, pane-died) to track agent activity
7. WHEN a pane receives focus, THE System SHALL acknowledge the current task in AGENT_STATE.json
8. THE System SHALL integrate with the existing tmux configuration for consistent keybindings
9. WHEN all tasks in a window complete, THE System SHALL optionally close the window or keep it for reference

### Requirement 6: Dual-Document Architecture

**User Story:** As a developer, I want both human-readable and machine-readable state documents, so that I can quickly understand project status while agents coordinate efficiently.

#### Acceptance Criteria

1. THE State_Manager SHALL maintain PROJECT_PULSE.md with Mental Model, Narrative Delta, Risks & Debt, and Semantic Anchors sections
2. THE System SHALL maintain AGENT_STATE.json with tasks, review_findings, final_reports, blocked_items, pending_decisions, deferred_fixes, and window_mapping
3. WHEN a task transitions state, THE System SHALL update both PULSE_Document and Agent_State via State_Manager.sync_pulse()
4. THE PULSE_Document SHALL be readable by humans in 30 seconds or less
5. THE Agent_State SHALL conform to the agent-state-schema.json JSON Schema
6. WHEN pending_decisions exist for more than 24 hours, THE State_Manager SHALL escalate visibility in PULSE_Document Risks & Debt section

### Requirement 7: Task State Machine

**User Story:** As a developer, I want tasks to follow a defined state machine, so that task progress is predictable and trackable.

#### Acceptance Criteria

1. THE System SHALL support task states: not_started, in_progress, pending_review, under_review, final_review, completed, blocked
2. THE System SHALL use "not_started" as the initial state for all newly created tasks
3. WHEN a Worker starts a task, THE System SHALL transition it from "not_started" to "in_progress"
4. WHEN a Worker completes a task, THE System SHALL transition it from "in_progress" to "pending_review"
5. WHEN a Review starts, THE System SHALL transition the task from "pending_review" to "under_review"
6. WHEN all reviews complete, THE System SHALL transition the task from "under_review" to "final_review"
7. WHEN Final Report is produced, THE System SHALL transition the task from "final_review" to "completed"
8. IF an invalid state transition is attempted, THEN THE System SHALL reject it and log an error
9. THE System SHALL support criticality levels: standard, complex, security-sensitive
10. THE System SHALL allow transition from "blocked" back to "not_started" or "in_progress" when blocker is resolved

### Requirement 8: Codex Review Execution

**User Story:** As a developer, I want task reviews to be executed by a separate Codex instance, so that review is independent from implementation.

#### Acceptance Criteria

1. WHEN a task transitions to "pending_review", THE Orchestrator SHALL spawn a new Review_Codex instance
2. THE Review_Codex SHALL run in a new pane within the task's window
3. THE Review_Codex SHALL audit the code changes produced by the Worker agent
4. THE Review_Codex SHALL produce a Review_Finding with severity assessment (critical, major, minor, none)
5. FOR standard criticality tasks, THE System SHALL require exactly 1 Review_Codex
6. FOR complex or security-sensitive tasks, THE System SHALL spawn multiple Review_Codex instances in parallel
7. WHEN Review_Codex completes, THE System SHALL update review_findings in AGENT_STATE.json
8. THE Review_Codex SHALL NOT modify the implementation code directly
9. WHEN all Review_Codex instances complete, THE Orchestrator SHALL consolidate findings into a Final_Report

### Requirement 9: Agent Communication Protocol

**User Story:** As a developer, I want agents to communicate through a structured protocol, so that coordination is reliable and traceable.

#### Acceptance Criteria

1. THE Orchestrator SHALL dispatch tasks by invoking codeagent-wrapper --parallel with all ready tasks in a single call
2. THE codeagent-wrapper SHALL execute tasks and return a structured Execution Report synchronously
3. THE Orchestrator SHALL wait for codeagent-wrapper to complete before processing results
4. WHEN codeagent-wrapper completes, THE Orchestrator SHALL read the Execution Report and update AGENT_STATE.json
5. THE codeagent-wrapper SHALL write task progress to AGENT_STATE.json in real-time during execution
6. WHEN an agent encounters a blocker, THE codeagent-wrapper SHALL add an entry to blocked_items with blocking_reason and required_resolution
7. WHEN an agent needs human input, THE System SHALL add an entry to pending_decisions with context and options
8. THE System SHALL use file-based state via AGENT_STATE.json for persistence and human visibility
9. WHEN AGENT_STATE.json is modified, THE System SHALL validate it against the schema
10. THE Orchestrator SHALL invoke codeagent-wrapper multiple times: once for implementation tasks, then for review tasks

### Requirement 10: Codex Skills and Custom Prompts

**User Story:** As a developer, I want to define reusable Codex skills and prompts, so that orchestration patterns are consistent and shareable.

#### Acceptance Criteria

1. THE System SHALL create a Codex skill for orchestrating multi-agent workflows
2. THE System SHALL create custom prompts for common orchestration commands (dispatch-task, check-status, sync-pulse)
3. THE Skill SHALL include SKILL.md with name, description, and instructions
4. THE Skill SHALL support both explicit invocation (via /skills or $) and implicit invocation based on task context
5. WHEN a skill is invoked, THE Orchestrator SHALL load full instructions and referenced resources
6. THE System SHALL store skills in ~/.codex/skills for user-scope availability

### Requirement 11: Spec-to-Execution Handoff

**User Story:** As a developer, I want a clear handoff from Kiro spec phase to Codex execution phase, so that implementation can begin with a well-defined plan.

#### Acceptance Criteria

1. WHEN user completes Spec_Phase in Kiro, THE User SHALL invoke Codex with the spec directory path
2. THE Orchestrator SHALL validate that requirements.md, design.md, and tasks.md exist in the spec directory
3. THE Orchestrator SHALL parse tasks.md and extract individual tasks with their dependencies
4. FOR EACH task in tasks.md, THE Orchestrator SHALL create a corresponding entry in AGENT_STATE.json with status "not_started"
5. THE Orchestrator SHALL assign owner_agent based on task type (Kiro_CLI for code, Gemini for UI)
6. THE Orchestrator SHALL set initial criticality based on task markers (* for optional, security keywords for security-sensitive)
7. WHEN parsing fails, THE Orchestrator SHALL report the error and request manual intervention
8. THE Orchestrator SHALL initialize PROJECT_PULSE.md with Mental Model from design.md

### Requirement 12: codeagent-wrapper Integration

**User Story:** As a developer, I want to reuse the existing codeagent-wrapper for task execution, so that I benefit from its proven JSON parsing, parallel execution, and error handling capabilities.

#### Acceptance Criteria

1. THE System SHALL extend codeagent-wrapper with a new "kiro-cli" backend for kiro-cli integration
2. THE codeagent-wrapper SHALL support `--tmux-session <name>` flag to enable tmux visualization mode
3. THE codeagent-wrapper SHALL support `--tmux-attach` flag to keep tmux session alive after completion
4. THE codeagent-wrapper SHALL support `--state-file <path>` flag to specify AGENT_STATE.json location for real-time updates
5. WHEN `--tmux-session` is provided, THE codeagent-wrapper SHALL create a tmux window for each independent task
6. WHEN a task has dependencies, THE codeagent-wrapper SHALL create a pane in the dependency's window instead of a new window
7. THE codeagent-wrapper SHALL execute tasks within tmux panes while maintaining synchronous return to caller
8. WHEN all tasks complete, THE codeagent-wrapper SHALL return a structured Execution Report to the Orchestrator
9. THE tmux session SHALL persist after codeagent-wrapper exits, allowing user to review task history
10. THE codeagent-wrapper SHALL reuse existing JSON stream parsing, topological sort, timeout handling, and error recovery logic
11. THE codeagent-wrapper SHALL support `--window-for <task_id>` flag for single-task mode to create pane in existing window
