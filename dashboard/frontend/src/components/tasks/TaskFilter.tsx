import React from 'react';
import { TaskStatus, AgentType } from '../../types';
import { Search, Filter, User } from 'lucide-react';

interface TaskFilterProps {
    statusFilter: TaskStatus | 'all';
    setStatusFilter: (status: TaskStatus | 'all') => void;
    agentFilter: AgentType | 'all';
    setAgentFilter: (agent: AgentType | 'all') => void;
    searchQuery: string;
    setSearchQuery: (query: string) => void;
}

export const TaskFilter: React.FC<TaskFilterProps> = ({ 
    statusFilter, 
    setStatusFilter,
    agentFilter,
    setAgentFilter,
    searchQuery, 
    setSearchQuery 
}) => {
    return (
        <div className="flex flex-col md:flex-row gap-4 mb-6 bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
            <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <input
                    type="text"
                    placeholder="Search tasks..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
            </div>
            
            <div className="w-full md:w-48 relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as TaskStatus | 'all')}
                    className="w-full pl-10 pr-8 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none bg-white"
                >
                    <option value="all">All Statuses</option>
                    <option value="not_started">Not Started</option>
                    <option value="in_progress">In Progress</option>
                    <option value="pending_review">Pending Review</option>
                    <option value="blocked">Blocked</option>
                    <option value="completed">Completed</option>
                </select>
            </div>

            <div className="w-full md:w-48 relative">
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <select
                    value={agentFilter}
                    onChange={(e) => setAgentFilter(e.target.value as AgentType | 'all')}
                    className="w-full pl-10 pr-8 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none bg-white"
                >
                    <option value="all">All Agents</option>
                    <option value="kiro-cli">Kiro CLI</option>
                    <option value="gemini">Gemini</option>
                    <option value="codex">Codex</option>
                </select>
            </div>
        </div>
    );
};