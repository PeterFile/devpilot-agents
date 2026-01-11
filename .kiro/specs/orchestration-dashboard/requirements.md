# Requirements Document

## Introduction

This document defines the requirements for an Orchestration Dashboard - a web-based interface that provides real-time visibility into the multi-agent orchestration system. The dashboard will display task execution status, agent assignments, review results, and allow basic orchestration control operations.

The dashboard serves as a practical test case for the multi-agent-orchestration system, involving multiple parallel tasks across frontend (UI components), backend (API endpoints), and integration work.

## Glossary

- **Dashboard**: The web-based user interface for monitoring orchestration status
- **Task_Card**: A UI component displaying individual task information including status, agent, and progress
- **Status_Panel**: A summary panel showing overall orchestration health and statistics
- **Agent_Indicator**: Visual indicator showing which agent (kiro-cli, Gemini, Codex) is assigned to a task
- **Review_Badge**: Visual badge showing review status and severity
- **WebSocket_Connection**: Real-time connection for live status updates
- **API_Server**: Backend service providing orchestration data via REST endpoints

## Requirements

### Requirement 1: Dashboard Layout and Navigation

**User Story:** As a developer, I want a clean dashboard layout with clear navigation, so that I can quickly access different views of the orchestration status.

#### Acceptance Criteria

1. WHEN the dashboard loads, THE Dashboard SHALL display a header with the project name and current session identifier
2. THE Dashboard SHALL provide a sidebar navigation with links to: Overview, Tasks, Agents, Reviews, and Settings
3. WHEN a navigation item is clicked, THE Dashboard SHALL update the main content area without full page reload
4. THE Dashboard SHALL be responsive and usable on screens from 1024px to 1920px width
5. WHEN the orchestration session is not found, THE Dashboard SHALL display a clear error message with retry option

### Requirement 2: Task List View

**User Story:** As a developer, I want to see all tasks in a list view with their current status, so that I can track overall progress.

#### Acceptance Criteria

1. WHEN the Tasks view is active, THE Dashboard SHALL display all tasks from AGENT_STATE.json in a scrollable list
2. THE Task_Card SHALL display: task ID, description, current status, assigned agent, and dependencies
3. WHEN a task has subtasks, THE Task_Card SHALL show an expandable section to view subtasks
4. THE Dashboard SHALL color-code task status: gray (not_started), blue (in_progress), yellow (pending_review), green (completed), red (blocked)
5. WHEN a task is blocked, THE Task_Card SHALL display the blocking reason
6. THE Dashboard SHALL allow filtering tasks by status, agent, or search term

### Requirement 3: Real-time Status Updates

**User Story:** As a developer, I want to see task status changes in real-time, so that I don't need to manually refresh the page.

#### Acceptance Criteria

1. WHEN the dashboard connects, THE WebSocket_Connection SHALL establish a connection to the status update endpoint
2. WHEN a task status changes in AGENT_STATE.json, THE Dashboard SHALL update the corresponding Task_Card within 2 seconds
3. WHEN a new review is completed, THE Dashboard SHALL display a notification toast with the review summary
4. IF the WebSocket_Connection is lost, THEN THE Dashboard SHALL display a reconnection indicator and attempt to reconnect
5. WHEN reconnection succeeds, THE Dashboard SHALL fetch the full state to ensure consistency

### Requirement 4: Agent Status Panel

**User Story:** As a developer, I want to see which agents are currently active and their workload, so that I can understand resource utilization.

#### Acceptance Criteria

1. THE Status_Panel SHALL display each agent type (kiro-cli, Gemini, Codex) with their current task count
2. WHEN an agent is executing a task, THE Agent_Indicator SHALL show an animated "working" state
3. THE Status_Panel SHALL show the total number of tasks in each status category
4. WHEN hovering over an agent, THE Dashboard SHALL display a tooltip with the list of assigned tasks

### Requirement 5: Review Results Display

**User Story:** As a developer, I want to see review results for completed tasks, so that I can understand code quality and required fixes.

#### Acceptance Criteria

1. WHEN a task has review results, THE Task_Card SHALL display a Review_Badge with severity level
2. THE Review_Badge SHALL use colors: green (none/minor), yellow (major), red (critical)
3. WHEN clicking on a Review_Badge, THE Dashboard SHALL expand to show full review findings
4. THE review findings display SHALL include: severity, summary, details, and reviewer agent
5. WHEN a task is in fix loop, THE Dashboard SHALL display the current attempt number (e.g., "Fix Attempt 2/3")

### Requirement 6: Task Dependency Visualization

**User Story:** As a developer, I want to see task dependencies visually, so that I can understand the execution order and blockers.

#### Acceptance Criteria

1. THE Dashboard SHALL provide a dependency graph view showing tasks as nodes and dependencies as edges
2. WHEN a task is blocked, THE dependency graph SHALL highlight the blocking path in red
3. THE dependency graph SHALL support zoom and pan interactions
4. WHEN clicking a node in the graph, THE Dashboard SHALL navigate to that task's detail view
5. THE dependency graph SHALL update in real-time as task statuses change

### Requirement 7: Backend API Endpoints

**User Story:** As a frontend developer, I want well-defined API endpoints, so that I can fetch and display orchestration data.

#### Acceptance Criteria

1. THE API_Server SHALL provide GET /api/state endpoint returning the current AGENT_STATE.json content
2. THE API_Server SHALL provide GET /api/tasks endpoint returning a list of all tasks with their details
3. THE API_Server SHALL provide GET /api/tasks/{id} endpoint returning details for a specific task
4. THE API_Server SHALL provide GET /api/reviews endpoint returning all review results
5. THE API_Server SHALL provide WebSocket endpoint /ws/status for real-time updates
6. WHEN AGENT_STATE.json is invalid, THE API_Server SHALL return a 500 error with validation details

### Requirement 8: Error Handling and Loading States

**User Story:** As a developer, I want clear feedback during loading and errors, so that I understand the system state.

#### Acceptance Criteria

1. WHEN data is loading, THE Dashboard SHALL display skeleton loaders in place of content
2. WHEN an API request fails, THE Dashboard SHALL display an error message with the failure reason
3. THE Dashboard SHALL provide a "Retry" button for failed requests
4. WHEN the orchestration is paused or suspended, THE Dashboard SHALL display a prominent banner indicating the state
5. IF a task requires human intervention, THEN THE Dashboard SHALL highlight it with a special "Action Required" indicator
