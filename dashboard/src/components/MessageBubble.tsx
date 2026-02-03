/**
 * MessageBubble Component
 * 
 * Displays a single event as a chat-style message with markdown rendering.
 */

import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { NormalizedEvent, EventType } from '../lib/types';
import './MessageBubble.css';

interface MessageBubbleProps {
  event: NormalizedEvent;
}

const eventIcons: Record<EventType, string> = {
  message: '💬',
  tool_call: '🔧',
  tool_result: '✅',
  error: '❌',
  status: '📊',
  test_result: '🧪',
  file_change: '📝',
  command: '⚡',
};

const eventColors: Record<EventType, string> = {
  message: 'var(--color-message)',
  tool_call: 'var(--color-tool)',
  tool_result: 'var(--color-success)',
  error: 'var(--color-error)',
  status: 'var(--color-status)',
  test_result: 'var(--color-test)',
  file_change: 'var(--color-file)',
  command: 'var(--color-command)',
};

function formatTime(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function MessageBubbleComponent({ event }: MessageBubbleProps) {
  const icon = eventIcons[event.type] || '📋';
  const accentColor = eventColors[event.type] || 'var(--color-border)';
  const time = useMemo(() => formatTime(event.timestamp), [event.timestamp]);
  
  return (
    <div className="message-bubble" style={{ '--accent-color': accentColor } as React.CSSProperties}>
      <div className="message-header">
        <span className="message-icon">{icon}</span>
        <span className="message-source">
          {event.source.window}
          <span className="message-pane">:{event.source.pane}</span>
        </span>
        <span className="message-time">{time}</span>
      </div>
      <div className="message-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const isInline = !match;
              
              return isInline ? (
                <code className="inline-code" {...props}>
                  {children}
                </code>
              ) : (
                <pre className={`code-block language-${match[1]}`}>
                  <code {...props}>{children}</code>
                </pre>
              );
            },
            blockquote({ children }) {
              return <blockquote className="quote">{children}</blockquote>;
            },
          }}
        >
          {event.markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}

export const MessageBubble = memo(MessageBubbleComponent);
