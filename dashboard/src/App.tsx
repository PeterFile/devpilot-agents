/**
 * Tmux Event Visualization Dashboard
 * 
 * Real-time visualization of multi-agent orchestration events.
 */

import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { LogViewer } from './components/LogViewer';
import { StatsPanel } from './components/StatsPanel';
import { useWebSocket } from './lib/websocket';
import type { EventType } from './lib/types';
import './App.css';

function App() {
  const { events, session, connected, error, clearEvents } = useWebSocket();
  const [selectedWindow, setSelectedWindow] = useState<string>();
  const [filter] = useState<{
    types?: EventType[];
    search?: string;
    source?: string;
  }>({});

  return (
    <div className="dashboard">
      <Sidebar
        session={session}
        connected={connected}
        selectedWindow={selectedWindow}
        onSelectWindow={setSelectedWindow}
      />
      
      <main className="main-content">
        {error && (
          <div className="error-banner">
            <span>⚠️ {error}</span>
          </div>
        )}
        <LogViewer
          events={events}
          onClear={clearEvents}
          filter={filter}
        />
      </main>
      
      <StatsPanel events={events} />
    </div>
  );
}

export default App;
