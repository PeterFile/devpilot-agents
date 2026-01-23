import { useCallback, useState, useRef } from 'react';
import type { Node, Edge, NodeChange, EdgeChange, Connection } from '@xyflow/react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
  MarkerType,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  Handle,
  Position,
  reconnectEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './App.css';

const nodeWidth = 200;
const nodeHeight = 60;

type Phase = 'setup' | 'assign' | 'loop' | 'decision' | 'done';

const phaseColors: Record<Phase, { bg: string; border: string }> = {
  setup: { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6' },
  assign: { bg: 'rgba(168, 85, 247, 0.15)', border: '#a855f7' },
  loop: { bg: 'rgba(34, 197, 94, 0.15)', border: '#22c55e' },
  decision: { bg: 'rgba(251, 191, 36, 0.15)', border: '#fbbf24' },
  done: { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981' },
};

const allSteps: { id: string; label: string; description: string; phase: Phase }[] = [
  // Setup phase
  { id: '1', label: 'Parse Spec Directory', description: 'init_orchestration.py reads spec', phase: 'setup' },
  { id: '2', label: 'Generate TASKS_PARSED.json', description: 'Break down into dispatch units', phase: 'setup' },
  { id: '3', label: 'Create AGENT_STATE.json', description: 'Scaffold state structure', phase: 'setup' },
  // Assignment phase
  { id: '4', label: 'AI Decision Phase', description: 'Fill owner_agent, target_window', phase: 'assign' },
  { id: '5', label: 'Generate PROJECT_PULSE.md', description: 'Track progress overview', phase: 'assign' },
  // Execution loop
  { id: '6', label: 'dispatch_batch.py', description: 'Send tasks to Codex/Gemini', phase: 'loop' },
  { id: '7', label: 'Parallel Execution', description: 'Tasks run in tmux windows', phase: 'loop' },
  { id: '8', label: 'dispatch_reviews.py', description: 'Trigger code reviews', phase: 'loop' },
  { id: '9', label: 'consolidate_reviews.py', description: 'Collect review results', phase: 'loop' },
  { id: '10', label: 'sync_pulse.py', description: 'Update state & pulse', phase: 'loop' },
  // Decision
  { id: '11', label: 'All tasks complete?', description: '', phase: 'decision' },
  // Exit
  { id: '12', label: 'Done!', description: 'All dispatch units completed', phase: 'done' },
];

const notes = [
  {
    id: 'note-1',
    appearsWithStep: 3,
    position: { x: 420, y: 80 },
    color: { bg: 'rgba(59, 130, 246, 0.1)', border: 'rgba(59, 130, 246, 0.5)' },
    content: `{
  "task_id": "1",
  "owner_agent": "codex",
  "target_window": "task-1",
  "criticality": "standard",
  "status": "pending"
}`,
  },
  {
    id: 'note-2',
    appearsWithStep: 7,
    position: { x: 520, y: 420 },
    color: { bg: 'rgba(34, 197, 94, 0.1)', border: 'rgba(34, 197, 94, 0.5)' },
    content: `Parallel Rules:
• Non-conflicting writes → parallel
• Same file writes → sequential
• Max 9 tmux windows`,
  },
];

function CustomNode({ data }: { data: { title: string; description: string; phase: Phase } }) {
  const colors = phaseColors[data.phase];
  return (
    <div 
      className="custom-node"
      style={{ 
        backgroundColor: colors.bg, 
        borderColor: colors.border 
      }}
    >
      <Handle type="target" position={Position.Top} id="top" />
      <Handle type="target" position={Position.Left} id="left" />
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="source" position={Position.Bottom} id="bottom" />
      <Handle type="target" position={Position.Right} id="right-target" style={{ right: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom-target" style={{ bottom: 0 }} />
      <Handle type="source" position={Position.Top} id="top-source" />
      <Handle type="source" position={Position.Left} id="left-source" />
      <div className="node-content">
        <div className="node-title">{data.title}</div>
        {data.description && <div className="node-description">{data.description}</div>}
      </div>
    </div>
  );
}

function NoteNode({ data }: { data: { content: string; color: { bg: string; border: string } } }) {
  return (
    <div 
      className="note-node"
      style={{
        backgroundColor: data.color.bg,
        borderColor: data.color.border,
      }}
    >
      <pre>{data.content}</pre>
    </div>
  );
}

const nodeTypes = { custom: CustomNode, note: NoteNode };

const positions: { [key: string]: { x: number; y: number } } = {
  // Setup phase - vertical left
  '1': { x: 40, y: 20 },
  '2': { x: 60, y: 120 },
  '3': { x: 80, y: 220 },
  // Assignment phase - spread horizontally
  '4': { x: 60, y: 340 },
  '5': { x: 300, y: 340 },
  // Execution loop - wider circular arrangement
  '6': { x: 40, y: 480 },
  '7': { x: 320, y: 480 },
  '8': { x: 580, y: 560 },
  '9': { x: 380, y: 680 },
  '10': { x: 120, y: 680 },
  // Decision - moved down
  '11': { x: 40, y: 820 },
  // Exit - centered below
  '12': { x: 300, y: 940 },
  // Notes - adjusted to avoid overlap
  'note-1': { x: 520, y: 100 },
  'note-2': { x: 620, y: 680 },
};

const edgeConnections: { source: string; target: string; sourceHandle?: string; targetHandle?: string; label?: string }[] = [
  // Setup phase
  { source: '1', target: '2', sourceHandle: 'bottom', targetHandle: 'top' },
  { source: '2', target: '3', sourceHandle: 'bottom', targetHandle: 'top' },
  // Assignment phase
  { source: '3', target: '4', sourceHandle: 'bottom', targetHandle: 'top' },
  { source: '4', target: '5', sourceHandle: 'right', targetHandle: 'left' },
  { source: '5', target: '6', sourceHandle: 'bottom', targetHandle: 'top' },
  // Execution loop
  { source: '6', target: '7', sourceHandle: 'right', targetHandle: 'left' },
  { source: '7', target: '8', sourceHandle: 'right', targetHandle: 'top' },
  { source: '8', target: '9', sourceHandle: 'bottom', targetHandle: 'right-target' },
  { source: '9', target: '10', sourceHandle: 'left-source', targetHandle: 'right-target' },
  { source: '10', target: '11', sourceHandle: 'bottom', targetHandle: 'top' },
  // Decision
  { source: '11', target: '6', sourceHandle: 'top-source', targetHandle: 'left', label: 'No' },
  { source: '11', target: '12', sourceHandle: 'bottom', targetHandle: 'top', label: 'Yes' },
];

function createNode(step: typeof allSteps[0], visible: boolean, position?: { x: number; y: number }): Node {
  return {
    id: step.id,
    type: 'custom',
    position: position || positions[step.id],
    data: {
      title: step.label,
      description: step.description,
      phase: step.phase,
    },
    style: {
      width: nodeWidth,
      height: nodeHeight,
      opacity: visible ? 1 : 0,
      transition: 'opacity 0.5s ease-in-out',
      pointerEvents: visible ? 'auto' : 'none',
    },
  };
}

function createEdge(conn: typeof edgeConnections[0], visible: boolean): Edge {
  return {
    id: `e${conn.source}-${conn.target}`,
    source: conn.source,
    target: conn.target,
    sourceHandle: conn.sourceHandle,
    targetHandle: conn.targetHandle,
    label: visible ? conn.label : undefined,
    animated: visible,
    style: {
      stroke: 'rgba(255, 255, 255, 0.6)',
      strokeWidth: 2,
      opacity: visible ? 1 : 0,
      transition: 'opacity 0.5s ease-in-out',
    },
    labelStyle: {
      fill: '#fff',
      fontWeight: 600,
      fontSize: 12,
    },
    labelShowBg: true,
    labelBgPadding: [8, 4] as [number, number],
    labelBgStyle: {
      fill: 'rgba(30, 30, 50, 0.9)',
      stroke: 'rgba(255, 255, 255, 0.3)',
      strokeWidth: 1,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: 'rgba(255, 255, 255, 0.6)',
    },
  };
}

function createNoteNode(note: typeof notes[0], visible: boolean, position?: { x: number; y: number }): Node {
  return {
    id: note.id,
    type: 'note',
    position: position || positions[note.id],
    data: { content: note.content, color: note.color },
    style: {
      opacity: visible ? 1 : 0,
      transition: 'opacity 0.5s ease-in-out',
      pointerEvents: visible ? 'auto' : 'none',
    },
    draggable: true,
    selectable: false,
    connectable: false,
  };
}

function App() {
  const [visibleCount, setVisibleCount] = useState(1);
  const nodePositions = useRef<{ [key: string]: { x: number; y: number } }>({ ...positions });

  const getNodes = (count: number) => {
    const stepNodes = allSteps.map((step, index) =>
      createNode(step, index < count, nodePositions.current[step.id])
    );
    const noteNodes = notes.map(note => {
      const noteVisible = count >= note.appearsWithStep;
      return createNoteNode(note, noteVisible, nodePositions.current[note.id]);
    });
    return [...stepNodes, ...noteNodes];
  };

  const initialNodes = getNodes(1);
  const initialEdges = edgeConnections.map((conn) =>
    createEdge(conn, false)
  );

  const [nodes, setNodes] = useNodesState(initialNodes);
  const [edges, setEdges] = useEdgesState(initialEdges);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      changes.forEach((change) => {
        if (change.type === 'position' && change.position) {
          nodePositions.current[change.id] = change.position;
        }
      });
      setNodes((nds) => applyNodeChanges(changes, nds));
    },
    [setNodes]
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds));
    },
    [setEdges]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true, style: { stroke: 'rgba(255, 255, 255, 0.6)', strokeWidth: 2 }, markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(255, 255, 255, 0.6)' } }, eds));
    },
    [setEdges]
  );

  const onReconnect = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      setEdges((eds) => reconnectEdge(oldEdge, newConnection, eds));
    },
    [setEdges]
  );

  const getEdgeVisibility = (conn: typeof edgeConnections[0], visibleStepCount: number) => {
    const sourceIndex = allSteps.findIndex(s => s.id === conn.source);
    const targetIndex = allSteps.findIndex(s => s.id === conn.target);
    return sourceIndex < visibleStepCount && targetIndex < visibleStepCount;
  };

  const handleNext = useCallback(() => {
    if (visibleCount < allSteps.length) {
      const newCount = visibleCount + 1;
      setVisibleCount(newCount);

      setNodes(getNodes(newCount));
      setEdges(
        edgeConnections.map((conn) =>
          createEdge(conn, getEdgeVisibility(conn, newCount))
        )
      );
    }
  }, [visibleCount, setNodes, setEdges]);

  const handlePrev = useCallback(() => {
    if (visibleCount > 1) {
      const newCount = visibleCount - 1;
      setVisibleCount(newCount);

      setNodes(getNodes(newCount));
      setEdges(
        edgeConnections.map((conn) =>
          createEdge(conn, getEdgeVisibility(conn, newCount))
        )
      );
    }
  }, [visibleCount, setNodes, setEdges]);

  const handleReset = useCallback(() => {
    setVisibleCount(1);
    nodePositions.current = { ...positions };
    setNodes(getNodes(1));
    setEdges(edgeConnections.map((conn) => createEdge(conn, false)));
  }, [setNodes, setEdges]);

  return (
    <div className="app-container">
      <div className="header">
        <h1>Multi-Agent Orchestration Workflow</h1>
        <p>Coordinating Codex and Gemini agents for parallel task execution</p>
      </div>
      <div className="flow-container">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onReconnect={onReconnect}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={true}
          nodesConnectable={true}
          edgesReconnectable={true}
          elementsSelectable={true}
          deleteKeyCode={['Backspace', 'Delete']}
          panOnDrag={true}
          panOnScroll={true}
          zoomOnScroll={true}
          zoomOnPinch={true}
          zoomOnDoubleClick={true}
          selectNodesOnDrag={false}
        >
          <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="rgba(255, 255, 255, 0.08)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="controls">
        <button onClick={handlePrev} disabled={visibleCount <= 1}>
          Previous
        </button>
        <span className="step-counter">
          Step {visibleCount} of {allSteps.length}
        </span>
        <button onClick={handleNext} disabled={visibleCount >= allSteps.length}>
          Next
        </button>
        <button onClick={handleReset} className="reset-btn">
          Reset
        </button>
      </div>
      <div className="instructions">
        Click Next to reveal each step of the orchestration workflow
      </div>
    </div>
  );
}

export default App;
