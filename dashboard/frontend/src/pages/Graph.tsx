import React from 'react';
import { useAgentState } from '../hooks/useAgentState';
import { DependencyGraph } from '../components/graph/DependencyGraph';
import { useNavigate } from 'react-router-dom';

export const Graph: React.FC = () => {
    const { state, isLoading, error } = useAgentState();
    const navigate = useNavigate();

    if (isLoading) return <div className="p-8 flex justify-center text-gray-500">Loading graph...</div>;
    if (error) return <div className="p-8 text-red-500 bg-red-50 rounded-lg m-4">Error: {error.message}</div>;
    if (!state) return <div className="p-8">No state available</div>;

    return (
        <div className="flex flex-col h-full">
            <h1 className="text-2xl font-bold text-gray-900 mb-4 px-1">Task Dependencies</h1>
            <div className="flex-1 min-h-[500px]"> 
                <DependencyGraph 
                    tasks={state.tasks} 
                    onTaskSelect={(taskId) => navigate(`/tasks?search=${taskId}`)}
                />
            </div>
        </div>
    );
};
