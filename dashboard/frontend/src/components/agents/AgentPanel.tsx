import React from 'react';
import { Task } from '../../types';
import { TaskStatusBadge } from '../tasks/TaskStatusBadge';
import { Bot, Terminal, Cpu } from 'lucide-react';

interface AgentPanelProps {
    tasks: Task[];
}

export const AgentPanel: React.FC<AgentPanelProps> = ({ tasks }) => {
    const agents = ['kiro-cli', 'gemini', 'codex'];

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {agents.map(agent => (
                <AgentCard key={agent} agentName={agent} tasks={tasks.filter(t => t.owner_agent === agent)} />
            ))}
        </div>
    );
};

const AgentCard = ({ agentName, tasks }: { agentName: string, tasks: Task[] }) => {
    const inProgressCount = tasks.filter(t => t.status === 'in_progress').length;
    
    let Icon = Bot;
    if (agentName === 'kiro-cli') Icon = Terminal;
    if (agentName === 'codex') Icon = Cpu;

    return (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
                <div className="flex items-center space-x-2">
                    <Icon size={20} className="text-gray-600" />
                    <h3 className="font-semibold text-gray-900 capitalize">{agentName}</h3>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${inProgressCount > 0 ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'}`}>
                    {inProgressCount > 0 ? 'Active' : 'Idle'}
                </span>
            </div>
            
            <div className="p-4">
                <div className="flex justify-between text-sm text-gray-600 mb-4">
                    <span>Total Tasks:</span>
                    <span className="font-medium">{tasks.length}</span>
                </div>
                
                <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Current Activity</h4>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                    {tasks.filter(t => t.status === 'in_progress' || t.status === 'pending_review').map(task => (
                        <div key={task.task_id} className="text-sm p-2 bg-gray-50 rounded border border-gray-100">
                            <div className="flex justify-between items-start mb-1">
                                <span className="font-mono text-xs text-gray-500">{task.task_id}</span>
                                <TaskStatusBadge status={task.status} />
                            </div>
                            <p className="line-clamp-2 text-gray-800">{task.description}</p>
                        </div>
                    ))}
                    {tasks.filter(t => t.status === 'in_progress' || t.status === 'pending_review').length === 0 && (
                        <p className="text-sm text-gray-400 italic text-center py-4">No active tasks</p>
                    )}
                </div>
            </div>
        </div>
    );
};
