import React, { useState } from 'react';
import { useAgentState } from '../hooks/useAgentState';
import { TaskCard } from '../components/tasks/TaskCard';
import { TaskFilter } from '../components/tasks/TaskFilter';
import { TaskStatus } from '../types';

export const Tasks: React.FC = () => {
  const { state, isLoading, error } = useAgentState();
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  if (isLoading) return <div className="p-8 flex justify-center text-gray-500">Loading tasks...</div>;
  if (error) return <div className="p-8 text-red-500 bg-red-50 rounded-lg m-4">Error loading tasks: {error.message}</div>;
  if (!state) return <div className="p-8 text-gray-500">No project state available.</div>;

  const filteredTasks = state.tasks.filter(task => {
    const matchesStatus = statusFilter === 'all' || task.status === statusFilter;
    const matchesSearch = task.description.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          task.task_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-end mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Tasks <span className="text-gray-400 text-lg font-normal ml-2">({filteredTasks.length})</span></h1>
      </div>

      <TaskFilter 
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
      />

      <div className="space-y-3">
        {filteredTasks.length > 0 ? (
            filteredTasks.map(task => (
                <TaskCard key={task.task_id} task={task} />
            ))
        ) : (
            <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 text-gray-500">
                No tasks found matching your filters.
            </div>
        )}
      </div>
    </div>
  );
};
