import React from 'react';
import { Activity, Terminal } from 'lucide-react';
import { useOrchestration } from '../../hooks/useOrchestration';

export const Header: React.FC = () => {
  const { state } = useOrchestration();

  return (
    <header className="h-16 border-b border-gray-800 bg-gray-950 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-500/10 rounded-lg">
          <Terminal className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-gray-100 tracking-wide">
            {state.project_name}
          </h1>
          <p className="text-xs text-gray-500 font-mono">
            ID: {state.session_id}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-900 border border-gray-800">
          <Activity className="w-3.5 h-3.5 text-green-400" />
          <span className="text-xs font-medium text-gray-300 uppercase tracking-wider">
            {state.status}
          </span>
        </div>
      </div>
    </header>
  );
};
