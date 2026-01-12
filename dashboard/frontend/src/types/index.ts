export type TaskStatus = 'not_started' | 'in_progress' | 'pending_review' | 'completed' | 'blocked';
export type AgentType = 'kiro-cli' | 'gemini' | 'codex';

export interface AgentState {
  project_name: string;
  session_id: string;
  status: 'idle' | 'running' | 'paused' | 'error';
  // Add more as needed
}

export interface Task {
  id: string;
  description: string;
  status: TaskStatus;
  agent: AgentType;
  dependencies: string[];
}
