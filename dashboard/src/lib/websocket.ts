/**
 * WebSocket Client Hook
 * 
 * Connects to the event server and manages real-time event streaming.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { RawEvent, NormalizedEvent, SessionState } from './types';
import { normalizeEvent } from './normalizer';

const WS_URL = 'ws://localhost:3001';
const MAX_EVENTS = 1000;
const RECONNECT_DELAY = 3000;

interface UseWebSocketResult {
  events: NormalizedEvent[];
  session: SessionState | null;
  connected: boolean;
  error: string | null;
  clearEvents: () => void;
}

export function useWebSocket(): UseWebSocketResult {
  const [events, setEvents] = useState<NormalizedEvent[]>([]);
  const [session, setSession] = useState<SessionState | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  
  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    try {
      console.log(`[WS] Connecting to ${WS_URL}...`);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      
      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setError(null);
        console.log('[WS] Connected');
      };
      
      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        
        try {
          const data = JSON.parse(event.data);
          console.log('[WS] Received:', data.type || data.event_type, data.id || '');
          
          if (data.type === 'init') {
            setSession({
              name: data.session,
              windows: [],
              connected: true,
            });
          } else if (data.type === 'session_state') {
            setSession(data.state);
          } else if (data.id) {
            const normalized = normalizeEvent(data as RawEvent);
            setEvents(prev => {
              const updated = [...prev, normalized];
              return updated.length > MAX_EVENTS 
                ? updated.slice(-MAX_EVENTS) 
                : updated;
            });
          }
        } catch (e) {
          console.error('[WS] Parse error:', e, 'Raw:', event.data.slice(0, 200));
        }
      };
      
      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        wsRef.current = null;
        
        // Reconnect after delay
        console.log('[WS] Disconnected, reconnecting in 3s...');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, RECONNECT_DELAY);
      };
      
      ws.onerror = () => {
        if (!mountedRef.current) return;
        setError('Connection error');
        // Let onclose handle reconnect
      };
      
    } catch (e) {
      setError(`Failed to connect: ${e}`);
      // Retry after delay
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, RECONNECT_DELAY);
    }
  }, []);
  
  useEffect(() => {
    mountedRef.current = true;
    connect();
    
    return () => {
      mountedRef.current = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);
  
  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);
  
  return {
    events,
    session,
    connected,
    error,
    clearEvents,
  };
}
