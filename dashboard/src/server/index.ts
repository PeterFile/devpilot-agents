/**
 * WebSocket Server
 * 
 * Bridges Python collector output to browser clients via WebSocket.
 */

import express from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { spawn, ChildProcess } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const PORT = 3001;

interface Client {
  ws: WebSocket;
  id: string;
}

const clients: Map<string, Client> = new Map();
let collector: ChildProcess | null = null;
let clientIdCounter = 0;

// Event cache for new clients
const MAX_CACHED_EVENTS = 100;
const eventBuffer: string[] = [];

// Create Express app
const app = express();
app.use(express.json());

// Health check endpoint
app.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    clients: clients.size,
    collectorRunning: collector !== null && !collector.killed,
  });
});

// Create HTTP server
const server = createServer(app);

// Create WebSocket server
const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
  const clientId = `client-${++clientIdCounter}`;
  clients.set(clientId, { ws, id: clientId });
  
  console.log(`[WS] Client connected: ${clientId} (total: ${clients.size})`);
  
  // Send initial state
  ws.send(JSON.stringify({
    type: 'init',
    session: 'all',
    timestamp: Date.now() / 1000,
  }));
  
  // Send cached events to new client
  console.log(`[WS] Sending ${eventBuffer.length} cached events to ${clientId}`);
  for (const event of eventBuffer) {
    ws.send(event);
  }
  
  ws.on('close', () => {
    clients.delete(clientId);
    console.log(`[WS] Client disconnected: ${clientId} (total: ${clients.size})`);
  });
  
  ws.on('error', (err) => {
    console.error(`[WS] Client error: ${clientId}`, err.message);
  });
});

// Broadcast message to all clients and cache for new clients
function broadcast(data: string) {
  // Cache event for new clients (only events with id)
  try {
    const parsed = JSON.parse(data);
    if (parsed.id) {
      eventBuffer.push(data);
      if (eventBuffer.length > MAX_CACHED_EVENTS) {
        eventBuffer.shift();
      }
    }
  } catch {
    // Not JSON, skip caching
  }
  
  clients.forEach(({ ws }) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(data);
    }
  });
}

// Start Python collector
function startCollector() {
  let collectorPath = resolve(__dirname, '../../scripts/collector.py');
  
  // Convert Windows path to WSL path if needed
  if (collectorPath.match(/^[A-Z]:\\/i)) {
    const drive = collectorPath[0].toLowerCase();
    collectorPath = `/mnt/${drive}${collectorPath.slice(2).replace(/\\/g, '/')}`;
  }
  
  console.log(`[Collector] Starting...`);
  console.log(`[Collector] Path: ${collectorPath}`);
  
  collector = spawn('python3', [
    collectorPath,
    '--interval', '500',
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: true,
  });
  
  if (!collector.pid) {
    console.error('[Collector] Failed to spawn process');
    return;
  }
  
  console.log(`[Collector] PID: ${collector.pid}`);
  
  collector.stdout?.on('data', (data: Buffer) => {
    const raw = data.toString();
    console.log(`[Collector] Raw output (${raw.length} bytes)`);
    const lines = raw.trim().split('\n');
    
    for (const line of lines) {
      if (!line) continue;
      
      try {
        JSON.parse(line);
        broadcast(line);
      } catch {
        console.error('[Collector] Invalid JSON:', line.slice(0, 100));
      }
    }
  });
  
  collector.stderr?.on('data', (data: Buffer) => {
    console.error('[Collector] Error:', data.toString());
  });
  
  collector.on('close', (code) => {
    console.log(`[Collector] Exited with code ${code}`);
    collector = null;
    
    if (code !== 0) {
      console.log('[Collector] Restarting in 5 seconds...');
      setTimeout(startCollector, 5000);
    }
  });
  
  collector.on('error', (err) => {
    console.error('[Collector] Failed to start:', err.message);
  });
}

// Graceful shutdown
function shutdown() {
  console.log('\n[Server] Shutting down...');
  
  if (collector) {
    collector.kill('SIGTERM');
  }
  
  wss.close(() => {
    server.close(() => {
      console.log('[Server] Goodbye!');
      process.exit(0);
    });
  });
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// Start server
server.listen(PORT, () => {
  console.log(`
╔══════════════════════════════════════════════╗
║     Tmux Event Dashboard Server              ║
╠══════════════════════════════════════════════╣
║  WebSocket:  ws://localhost:${PORT}             ║
║  Health:     http://localhost:${PORT}/health    ║
║  Session:    all (auto-detect)               ║
╚══════════════════════════════════════════════╝
  `);
  
  startCollector();
});
