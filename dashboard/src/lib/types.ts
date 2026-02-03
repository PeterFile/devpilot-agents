// Event types and interfaces for the dashboard

export interface EventSource {
  session: string;
  window: string;
  pane: string;
  command?: string;
}

export type EventType = 
  | 'message' 
  | 'tool_call' 
  | 'tool_result' 
  | 'error' 
  | 'status' 
  | 'test_result' 
  | 'file_change' 
  | 'command';

export interface RawEvent {
  id: string;
  timestamp: number;
  source: EventSource;
  event_type: EventType;
  content: string;
  raw?: string;
}

export interface NormalizedEvent {
  id: string;
  timestamp: number;
  source: EventSource;
  type: EventType;
  title: string;
  content: string;
  markdown: string;
  meta: EventMeta;
}

export interface EventMeta {
  filesModified?: string[];
  commandsRun?: string[];
  testResults?: { passed: number; failed: number };
  errors?: string[];
}

export interface AggregatedStats {
  totalEvents: number;
  filesModified: string[];
  commandsRun: string[];
  testsRun: { passed: number; failed: number };
  errors: string[];
}

export interface WindowInfo {
  id: string;
  name: string;
  isActive: boolean;
  panes: PaneInfo[];
}

export interface PaneInfo {
  id: string;
  command: string;
  status: 'active' | 'busy' | 'idle' | 'error';
  eventCount: number;
}

export interface SessionState {
  name: string;
  windows: WindowInfo[];
  connected: boolean;
}
