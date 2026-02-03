/**
 * LogViewer Component
 * 
 * Displays real-time chat-style message stream with virtualization.
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Pause, Play, Trash2, ArrowDown } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import type { NormalizedEvent, EventType } from '../lib/types';
import './LogViewer.css';

interface LogViewerProps {
  events: NormalizedEvent[];
  onClear: () => void;
  filter?: {
    types?: EventType[];
    search?: string;
    source?: string;
  };
}

export function LogViewer({ events, onClear, filter }: LogViewerProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  
  // Filter events
  const filteredEvents = events.filter(event => {
    if (filter?.types && filter.types.length > 0) {
      if (!filter.types.includes(event.type)) return false;
    }
    if (filter?.search) {
      const search = filter.search.toLowerCase();
      if (!event.content.toLowerCase().includes(search) &&
          !event.markdown.toLowerCase().includes(search)) {
        return false;
      }
    }
    if (filter?.source) {
      if (!event.source.window.includes(filter.source) &&
          !event.source.pane.includes(filter.source)) {
        return false;
      }
    }
    return true;
  });
  
  const virtualizer = useVirtualizer({
    count: filteredEvents.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,
    overscan: 5,
  });
  
  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && parentRef.current && filteredEvents.length > 0) {
      requestAnimationFrame(() => {
        virtualizer.scrollToIndex(filteredEvents.length - 1, { align: 'end' });
      });
    }
  }, [filteredEvents.length, autoScroll, virtualizer]);
  
  // Detect manual scroll to disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!parentRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = parentRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
    
    setShowScrollButton(!isAtBottom);
    
    // Re-enable auto-scroll when user scrolls to bottom
    if (isAtBottom && !autoScroll) {
      setAutoScroll(true);
    }
  }, [autoScroll]);
  
  const scrollToBottom = useCallback(() => {
    setAutoScroll(true);
    virtualizer.scrollToIndex(filteredEvents.length - 1, { align: 'end' });
  }, [virtualizer, filteredEvents.length]);
  
  const toggleAutoScroll = useCallback(() => {
    setAutoScroll(prev => !prev);
  }, []);
  
  return (
    <div className="log-viewer">
      <div className="log-header">
        <h2 className="log-title">Event Stream</h2>
        <div className="log-stats">
          <span className="event-count">{filteredEvents.length} events</span>
        </div>
        <div className="log-actions">
          <button 
            className={`action-btn ${autoScroll ? 'active' : ''}`}
            onClick={toggleAutoScroll}
            title={autoScroll ? 'Pause auto-scroll' : 'Resume auto-scroll'}
          >
            {autoScroll ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button 
            className="action-btn"
            onClick={onClear}
            title="Clear events"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
      
      <div 
        ref={parentRef} 
        className="log-content"
        onScroll={handleScroll}
      >
        {filteredEvents.length === 0 ? (
          <div className="log-empty">
            <div className="empty-icon">📭</div>
            <p>Waiting for events...</p>
            <p className="empty-hint">Events will appear here as they stream from tmux</p>
          </div>
        ) : (
          <div
            style={{
              height: `${virtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualizer.getVirtualItems().map((virtualItem) => (
              <div
                key={virtualItem.key}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualItem.start}px)`,
                }}
              >
                <MessageBubble event={filteredEvents[virtualItem.index]} />
              </div>
            ))}
          </div>
        )}
      </div>
      
      {showScrollButton && (
        <button 
          className="scroll-to-bottom"
          onClick={scrollToBottom}
        >
          <ArrowDown size={16} />
          <span>New events</span>
        </button>
      )}
    </div>
  );
}
