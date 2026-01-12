# Implementation Plan: Orchestration Dashboard

## Overview

This implementation plan breaks down the Orchestration Dashboard into incremental tasks. The dashboard consists of a React frontend and Python FastAPI backend. Tasks are organized to build foundational components first, then integrate them into complete views.

The implementation follows a backend-first approach for API endpoints, then frontend components, ensuring each layer can be tested independently before integration.

## Tasks

- [ ] 1 Set up project structure and dependencies
  - [ ] 1.1 Initialize frontend project with Vite + React + TypeScript
    - Create `dashboard/frontend/` directory
    - Initialize with `npm create vite@latest . -- --template react-ts`
    - Install dependencies: tailwindcss, react-query, zustand, react-router-dom, reactflow
    - Configure Tailwind CSS
    - _Requirements: 1.1, 1.2, 1.3_
    - _writes: dashboard/frontend/package.json, dashboard/frontend/vite.config.ts, dashboard/frontend/tailwind.config.js_

  - [ ] 1.2 Initialize backend project with FastAPI
    - Create `dashboard/backend/` directory
    - Create `requirements.txt` with fastapi, uvicorn, watchdog, pydantic, websockets
    - Create basic `main.py` with FastAPI app
    - _Requirements: 7.1, 7.5_
    - _writes: dashboard/backend/requirements.txt, dashboard/backend/main.py_

  - [ ] 1.3 Create shared TypeScript types from AGENT_STATE schema
    - Create `dashboard/frontend/src/types/index.ts`
    - Define Task, AgentState, ReviewFinding, and related interfaces
    - Match types to `agent-state-schema.json`
    - _Requirements: 2.2, 7.2_
    - _writes: dashboard/frontend/src/types/index.ts_

- [ ] 2 Implement backend API endpoints
  - [ ] 2.1 Implement state service and file operations
    - Create `dashboard/backend/services/state_service.py`
    - Implement `load_state()` function to read AGENT_STATE.json
    - Implement schema validation using jsonschema
    - Handle file not found and validation errors
    - _Requirements: 7.1, 7.6_
    - _writes: dashboard/backend/services/state_service.py, dashboard/backend/services/__init__.py_

  - [ ]* 2.2 Write property test for state validation (Property 13)
    - **Property 13: API State Validation**
    - **Validates: Requirements 7.6**
    - _writes: dashboard/backend/tests/test_state_service_property.py_

  - [ ] 2.3 Implement GET /api/state endpoint with full state data
    - Update `dashboard/backend/routers/state.py` to use state_service
    - Return full AGENT_STATE.json content
    - Return 500 with validation details on invalid state
    - _Requirements: 7.1, 7.6_
    - _writes: dashboard/backend/routers/state.py_

  - [ ] 2.4 Implement GET /api/tasks and GET /api/tasks/{id} endpoints with real data
    - Update `dashboard/backend/routers/tasks.py` to use state_service
    - GET /api/tasks returns all tasks array from state
    - GET /api/tasks/{id} returns single task or 404
    - _Requirements: 7.2, 7.3_
    - _writes: dashboard/backend/routers/tasks.py_

  - [ ]* 2.5 Write property tests for task endpoints (Properties 11, 12)
    - **Property 11: API Task Endpoint Consistency**
    - **Property 12: API Single Task Lookup**
    - **Validates: Requirements 7.2, 7.3**
    - _writes: dashboard/backend/tests/test_tasks_api_property.py_

  - [ ] 2.6 Implement GET /api/reviews endpoint with real data
    - Update `dashboard/backend/routers/reviews.py` to use state_service
    - Return all review_findings from state
    - _Requirements: 7.4_
    - _writes: dashboard/backend/routers/reviews.py_

  - [ ] 2.7 Implement WebSocket /ws/status endpoint
    - Create `dashboard/backend/websocket/handler.py`
    - Implement file watcher using watchdog
    - Broadcast state changes to connected clients
    - Register WebSocket route in main.py
    - _Requirements: 3.1, 3.2, 7.5_
    - _writes: dashboard/backend/websocket/handler.py, dashboard/backend/websocket/__init__.py, dashboard/backend/services/file_watcher.py_

- [ ] 3 Checkpoint - Backend API complete
  - Ensure all API tests pass
  - Verify endpoints work with sample AGENT_STATE.json
  - Ask the user if questions arise

  - [x] 4 Implement frontend layout components
    - [x] 4.1 Create Header component
      - Display project name and session identifier
      - Read session_name from state
      - _Requirements: 1.1_
      - _writes: dashboard/frontend/src/components/layout/Header.tsx_

    - [x] 4.2 Create Sidebar navigation component
      - Create dedicated Sidebar.tsx component (currently inline in App.tsx)
      - Navigation links: Overview, Tasks, Agents, Reviews, Graph
      - Use react-router-dom for client-side routing
      - Highlight active route
      - _Requirements: 1.2, 1.3_
      - _writes: dashboard/frontend/src/components/layout/Sidebar.tsx_

    - [x] 4.3 Create MainContent wrapper and App routing
      - Set up React Router with routes for each view
      - Implement responsive layout (1024px - 1920px)
      - Refactor App.tsx to use proper routing
      - _Requirements: 1.3, 1.4_
      - _writes: dashboard/frontend/src/components/layout/MainContent.tsx, dashboard/frontend/src/App.tsx_

    - [x] 4.4 Create common UI components
      - SkeletonLoader for loading states
      - ErrorMessage with retry button
      - Toast for notifications
      - Banner for status alerts
      - _Requirements: 8.1, 8.2, 8.3, 8.4_
      - _writes: dashboard/frontend/src/components/common/SkeletonLoader.tsx, dashboard/frontend/src/components/common/ErrorMessage.tsx, dashboard/frontend/src/components/common/Toast.tsx, dashboard/frontend/src/components/common/Banner.tsx_

    - [x]* 4.5 Write property test for error display (Property 14)
      - **Property 14: Error Display**
      - **Validates: Requirements 8.2**
      - _writes: dashboard/frontend/src/components/common/ErrorMessage.test.tsx_
- [ ] 5 Implement task display components
  - [ ] 5.1 Create TaskStatusBadge component
    - Color mapping: gray (not_started), blue (in_progress), yellow (pending_review), green (completed), red (blocked)
    - _Requirements: 2.4_
    - _writes: dashboard/frontend/src/components/tasks/TaskStatusBadge.tsx_

  - [ ]* 5.2 Write property test for status color mapping (Property 2)
    - **Property 2: Status Color Mapping Consistency**
    - **Validates: Requirements 2.4**
    - _writes: dashboard/frontend/src/components/tasks/TaskStatusBadge.test.tsx_

  - [ ] 5.3 Create ReviewBadge component
    - Color mapping: green (none/minor), yellow (major), red (critical)
    - Clickable to expand review details
    - _Requirements: 5.1, 5.2, 5.3_
    - _writes: dashboard/frontend/src/components/reviews/ReviewBadge.tsx_

  - [ ]* 5.4 Write property test for review severity colors (Property 3)
    - **Property 3: Review Severity Color Mapping**
    - **Validates: Requirements 5.2**
    - _writes: dashboard/frontend/src/components/reviews/ReviewBadge.test.tsx_

  - [ ] 5.5 Create FixLoopIndicator component
    - Display "Fix Attempt N/M" format
    - Show when fix_attempts > 0
    - _Requirements: 5.5_
    - _writes: dashboard/frontend/src/components/reviews/FixLoopIndicator.tsx_

  - [ ]* 5.6 Write property test for fix loop display (Property 9)
    - **Property 9: Fix Loop Display**
    - **Validates: Requirements 5.5**
    - _writes: dashboard/frontend/src/components/reviews/FixLoopIndicator.test.tsx_

  - [ ] 5.7 Create TaskCard component
    - Display task_id, description, status, owner_agent, dependencies
    - Expandable subtasks section
    - Show blocked_reason when blocked
    - Include ReviewBadge and FixLoopIndicator
    - Action Required indicator for human intervention
    - _Requirements: 2.2, 2.3, 2.5, 5.1, 5.5, 8.5_
    - _writes: dashboard/frontend/src/components/tasks/TaskCard.tsx_

  - [ ]* 5.8 Write property tests for TaskCard (Properties 1, 7, 8, 15)
    - **Property 1: Task Data Completeness**
    - **Property 7: Subtask Expansion**
    - **Property 8: Blocked Task Display**
    - **Property 15: Human Intervention Indicator**
    - **Validates: Requirements 2.2, 2.3, 2.5, 8.5**
    - _writes: dashboard/frontend/src/components/tasks/TaskCard.test.tsx_

- [ ] 6 Implement task list and filtering
  - [ ] 6.1 Create TaskFilter component
    - Filter by status dropdown
    - Filter by agent dropdown
    - Search input for text search
    - _Requirements: 2.6_
    - _writes: dashboard/frontend/src/components/tasks/TaskFilter.tsx_

  - [ ] 6.2 Create useTaskFilter hook
    - Implement filter logic for status, agent, search term
    - Return filtered task list
    - _Requirements: 2.6_
    - _writes: dashboard/frontend/src/hooks/useTaskFilter.ts_

  - [ ]* 6.3 Write property test for filter correctness (Property 5)
    - **Property 5: Filter Correctness**
    - **Validates: Requirements 2.6**
    - _writes: dashboard/frontend/src/hooks/useTaskFilter.test.ts_

  - [ ] 6.4 Create TaskList component
    - Scrollable list of TaskCards
    - Integrate TaskFilter
    - Show skeleton loaders while loading
    - _Requirements: 2.1, 8.1_
    - _writes: dashboard/frontend/src/components/tasks/TaskList.tsx_

  - [ ]* 6.5 Write property test for task list completeness (Property 4)
    - **Property 4: Task List Completeness**
    - **Validates: Requirements 2.1**
    - _writes: dashboard/frontend/src/components/tasks/TaskList.test.tsx_

- [ ] 7 Checkpoint - Task components complete
  - Ensure all task component tests pass
  - Verify TaskList renders correctly with sample data
  - Ask the user if questions arise

- [ ] 8 Implement agent status panel
  - [ ] 8.1 Create AgentIndicator component
    - Show working/idle state with animation
    - Display agent type icon
    - _Requirements: 4.2_
    - _writes: dashboard/frontend/src/components/agents/AgentIndicator.tsx_

  - [ ] 8.2 Create AgentPanel component
    - Display each agent type with task count
    - Show total tasks per status category
    - Tooltip with assigned task list on hover
    - _Requirements: 4.1, 4.3, 4.4_
    - _writes: dashboard/frontend/src/components/agents/AgentPanel.tsx_

  - [ ]* 8.3 Write property test for agent count accuracy (Property 6)
    - **Property 6: Agent Count Accuracy**
    - **Validates: Requirements 4.1, 4.3**
    - _writes: dashboard/frontend/src/components/agents/AgentPanel.test.tsx_

- [ ] 9 Implement dependency graph
  - [ ] 9.1 Create TaskNode component for React Flow
    - Custom node displaying task status and info
    - Click handler for navigation
    - _Requirements: 6.4_
    - _writes: dashboard/frontend/src/components/graph/TaskNode.tsx_

  - [ ] 9.2 Create DependencyGraph component
    - Use React Flow for graph rendering
    - Generate nodes from tasks, edges from dependencies
    - Highlight blocking paths in red
    - Support zoom and pan
    - _Requirements: 6.1, 6.2, 6.3_
    - _writes: dashboard/frontend/src/components/graph/DependencyGraph.tsx_

  - [ ]* 9.3 Write property test for graph completeness (Property 10)
    - **Property 10: Dependency Graph Completeness**
    - **Validates: Requirements 6.1**
    - _writes: dashboard/frontend/src/components/graph/DependencyGraph.test.tsx_

- [ ] 10 Implement real-time updates
  - [ ] 10.1 Create useWebSocket hook
    - Connect to /ws/status endpoint
    - Handle connection, disconnection, reconnection
    - Exponential backoff for reconnection
    - Fetch full state on reconnect
    - _Requirements: 3.1, 3.4, 3.5_
    - _writes: dashboard/frontend/src/hooks/useWebSocket.ts_

  - [ ] 10.2 Create useAgentState hook
    - Fetch initial state via React Query
    - Update state from WebSocket messages
    - Handle loading and error states
    - _Requirements: 3.2, 3.3_
    - _writes: dashboard/frontend/src/hooks/useAgentState.ts_

  - [ ] 10.3 Integrate real-time updates into components
    - TaskList updates on task_update messages
    - Toast notifications on review_complete
    - DependencyGraph updates on status changes
    - _Requirements: 3.2, 3.3, 6.5_
    - _writes: dashboard/frontend/src/App.tsx_

- [ ] 11 Implement view pages
  - [ ] 11.1 Create Overview page
    - Summary statistics
    - Recent activity
    - Quick status panel
    - _Requirements: 1.2_
    - _writes: dashboard/frontend/src/pages/Overview.tsx_

  - [ ] 11.2 Create Tasks page
    - Full TaskList with filters
    - _Requirements: 2.1, 2.6_
    - _writes: dashboard/frontend/src/pages/Tasks.tsx_

  - [ ] 11.3 Create Agents page
    - AgentPanel with detailed view
    - _Requirements: 4.1, 4.2, 4.3_
    - _writes: dashboard/frontend/src/pages/Agents.tsx_

  - [ ] 11.4 Create Reviews page
    - List of all review findings
    - Filter by severity
    - _Requirements: 5.1, 5.4_
    - _writes: dashboard/frontend/src/pages/Reviews.tsx_

  - [ ] 11.5 Create Graph page
    - Full-screen dependency graph
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
    - _writes: dashboard/frontend/src/pages/Graph.tsx_

- [ ] 12 Final integration and error handling
  - [x] 12.1 Implement session not found error page
    - Display when orchestration session not found
    - Provide retry option
    - _Requirements: 1.5_
    - _writes: dashboard/frontend/src/pages/NotFound.tsx_

  - [ ] 12.2 Add paused/suspended state banner
    - Show prominent banner when orchestration is paused
    - _Requirements: 8.4_
    - _writes: dashboard/frontend/src/components/common/StatusBanner.tsx_

  - [ ] 12.3 Create API client with error handling
    - Centralized API client
    - Consistent error handling
    - Retry logic
    - _Requirements: 8.2, 8.3_
    - _writes: dashboard/frontend/src/api/client.ts_

- [ ] 13 Final checkpoint - Full integration
  - Ensure all tests pass (frontend and backend)
  - Verify end-to-end functionality with real AGENT_STATE.json
  - Test WebSocket real-time updates
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Backend tasks should be completed before frontend integration tasks
- File manifest (_writes:) enables conflict detection for parallel execution

## Implementation Status Summary

**Completed:**
- Project structure and dependencies (frontend + backend)
- TypeScript types definition
- State service with validation
- Basic API router stubs
- Header, TaskStatusBadge, TaskFilter, AgentIndicator, TaskNode components
- useWebSocket hook with reconnection logic
- Zustand store setup
- Overview page with stats
- NotFound error page

**In Progress / Needs Completion:**
- Backend API endpoints need to use state_service (currently return placeholders)
- WebSocket endpoint and file watcher not implemented
- Sidebar needs to be extracted as separate component
- React Router integration incomplete
- Common UI components (SkeletonLoader, Toast, Banner) missing
- ReviewBadge, FixLoopIndicator, TaskCard components missing
- TaskList, AgentPanel, DependencyGraph components missing
- useTaskFilter, useAgentState hooks missing
- Tasks, Agents, Reviews, Graph pages missing
- API client with error handling missing
- Property tests not implemented

