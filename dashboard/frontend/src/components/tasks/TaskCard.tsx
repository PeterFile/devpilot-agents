import React, { useState } from 'react';
import { Task } from '../../types';
import { TaskStatusBadge } from './TaskStatusBadge';
import { ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react';

interface TaskCardProps {
  task: Task;
  onExpand?: (taskId: string) => void;
  onNavigate?: (taskId: string) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, onExpand, onNavigate }) => {
  const [expanded, setExpanded] = useState(false);

  const toggleExpand = () => {
    const newExpanded = !expanded;
    setExpanded(newExpanded);
    if (newExpanded && onExpand) {
      onExpand(task.task_id);
    }
  };

  const hasSubtasks = task.subtasks && task.subtasks.length > 0;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 mb-3 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3">
        {hasSubtasks && (
          <button
            onClick={toggleExpand}
            className="ml-4 text-gray-400 hover:text-gray-600 focus:outline-none"
            aria-label={expanded ? "Collapse subtasks" : "Expand subtasks"}
          >
            {task.subtasks && task.subtasks.length > 0 ? (
                expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />
            ) : <div className="w-[18px]" />}
          </button>
          
          <div>
            <div className="flex items-center space-x-2">
                <span className="font-mono text-xs text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
                    {task.task_id}
                </span>
                <h3 className="font-medium text-gray-900">{task.description}</h3>
            </div>
            
            <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
                <span>Type: <span className="capitalize">{task.type}</span></span>
                {task.owner_agent && <span>Agent: {task.owner_agent}</span>}
                {task.fix_attempts > 0 && (
                    <span className="text-orange-600 font-medium">
                        Fix Attempt {task.fix_attempts}/{task.max_fix_attempts}
                    </span>
                )}
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end space-y-2">
            <TaskStatusBadge status={task.status} />
            {task.status === 'blocked' && (
                <div className="flex items-center text-red-600 text-xs font-medium">
                    <AlertTriangle size={14} className="mr-1" />
                    Blocked
                </div>
            )}
        </div>
      </div>

      {expanded && task.subtasks && (
          <div className="mt-4 pl-10 pr-2 pb-2">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Subtasks</h4>
              <div className="space-y-2">
                  {task.subtasks.map(subId => (
                      <div key={subId} className="flex items-center text-sm text-gray-600 bg-gray-50 p-2 rounded">
                          <span className="font-mono text-xs mr-2">{subId}</span>
                      </div>
                  ))}
              </div>
          </div>
      )}

      {task.blocked_reason && (
          <div className="mt-3 bg-red-50 border border-red-100 rounded p-3 text-sm text-red-700 ml-10">
              <span className="font-bold">Blocked:</span> {task.blocked_reason}
          </div>
      )}
    </div>
  );
};