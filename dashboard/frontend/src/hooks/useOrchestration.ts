import { useState, useEffect } from 'react';
import { AgentState } from '../types';

export const useOrchestration = () => {
  const [state, setState] = useState<AgentState>({
    project_name: "Coding Agent Flow",
    session_id: "sess_" + Math.random().toString(36).substr(2, 9),
    status: 'running'
  });

  return { state };
};
