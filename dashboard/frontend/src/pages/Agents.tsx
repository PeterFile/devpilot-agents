import React from 'react';
import { useAgentState } from '../hooks/useAgentState';
import { AgentPanel } from '../components/agents/AgentPanel';

export const Agents: React.FC = () => {
    const { state, isLoading, error } = useAgentState();

    if (isLoading) return <div className="p-8 flex justify-center text-gray-500">Loading agents...</div>;
    if (error) return <div className="p-8 text-red-500 bg-red-50 rounded-lg m-4">Error loading state: {error.message}</div>;
    if (!state) return <div className="p-8 text-gray-500">No project state available.</div>;

    return (
        <div className="max-w-6xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">Agents & Workload</h1>
            <AgentPanel tasks={state.tasks} />
        </div>
    );
};
