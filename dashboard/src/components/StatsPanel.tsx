/**
 * StatsPanel Component
 * 
 * Displays aggregated statistics from events.
 */

import { useMemo, useState } from 'react';
import { FileText, Terminal, FlaskConical, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { NormalizedEvent } from '../lib/types';
import { aggregateStats } from '../lib/normalizer';
import './StatsPanel.css';

interface StatsPanelProps {
  events: NormalizedEvent[];
}

export function StatsPanel({ events }: StatsPanelProps) {
  const stats = useMemo(() => aggregateStats(events), [events]);
  
  return (
    <aside className="stats-panel">
      <div className="stats-header">
        <h2 className="stats-title">Aggregation</h2>
      </div>
      
      <div className="stats-content">
        <StatCard
          icon={<FileText size={18} />}
          label="Files Touched"
          count={stats.filesModified.length}
          items={stats.filesModified}
          color="var(--color-file)"
        />
        
        <StatCard
          icon={<Terminal size={18} />}
          label="Commands Run"
          count={stats.commandsRun.length}
          items={stats.commandsRun}
          color="var(--color-command)"
        />
        
        <TestCard
          passed={stats.testsRun.passed}
          failed={stats.testsRun.failed}
        />
        
        <StatCard
          icon={<AlertCircle size={18} />}
          label="Errors"
          count={stats.errors.length}
          items={stats.errors}
          color="var(--color-error)"
          isError
        />
      </div>
    </aside>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  count: number;
  items: string[];
  color: string;
  isError?: boolean;
}

function StatCard({ icon, label, count, items, color, isError }: StatCardProps) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className={`stat-card ${isError && count > 0 ? 'error' : ''}`}>
      <div 
        className="stat-header"
        onClick={() => items.length > 0 && setExpanded(!expanded)}
        style={{ cursor: items.length > 0 ? 'pointer' : 'default' }}
      >
        <div className="stat-icon" style={{ color }}>
          {icon}
        </div>
        <div className="stat-info">
          <span className="stat-label">{label}</span>
          <span className="stat-count" style={{ color: count > 0 ? color : undefined }}>
            {count}
          </span>
        </div>
        {items.length > 0 && (
          <div className="expand-icon">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        )}
      </div>
      
      {expanded && items.length > 0 && (
        <ul className="stat-items">
          {items.slice(0, 10).map((item, i) => (
            <li key={i} className="stat-item">
              {formatItem(item)}
            </li>
          ))}
          {items.length > 10 && (
            <li className="stat-item more">
              +{items.length - 10} more
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

interface TestCardProps {
  passed: number;
  failed: number;
}

function TestCard({ passed, failed }: TestCardProps) {
  const total = passed + failed;
  const passRate = total > 0 ? (passed / total) * 100 : 0;
  
  return (
    <div className="stat-card test-card">
      <div className="stat-header">
        <div className="stat-icon" style={{ color: 'var(--color-test)' }}>
          <FlaskConical size={18} />
        </div>
        <div className="stat-info">
          <span className="stat-label">Tests</span>
          <span className="stat-count">
            {total > 0 ? `${passed}/${total}` : '0'}
          </span>
        </div>
      </div>
      
      {total > 0 && (
        <div className="test-progress">
          <div className="progress-bar">
            <div 
              className="progress-fill passed"
              style={{ width: `${passRate}%` }}
            />
            <div 
              className="progress-fill failed"
              style={{ width: `${100 - passRate}%` }}
            />
          </div>
          <div className="test-stats">
            <span className="passed-count">✓ {passed}</span>
            <span className="failed-count">✗ {failed}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function formatItem(item: string): string {
  // Shorten file paths
  if (item.includes('/') || item.includes('\\')) {
    const parts = item.split(/[/\\]/);
    return parts.slice(-2).join('/');
  }
  // Truncate long commands
  if (item.length > 40) {
    return item.slice(0, 40) + '...';
  }
  return item;
}
