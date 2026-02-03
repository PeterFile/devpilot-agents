/**
 * Sidebar Component
 * 
 * Displays session tree with windows and panes.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight, Monitor, Terminal, Wifi, WifiOff } from 'lucide-react';
import type { SessionState, WindowInfo, PaneInfo } from '../lib/types';
import './Sidebar.css';

interface SidebarProps {
  session: SessionState | null;
  connected: boolean;
  onSelectWindow?: (windowId: string) => void;
  selectedWindow?: string;
}

const statusIcons: Record<PaneInfo['status'], string> = {
  active: '✅',
  busy: '⏳',
  idle: '💤',
  error: '❌',
};

export function Sidebar({ session, connected, onSelectWindow, selectedWindow }: SidebarProps) {
  const [expandedWindows, setExpandedWindows] = useState<Set<string>>(new Set());
  
  const toggleWindow = (windowId: string) => {
    setExpandedWindows(prev => {
      const next = new Set(prev);
      if (next.has(windowId)) {
        next.delete(windowId);
      } else {
        next.add(windowId);
      }
      return next;
    });
  };
  
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">
          <Monitor size={20} />
          <span>Dashboard</span>
        </h1>
        <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
          <span>{connected ? 'Live' : 'Offline'}</span>
        </div>
      </div>
      
      <div className="sidebar-content">
        {session ? (
          <div className="session-tree">
            <div className="session-name">
              <Terminal size={16} />
              <span>{session.name}</span>
            </div>
            
            {session.windows.length > 0 ? (
              <ul className="window-list">
                {session.windows.map(window => (
                  <WindowItem
                    key={window.id}
                    window={window}
                    expanded={expandedWindows.has(window.id)}
                    selected={selectedWindow === window.id}
                    onToggle={() => toggleWindow(window.id)}
                    onSelect={() => onSelectWindow?.(window.id)}
                  />
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <p>No windows detected</p>
                <p className="hint">Windows will appear when detected</p>
              </div>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <p>No session connected</p>
            <p className="hint">Start the server to connect</p>
          </div>
        )}
      </div>
      
      <div className="sidebar-footer">
        <div className="footer-info">
          <span className="version">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}

interface WindowItemProps {
  window: WindowInfo;
  expanded: boolean;
  selected: boolean;
  onToggle: () => void;
  onSelect: () => void;
}

function WindowItem({ window: win, expanded, selected, onToggle, onSelect }: WindowItemProps) {
  return (
    <li className="window-item">
      <div 
        className={`window-header ${selected ? 'selected' : ''} ${win.isActive ? 'active' : ''}`}
        onClick={onSelect}
      >
        <button className="expand-btn" onClick={(e) => { e.stopPropagation(); onToggle(); }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="window-name">{win.name}</span>
        {win.isActive && <span className="active-badge">●</span>}
      </div>
      
      {expanded && win.panes.length > 0 && (
        <ul className="pane-list">
          {win.panes.map(pane => (
            <li key={pane.id} className="pane-item">
              <span className="pane-status">{statusIcons[pane.status]}</span>
              <span className="pane-id">{pane.id}</span>
              <span className="pane-command">{pane.command}</span>
              {pane.eventCount > 0 && (
                <span className="pane-count">{pane.eventCount}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
