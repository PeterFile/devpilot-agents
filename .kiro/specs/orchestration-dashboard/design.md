# Design Document: Orchestration Dashboard

## Overview

The Orchestration Dashboard is a web-based monitoring interface for the multi-agent orchestration system. It provides real-time visibility into task execution, agent assignments, and review workflows. The dashboard is built as a React single-page application with a Python FastAPI backend that reads from AGENT_STATE.json and provides WebSocket updates.

This design supports the multi-agent orchestration workflow by:
- Providing visual feedback on task progress across kiro-cli, Gemini, and Codex agents
- Displaying review results and fix loop status
- Showing task dependencies and blocking relationships
- Enabling basic orchestration monitoring without command-line interaction

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Orchestration Dashboard                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   Frontend   │    │   Backend    │    │   Data Sources       │  │
│  │   (React)    │◄──►│  (FastAPI)   │◄──►│                      │  │
│  │              │    │              │    │  AGENT_STATE.json    │  │
│  │  - TaskList  │    │  REST API    │    │  PROJECT_PULSE.md    │  │
│  │  - Graph     │    │  WebSocket   │    │                      │  │
│  │  - Panels    │    │  File Watch  │    └──────────────────────┘  │
│  └──────────────┘    └──────────────┘                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS
- **State Management**: React Query for server state, Zustand for UI state
- **Graph Visualization**: React Flow
- **Backend**: Python FastAPI
- **Real-time**: WebSocket with watchdog file monitoring
- **Testing**: Vitest + React Testing Library (frontend), pytest + hypothesis (backend)

## Components and Interfaces

### Frontend Components

```
src/
├── components/
│   ├── layout/
│   │   ├── Header.tsx           # Project name, session ID
│   │   ├── Sidebar.tsx          # Navigation links
│   │   └── MainContent.tsx      # Content area wrapper
│   ├── tasks/
│   │   ├── TaskList.tsx         # Scrollable task list
│   │   ├── TaskCard.tsx         # Individual task display
│   │   ├── TaskFilter.tsx       # Filter controls
│   │   └── TaskStatusBadge.tsx  # Status color indicator
│   ├── agents/
│   │   ├── AgentPanel.tsx       # Agent status summary
│   │   └── AgentIndicator.tsx   # Working/idle indicator
│   ├── reviews/
│   │   ├── ReviewBadge.tsx      # Severity badge
│   │   ├── ReviewDetails.tsx    # Expanded findings
│   │   └── FixLoopIndicator.tsx # Attempt counter
│   ├── graph/
│   │   ├── DependencyGraph.tsx  # React Flow graph
│   │   └── TaskNode.tsx         # Custom node component
│   └── common/
│       ├── SkeletonLoader.tsx   # Loading placeholder
│       ├── ErrorMessage.tsx     # Error display with retry
│       ├── Toast.tsx            # Notification toast
│       └── Banner.tsx           # Status banner
├── hooks/
│   ├── useWebSocket.ts          # WebSocket connection
│   ├── useAgentState.ts         # State fetching
│   └── useTaskFilter.ts         # Filter logic
├── api/
│   └── client.ts                # API client
├── types/
│   └── index.ts                 # TypeScript types
└── App.tsx                      # Main app with routing
```

### Backend API Structure

```
backend/
├── main.py                      # FastAPI app entry
├── routers/
│   ├── state.py                 # GET /api/state
│   ├── tasks.py                 # GET /api/tasks, /api/tasks/{id}
│   └── reviews.py               # GET /api/reviews
├── websocket/
│   └── handler.py               # WebSocket /ws/status
├── services/
│   ├── state_service.py         # State file operations
│   └── file_watcher.py          # File change detection
└── models/
    └── schemas.py               # Pydantic models
```

### Component Interfaces

```typescript
// TaskCard Props
interface TaskCardProps {
  task: Task;
  onExpand?: (taskId: string) => void;
  onNavigate?: (taskId: string) => void;
}

// Task Type (matches AGENT_STATE schema)
interface Task {
  task_id: string;
  description: string;
  type: 'code' | 'ui' | 'review';
  status: TaskStatus;
  owner_agent?: string;
  dependencies: string[];
  subtasks: string[];
  parent_id?: string;
  fix_attempts: number;
  max_fix_attempts: number;
  escalated: boolean;
  last_review_severity?: Severity;
  review_history: ReviewHistoryEntry[];
  blocked_reason?: string;
  blocked_by?: string;
}

type TaskStatus = 
  | 'not_started' 
  | 'in_progress' 
  | 'pending_review' 
  | 'under_review'
  | 'fix_required'
  | 'final_review'
  | 'completed' 
  | 'blocked';

type Severity = 'critical' | 'major' | 'minor' | 'none';

// WebSocket Message
interface StatusUpdate {
  type: 'task_update' | 'review_complete' | 'state_sync';
  payload: Task | ReviewFinding | AgentState;
  timestamp: string;
}
```

## Data Models

### AgentState (from AGENT_STATE.json)

The dashboard reads the existing `AGENT_STATE.json` schema defined in `multi-agent-orchestration/skill/references/agent-state-schema.json`. Key fields used:

```typescript
interface AgentState {
  spec_path: string;
  session_name: string;
  tasks: Task[];
  review_findings: ReviewFinding[];
  final_reports: FinalReport[];
  blocked_items: BlockedItem[];
  pending_decisions: PendingDecision[];
  window_mapping: Record<string, string>;
}
```

### Derived View Models

```typescript
// Agent workload summary
interface AgentSummary {
  agent: 'kiro-cli' | 'gemini' | 'codex';
  taskCount: number;
  inProgressCount: number;
  assignedTasks: string[];
}

// Status counts for panel
interface StatusCounts {
  not_started: number;
  in_progress: number;
  pending_review: number;
  completed: number;
  blocked: number;
}

// Graph node data
interface GraphNode {
  id: string;
  data: {
    task: Task;
    isBlocked: boolean;
    blockingPath: string[];
  };
  position: { x: number; y: number };
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Task Data Completeness

*For any* task from AGENT_STATE.json, when rendered as a TaskCard, the displayed content SHALL include task_id, description, status, owner_agent (if assigned), and dependencies list.

**Validates: Requirements 2.2**

### Property 2: Status Color Mapping Consistency

*For any* task status value, the TaskStatusBadge SHALL apply the correct color class: gray for not_started, blue for in_progress, yellow for pending_review/under_review/fix_required, green for completed/final_review, red for blocked.

**Validates: Requirements 2.4**

### Property 3: Review Severity Color Mapping

*For any* review severity value, the ReviewBadge SHALL apply the correct color: green for none/minor, yellow for major, red for critical.

**Validates: Requirements 5.2**

### Property 4: Task List Completeness

*For any* valid AgentState, the TaskList component SHALL render exactly one TaskCard for each task in state.tasks, with no duplicates and no missing tasks.

**Validates: Requirements 2.1**

### Property 5: Filter Correctness

*For any* filter criteria (status, agent, or search term) applied to a task list, the filtered results SHALL contain only tasks matching ALL active filter criteria, and SHALL contain ALL tasks that match.

**Validates: Requirements 2.6**

### Property 6: Agent Count Accuracy

*For any* valid AgentState, the AgentPanel SHALL display task counts per agent that exactly match the count of tasks with that owner_agent value in state.tasks.

**Validates: Requirements 4.1, 4.3**

### Property 7: Subtask Expansion

*For any* task with non-empty subtasks array, the TaskCard SHALL render an expandable section, and when expanded, SHALL display all subtask IDs.

**Validates: Requirements 2.3**

### Property 8: Blocked Task Display

*For any* task with status='blocked', the TaskCard SHALL display the blocked_reason if present.

**Validates: Requirements 2.5**

### Property 9: Fix Loop Display

*For any* task with fix_attempts > 0, the TaskCard SHALL display the current attempt number in format "Fix Attempt N/M" where N=fix_attempts and M=max_fix_attempts.

**Validates: Requirements 5.5**

### Property 10: Dependency Graph Completeness

*For any* valid AgentState, the DependencyGraph SHALL render one node for each task and one edge for each dependency relationship, with no missing or duplicate elements.

**Validates: Requirements 6.1**

### Property 11: API Task Endpoint Consistency

*For any* valid AGENT_STATE.json, GET /api/tasks SHALL return a JSON array where each element corresponds to a task in the file, preserving all fields.

**Validates: Requirements 7.2**

### Property 12: API Single Task Lookup

*For any* task_id that exists in AGENT_STATE.json, GET /api/tasks/{id} SHALL return that task's complete data. For any task_id that does not exist, it SHALL return 404.

**Validates: Requirements 7.3**

### Property 13: API State Validation

*For any* AGENT_STATE.json that fails schema validation, GET /api/state SHALL return HTTP 500 with error details describing the validation failure.

**Validates: Requirements 7.6**

### Property 14: Error Display

*For any* API error response, the ErrorMessage component SHALL display the error message from the response and render a clickable Retry button.

**Validates: Requirements 8.2**

### Property 15: Human Intervention Indicator

*For any* task where blocked_reason contains "human_intervention" or where a pending_decision exists with that task_id, the TaskCard SHALL display an "Action Required" indicator.

**Validates: Requirements 8.5**

## Error Handling

### Frontend Error Handling

| Error Type | Handling Strategy |
|------------|-------------------|
| API 404 (session not found) | Display error page with session selector |
| API 500 (server error) | Display error message with retry button |
| API timeout | Display timeout message, auto-retry after 5s |
| WebSocket disconnect | Show reconnection indicator, exponential backoff retry |
| Invalid state data | Log error, display partial data with warning |

### Backend Error Handling

| Error Type | Response |
|------------|----------|
| AGENT_STATE.json not found | 404 with helpful message |
| AGENT_STATE.json invalid JSON | 500 with parse error details |
| AGENT_STATE.json schema invalid | 500 with validation errors |
| File read permission error | 500 with permission error |

### WebSocket Error Recovery

```typescript
// Reconnection strategy
const reconnectStrategy = {
  maxAttempts: 10,
  baseDelay: 1000,      // 1 second
  maxDelay: 30000,      // 30 seconds
  backoffMultiplier: 2,
  onReconnect: () => fetchFullState()  // Sync state after reconnect
};
```

## Testing Strategy

### Unit Tests

Unit tests verify specific component behaviors and edge cases:

- **TaskCard**: Renders all required fields, handles missing optional fields
- **TaskStatusBadge**: Correct color for each status value
- **ReviewBadge**: Correct color for each severity
- **TaskFilter**: Filter logic correctness
- **API endpoints**: Response format, error handling

### Property-Based Tests

Property-based tests verify universal properties across generated inputs using Hypothesis (Python) and fast-check (TypeScript):

**Frontend (fast-check)**:
- Task data completeness (Property 1)
- Status color mapping (Property 2)
- Review severity colors (Property 3)
- Filter correctness (Property 5)
- Subtask expansion (Property 7)

**Backend (hypothesis)**:
- API task endpoint consistency (Property 11)
- API single task lookup (Property 12)
- API state validation (Property 13)

### Test Configuration

- **Minimum iterations**: 100 per property test
- **Frontend framework**: Vitest + @testing-library/react + fast-check
- **Backend framework**: pytest + hypothesis
- **Tag format**: `Feature: orchestration-dashboard, Property N: {property_text}`

### Integration Tests

- WebSocket connection and message handling
- Full page render with mock state
- Navigation between views
- Real-time update propagation
