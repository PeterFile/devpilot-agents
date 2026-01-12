import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Task } from '../../types';
import { TaskStatusBadge } from '../tasks/TaskStatusBadge';

interface TaskNodeData {
  task: Task;
  onNodeClick: (taskId: string) => void;
}

export const TaskNode: React.FC<NodeProps<TaskNodeData>> = memo(({ data }) => {
  return (
    <div className="bg-white rounded-md border border-gray-200 shadow-sm p-3 min-w-[200px]"
         onClick={() => data.onNodeClick(data.task.task_id)}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      
      <div className="flex flex-col space-y-2">
        <div className="flex justify-between items-center">
            <span className="font-mono text-xs text-gray-500 bg-gray-50 px-1 rounded">{data.task.task_id}</span>
            <div className={`w-2 h-2 rounded-full ${data.task.status === 'blocked' ? 'bg-red-500' : 'bg-green-500'}`} />
        </div>
        
        <div className="text-sm font-medium text-gray-900 line-clamp-2">
            {data.task.description}
        </div>
        
        <TaskStatusBadge status={data.task.status} />
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
    </div>
  );
});
