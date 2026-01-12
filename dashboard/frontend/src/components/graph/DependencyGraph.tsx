import React, { useEffect, useMemo } from 'react';
import ReactFlow, { 
    Background, 
    Controls, 
    Edge, 
    Node, 
    useNodesState, 
    useEdgesState, 
    MarkerType 
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Task } from '../../types';
import { TaskNode } from './TaskNode';

interface DependencyGraphProps {
    tasks: Task[];
    onTaskSelect: (taskId: string) => void;
}

const nodeTypes = {
    taskNode: TaskNode,
};

export const DependencyGraph: React.FC<DependencyGraphProps> = ({ tasks, onTaskSelect }) => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        if (!tasks.length) return;

        // Simple level-based layout
        const levels: Record<string, number> = {};
        const getLevel = (id: string, visited = new Set<string>()): number => {
            if (visited.has(id)) return 0; // Cycle
            if (levels[id] !== undefined) return levels[id];
            visited.add(id);
            
            const task = tasks.find(t => t.task_id === id);
            if (!task || !task.dependencies.length) {
                levels[id] = 0;
                return 0;
            }
            
            const maxParentLevel = Math.max(...task.dependencies.map(d => getLevel(d, new Set(visited))));
            levels[id] = maxParentLevel + 1;
            return maxParentLevel + 1;
        };
        
        tasks.forEach(t => getLevel(t.task_id));
        
        const nodesByLevel: Record<number, Task[]> = {};
        tasks.forEach(t => {
            const lvl = levels[t.task_id] || 0;
            if (!nodesByLevel[lvl]) nodesByLevel[lvl] = [];
            nodesByLevel[lvl].push(t);
        });

        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];

        Object.entries(nodesByLevel).forEach(([levelStr, levelTasks]) => {
            const level = parseInt(levelStr);
            levelTasks.forEach((task, index) => {
                newNodes.push({
                    id: task.task_id,
                    type: 'taskNode',
                    position: { x: index * 250, y: level * 200 },
                    data: { task, onNodeClick: onTaskSelect },
                });

                task.dependencies.forEach(depId => {
                    newEdges.push({
                        id: `${depId}-${task.task_id}`,
                        source: depId,
                        target: task.task_id,
                        markerEnd: { type: MarkerType.ArrowClosed },
                        type: 'smoothstep',
                        animated: task.status === 'in_progress'
                    });
                });
            });
        });

        setNodes(newNodes);
        setEdges(newEdges);
    }, [tasks, setNodes, setEdges, onTaskSelect]);

    return (
        <div className="h-full w-full bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
            >
                <Background />
                <Controls />
            </ReactFlow>
        </div>
    );
};
