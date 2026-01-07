# Implementation Plan: Multi-Agent Orchestration

## Overview

This implementation plan extends the existing codeagent-wrapper with tmux visualization support and creates a Codex skill for orchestrating multi-agent workflows. The implementation follows a synchronous batch execution model where Codex orchestrates kiro-cli and Gemini workers.

## Tasks

- [x] 1. Extend codeagent-wrapper with tmux support
  - [x] 1.1 Add TmuxManager component (tmux.go)
    - Implement TmuxConfig struct with SessionName, MainWindow, WindowFor, StateFile fields
    - Implement SessionExists(), CreateWindow(), CreatePane(), SendCommand() methods
    - Implement SetupTaskPanes() for batch window/pane creation logic
    - _Requirements: 5.2, 5.3, 5.4, 12.2, 12.5, 12.6_

  - [x] 1.2 Write property tests for TmuxManager
    - **Property 6: Window/Pane Placement by Dependency**
    - **Property 7: Window Naming Convention**
    - **Validates: Requirements 5.2, 5.3, 5.4**

  - [x] 1.3 Add StateWriter component (state.go)
    - Implement AgentState struct with ALL fields (tasks, review_findings, final_reports, blocked_items, pending_decisions, deferred_fixes, window_mapping)
    - Implement WriteTaskResult(), WriteReviewFinding(), WriteFinalReport(), WriteBlockedItem(), WritePendingDecision(), WriteDeferredFix() methods
    - Implement atomic file writes via temp file + rename
    - _Requirements: 6.2, 9.5, 9.6, 9.7_

  - [x] 1.4 Write property tests for StateWriter
    - **Property 11: AGENT_STATE Schema Conformance**
    - **Property 16: codeagent-wrapper State File Update**
    - **Validates: Requirements 6.5, 9.5**

  - [x] 1.5 Add KiroCliBackend (kiro_cli_backend.go)
    - Implement Backend interface: Name() returns "kiro-cli", Command() returns "kiro"
    - Implement BuildArgs() with chat, -C, --json flags
    - Register in backends map
    - _Requirements: 12.1_

  - [x] 1.6 Write unit tests for KiroCliBackend
    - Test BuildArgs() output format
    - Test backend registration
    - _Requirements: 12.1_

- [x] 2. Checkpoint - Ensure all codeagent-wrapper tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Extend codeagent-wrapper CLI and execution flow
  - [x] 3.1 Add new CLI flags to config.go
    - Add --tmux-session, --tmux-attach, --window-for, --state-file, --review flags
    - Update parseArgs() to handle new flags
    - _Requirements: 12.2, 12.3, 12.4, 12.11_

  - [x] 3.2 Implement tmux execution mode in main.go
    - Add runTmuxMode() function for tmux-enabled execution
    - Integrate TmuxManager for window/pane creation
    - Integrate StateWriter for real-time state updates
    - _Requirements: 12.5, 12.6, 12.7_

  - [x] 3.3 Extend parallel executor for tmux support
    - Modify executor.go to use TmuxManager when --tmux-session is provided
    - Implement batch task input parsing (---TASK--- / ---CONTENT--- format)
    - Create windows for independent tasks, panes for dependent tasks
    - _Requirements: 5.2, 5.3, 12.5, 12.6_

  - [x] 3.4 Write property tests for tmux execution mode
    - **Property 17: Tmux Window Creation for Independent Tasks**
    - **Property 18: Tmux Pane Creation for Dependent Tasks**
    - **Validates: Requirements 5.2, 5.3, 5.4**

  - [x] 3.5 Implement Execution Report generation
    - Generate structured JSON report after all tasks complete
    - Include task results, files changed, coverage, test results
    - Return report to caller synchronously
    - _Requirements: 9.2, 12.8_

- [x] 4. Checkpoint - Ensure codeagent-wrapper builds and tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement State Manager and validation
  - [x] 5.1 Create agent-state-schema.json
    - Define JSON Schema for AGENT_STATE.json
    - Include all required fields: spec_path, session_name, tasks, review_findings, final_reports, blocked_items, pending_decisions, deferred_fixes, window_mapping
    - _Requirements: 6.5_

  - [x] 5.2 Implement state transition validation
    - Create valid transitions map per state machine
    - Implement validate_transition() function
    - Reject invalid transitions with error logging
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.8_

  - [x] 5.3 Write property tests for state transitions
    - **Property 4: State Transition Validity**
    - **Property 5: Invalid Transition Rejection**
    - **Property 13: Task Status Enum Validity**
    - **Property 14: Criticality Enum Validity**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8**

- [x] 6. Implement Spec Parser
  - [x] 6.1 Create spec_parser.py
    - Implement parse_tasks() to extract tasks from tasks.md
    - Implement validate_spec_directory() to check all files exist
    - Agent reads requirements.md and design.md directly when executing tasks
    - _Requirements: 1.2, 11.2, 11.3_

  - [x] 6.2 Write property tests for Spec Parser
    - **Property 1: Task Parsing Round-Trip Consistency**
    - **Validates: Requirements 1.2, 11.3, 11.4**

  - [x] 6.3 Implement task dependency extraction
    - Parse dependency markers from tasks.md
    - Build dependency graph
    - Detect circular dependencies
    - _Requirements: 11.3, 11.7_

- [x] 7. Checkpoint - Ensure spec parser tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Create Codex Orchestrator Skill
  - [x] 8.1 Create skill directory structure
    - Create skills/multi-agent-orchestrator/
    - Create SKILL.md with name, description, trigger conditions
    - Create scripts/ and references/ directories
    - _Requirements: 10.1, 10.3, 10.4_

  - [x] 8.2 Implement orchestrator initialization script
    - Create scripts/init_orchestration.py
    - Parse spec directory and validate files
    - Initialize AGENT_STATE.json with tasks from tasks.md
    - Initialize PROJECT_PULSE.md with mental model from design.md
    - _Requirements: 11.2, 11.4, 11.5, 11.6, 11.8_

  - [x] 8.3 Write property tests for initialization
    - **Property 2: Agent Assignment by Task Type**
    - **Property 3: Dependency-Based Blocking**
    - **Validates: Requirements 1.3, 1.7, 11.5**

  - [x] 8.4 Implement batch dispatch logic
    - Create scripts/dispatch_batch.py
    - Collect ready tasks (no unmet dependencies)
    - Build task config for codeagent-wrapper --parallel
    - Invoke codeagent-wrapper synchronously
    - Process Execution Report
    - _Requirements: 1.3, 1.4, 9.1, 9.3, 9.4, 9.10_

  - [x] 8.5 Implement review dispatch logic
    - Create scripts/dispatch_reviews.py
    - Identify tasks in pending_review status
    - Build review task config with codex backend
    - Invoke codeagent-wrapper for review batch
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 8.6 Write property tests for review dispatch
    - **Property 8: Review Count by Criticality**
    - **Property 9: Review Pane Placement**
    - **Validates: Requirements 8.2, 8.5, 8.6**

- [x] 9. Implement sync_pulse and dual-document management
  - [x] 9.1 Create scripts/sync_pulse.py
    - Read AGENT_STATE.json
    - Update PROJECT_PULSE.md Mental Model section
    - Update Narrative Delta with recent completions
    - Update Risks & Debt with blocked items and pending decisions
    - Escalate 24h+ pending decisions
    - _Requirements: 6.1, 6.3, 6.4, 6.6_
    - **Note: Reference implementation exists in skills/agent-pulse-coordination/scripts/sync_pulse.py**

  - [x] 9.2 Write property tests for sync_pulse
    - **Property 12: Dual Document Synchronization**
    - **Property 15: Blocked Task Has Blocked Item Entry**
    - **Validates: Requirements 6.3, 3.5, 9.6**

  - [x] 9.3 Implement review consolidation
    - Create scripts/consolidate_reviews.py
    - Collect all review findings for a task
    - Generate Final Report with overall severity
    - Update AGENT_STATE.json final_reports
    - _Requirements: 8.9_

  - [x] 9.4 Write property tests for review consolidation
    - **Property 10: Review Completion Triggers Consolidation**
    - **Validates: Requirements 8.9**

- [x] 10. Checkpoint - Ensure all skill scripts work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Create custom prompts for Codex
  - [x] 11.1 Create dispatch-task.md prompt
    - Define argument hints and description
    - Include step-by-step dispatch instructions
    - _Requirements: 10.2_

  - [x] 11.2 Create spawn-review.md prompt
    - Define argument hints for task_id
    - Include review spawn instructions
    - _Requirements: 10.2_

  - [x] 11.3 Create sync-pulse.md prompt
    - Define sync instructions
    - Include PULSE update steps
    - _Requirements: 10.2_

  - [x] 11.4 Create check-status.md prompt
    - Define status check instructions
    - Include state reading and reporting
    - _Requirements: 10.2_

- [x] 12. Integration testing
  - [x] 12.1 Create end-to-end test with sample spec
    - Create test spec directory with requirements.md, design.md, tasks.md
    - Test full orchestration flow
    - Verify AGENT_STATE.json and PROJECT_PULSE.md updates
    - _Requirements: All_

  - [x] 12.2 Test tmux session persistence
    - Verify session survives after codeagent-wrapper exits
    - Verify user can review task history in tmux
    - _Requirements: 12.9_

- [x] 13. Final checkpoint - Full system verification
  - Ensure all tests pass, ask the user if questions arise.
  - Verify codeagent-wrapper builds successfully
  - Verify skill installation works
  - Verify end-to-end orchestration flow

## Notes

- All tasks including property tests are required for comprehensive coverage
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Go code uses standard library only (no external dependencies)
- Python scripts use hypothesis for property-based testing
- Tasks 1-3 and 5 are largely complete based on existing codebase implementation
- Reference implementation for sync_pulse.py exists in skills/agent-pulse-coordination/scripts/
