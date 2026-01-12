import { useState, useMemo } from 'react';
import { Task, TaskStatus, AgentType } from '../types';

export const useTaskFilter = (tasks: Task[]) => {
    const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
    const [agentFilter, setAgentFilter] = useState<AgentType | 'all'>('all');
    const [searchQuery, setSearchQuery] = useState('');

    const filteredTasks = useMemo(() => {
        return tasks.filter(task => {
            const matchesStatus = statusFilter === 'all' || task.status === statusFilter;
            const matchesAgent = agentFilter === 'all' || task.agent === agentFilter;
            const matchesSearch = task.description.toLowerCase().includes(searchQuery.toLowerCase()) || 
                                  task.id.toLowerCase().includes(searchQuery.toLowerCase());
            
            return matchesStatus && matchesAgent && matchesSearch;
        });
    }, [tasks, statusFilter, agentFilter, searchQuery]);

    return {
        statusFilter,
        setStatusFilter,
        agentFilter,
        setAgentFilter,
        searchQuery,
        setSearchQuery,
        filteredTasks
    };
};
