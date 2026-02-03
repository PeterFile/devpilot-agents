/**
 * Event Normalizer
 * 
 * Transforms raw JSON events from tmux into human-readable messages
 * with markdown formatting.
 */

import type { RawEvent, NormalizedEvent, EventMeta, AggregatedStats, EventType } from './types';

/**
 * Extract a human-readable title from event content
 */
function extractTitle(content: string, eventType: EventType): string {
  const titles: Record<EventType, string> = {
    message: '💬 Message',
    tool_call: '🔧 Tool Call',
    tool_result: '✅ Result',
    error: '❌ Error',
    status: '📊 Status',
    test_result: '🧪 Test Result',
    file_change: '📝 File Changed',
    command: '⚡ Command',
  };
  
  return titles[eventType] || '📋 Event';
}

/**
 * Convert raw content to markdown format
 */
function toMarkdown(content: string, eventType: EventType): string {
  // Try to parse as JSON first
  try {
    const json = JSON.parse(content);
    return formatJsonAsMarkdown(json, eventType);
  } catch {
    // Check for key:value pattern (e.g., "type: message timestamp: ...")
    if (content.includes(': ') && /^\w+:/.test(content.trim())) {
      return formatKeyValueText(content, eventType);
    }
    // Not JSON, format as plain text or code
    return formatPlainText(content, eventType);
  }
}

/**
 * Parse key:value formatted text into structured data
 */
function parseKeyValueText(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  
  // Known keys to look for
  const knownKeys = ['type', 'timestamp', 'role', 'content', 'delta', 'item', 'text', 'status', 'usage', 'command'];
  
  const remaining = text;
  for (const key of knownKeys) {
    const regex = new RegExp(`\\b${key}:\\s*`, 'i');
    const match = remaining.match(regex);
    if (match && match.index !== undefined) {
      // Find where this value ends (either at next key or end)
      const startIdx = match.index + match[0].length;
      let endIdx = remaining.length;
      
      for (const nextKey of knownKeys) {
        if (nextKey === key) continue;
        const nextRegex = new RegExp(`\\s+${nextKey}:\\s*`, 'i');
        const nextMatch = remaining.slice(startIdx).match(nextRegex);
        if (nextMatch && nextMatch.index !== undefined) {
          const potentialEnd = startIdx + nextMatch.index;
          if (potentialEnd < endIdx) {
            endIdx = potentialEnd;
          }
        }
      }
      
      result[key] = remaining.slice(startIdx, endIdx).trim();
    }
  }
  
  return result;
}

/**
 * Format key:value text as markdown
 */
function formatKeyValueText(content: string, _eventType: EventType): string {
  const parsed = parseKeyValueText(content);
  const parts: string[] = [];
  
  // Format based on content type
  if (parsed.type) {
    const typeLabel = parsed.type.replace(/_/g, ' ').replace(/\./g, ' › ');
    parts.push(`**${typeLabel}**`);
  }
  
  if (parsed.role) {
    parts.push(`*${parsed.role}*`);
  }
  
  if (parsed.content) {
    // Try to unescape and format content
    let displayContent = parsed.content;
    
    // Handle escaped newlines
    displayContent = displayContent.replace(/\\n/g, '\n');
    
    // Check if content looks like JSON
    if (displayContent.startsWith('{') || displayContent.startsWith('[')) {
      try {
        const innerJson = JSON.parse(displayContent);
        displayContent = '```json\n' + JSON.stringify(innerJson, null, 2) + '\n```';
      } catch {
        // Keep as is
      }
    }
    
    parts.push(displayContent);
  }
  
  if (parsed.text) {
    parts.push(parsed.text.replace(/\\n/g, '\n'));
  }
  
  if (parsed.item) {
    // Try to parse item as JSON
    try {
      const itemJson = JSON.parse(parsed.item);
      parts.push(formatItemContent(itemJson));
    } catch {
      parts.push(parsed.item);
    }
  }
  
  if (parsed.status) {
    parts.push(`**Status**: \`${parsed.status}\``);
  }
  
  if (parsed.usage) {
    try {
      const usage = JSON.parse(parsed.usage);
      parts.push(`📊 Tokens: ${usage.input_tokens?.toLocaleString() || 0} in / ${usage.output_tokens?.toLocaleString() || 0} out`);
    } catch {
      parts.push(`Usage: ${parsed.usage}`);
    }
  }
  
  return parts.length > 0 ? parts.join('\n\n') : content;
}

/**
 * Format item content (from agent events)
 */
function formatItemContent(item: Record<string, unknown>): string {
  const parts: string[] = [];
  
  if (item.type) {
    parts.push(`🔹 **${String(item.type).replace(/_/g, ' ')}**`);
  }
  
  if (item.id) {
    parts.push(`ID: \`${item.id}\``);
  }
  
  if (item.text) {
    parts.push(String(item.text).replace(/\\n/g, '\n'));
  }
  
  if (item.command) {
    parts.push('```bash\n' + item.command + '\n```');
  }
  
  if (item.aggregated_output) {
    const output = String(item.aggregated_output);
    if (output.length > 200) {
      parts.push('```\n' + output.slice(0, 200) + '...\n```');
    } else if (output.trim()) {
      parts.push('```\n' + output + '\n```');
    }
  }
  
  if (item.exit_code !== undefined && item.exit_code !== null) {
    const code = item.exit_code as number;
    parts.push(code === 0 ? '✅ Exit: 0' : `❌ Exit: ${code}`);
  }
  
  if (item.status) {
    parts.push(`Status: \`${item.status}\``);
  }
  
  return parts.join('\n');
}

/**
 * Format JSON content as readable markdown
 */
function formatJsonAsMarkdown(json: Record<string, unknown>, _eventType: EventType): string {
  const parts: string[] = [];
  
  // Handle agent message format
  if (json.type === 'agent_message' && json.text) {
    return String(json.text).replace(/\\n/g, '\n');
  }
  
  // Handle item.completed format
  if (json.type === 'item.completed' && json.item) {
    return formatItemContent(json.item as Record<string, unknown>);
  }
  
  // Handle turn.completed format
  if (json.type === 'turn.completed' && json.usage) {
    const usage = json.usage as Record<string, number>;
    return `📊 **Turn Complete**\nTokens: ${usage.input_tokens?.toLocaleString() || 0} in / ${usage.output_tokens?.toLocaleString() || 0} out`;
  }
  
  // Tool call formatting
  if (json.tool_name || json.tool) {
    const toolName = json.tool_name || json.tool;
    parts.push(`Running **${toolName}**...`);
    
    if (json.arguments || json.args) {
      const args = json.arguments || json.args;
      if (typeof args === 'object') {
        const argStr = Object.entries(args as Record<string, unknown>)
          .map(([k, v]) => `- \`${k}\`: ${JSON.stringify(v)}`)
          .join('\n');
        parts.push(argStr);
      }
    }
  }
  
  // Tool result formatting
  if (json.result || json.output) {
    const result = json.result || json.output;
    if (typeof result === 'string') {
      if (result.includes('\n')) {
        parts.push('```\n' + result + '\n```');
      } else {
        parts.push(result);
      }
    }
  }
  
  // Status formatting
  if (json.status && typeof json.status === 'string') {
    parts.push(`**Status**: ${json.status}`);
  }
  
  // Message formatting
  if (json.message) {
    parts.push(String(json.message));
  }
  
  // Error formatting
  if (json.error) {
    parts.push(`**Error**: ${json.error}`);
  }
  
  // File changes
  if (json.file || json.path) {
    const file = json.file || json.path;
    parts.push(`Modified \`${file}\``);
    
    if (json.diff) {
      parts.push('```diff\n' + json.diff + '\n```');
    }
  }
  
  if (parts.length === 0) {
    // Fallback: format as readable JSON
    return '```json\n' + JSON.stringify(json, null, 2) + '\n```';
  }
  
  return parts.join('\n\n');
}

/**
 * Format plain text content as markdown
 */
function formatPlainText(content: string, eventType: EventType): string {
  // ANSI escape sequence removal
  // eslint-disable-next-line no-control-regex
  const cleanContent = content.replace(/\x1b\[[0-9;]*m/g, '');
  
  // Command detection
  if (cleanContent.startsWith('$') || cleanContent.startsWith('>')) {
    const cmd = cleanContent.slice(1).trim();
    return '```bash\n' + cmd + '\n```';
  }
  
  // Code block detection
  if (cleanContent.includes('```')) {
    return cleanContent;
  }
  
  // Error formatting
  if (eventType === 'error' || cleanContent.toLowerCase().includes('error')) {
    return `> ⚠️ ${cleanContent}`;
  }
  
  // Warning formatting (yellow background often indicates warnings)
  if (cleanContent.toLowerCase().includes('warning')) {
    return `> ⚠️ ${cleanContent}`;
  }
  
  // File path detection
  const fileMatch = cleanContent.match(/([a-zA-Z]:[/\\]|\.?[/\\])?[\w\-./\\]+\.(ts|tsx|js|jsx|py|go|rs|md)/g);
  if (fileMatch) {
    let formatted = cleanContent;
    fileMatch.forEach(file => {
      formatted = formatted.replace(file, `\`${file}\``);
    });
    return formatted;
  }
  
  return cleanContent;
}

/**
 * Extract metadata from event content
 */
function extractMeta(content: string, eventType: EventType): EventMeta {
  const meta: EventMeta = {};
  
  // Extract file paths
  const fileMatches = content.match(/[a-zA-Z]?:?[/\\]?[\w\-./\\]+\.(ts|tsx|js|jsx|py|go|rs|md|json)/g);
  if (fileMatches) {
    meta.filesModified = [...new Set(fileMatches)];
  }
  
  // Extract commands
  if (eventType === 'command' || content.startsWith('$')) {
    const cmd = content.replace(/^\$\s*/, '').trim();
    if (cmd) {
      meta.commandsRun = [cmd];
    }
  }
  
  // Extract test results
  const passMatch = content.match(/(\d+)\s*(?:tests?\s+)?passed/i);
  const failMatch = content.match(/(\d+)\s*(?:tests?\s+)?failed/i);
  if (passMatch || failMatch) {
    meta.testResults = {
      passed: passMatch ? parseInt(passMatch[1]) : 0,
      failed: failMatch ? parseInt(failMatch[1]) : 0,
    };
  }
  
  // Extract errors
  if (eventType === 'error') {
    meta.errors = [content];
  }
  
  return meta;
}

/**
 * Normalize a raw event into a display-ready format
 */
export function normalizeEvent(raw: RawEvent): NormalizedEvent {
  const eventType = raw.event_type;
  const title = extractTitle(raw.content, eventType);
  const markdown = toMarkdown(raw.content, eventType);
  const meta = extractMeta(raw.content, eventType);
  
  return {
    id: raw.id,
    timestamp: raw.timestamp,
    source: raw.source,
    type: eventType,
    title,
    content: raw.content,
    markdown,
    meta,
  };
}

/**
 * Aggregate stats from multiple events
 */
export function aggregateStats(events: NormalizedEvent[]): AggregatedStats {
  const filesSet = new Set<string>();
  const commandsSet = new Set<string>();
  const errorsSet = new Set<string>();
  let testsPassed = 0;
  let testsFailed = 0;
  
  for (const event of events) {
    if (event.meta.filesModified) {
      event.meta.filesModified.forEach(f => filesSet.add(f));
    }
    if (event.meta.commandsRun) {
      event.meta.commandsRun.forEach(c => commandsSet.add(c));
    }
    if (event.meta.errors) {
      event.meta.errors.forEach(e => errorsSet.add(e));
    }
    if (event.meta.testResults) {
      testsPassed += event.meta.testResults.passed;
      testsFailed += event.meta.testResults.failed;
    }
  }
  
  return {
    totalEvents: events.length,
    filesModified: [...filesSet],
    commandsRun: [...commandsSet],
    testsRun: { passed: testsPassed, failed: testsFailed },
    errors: [...errorsSet],
  };
}
