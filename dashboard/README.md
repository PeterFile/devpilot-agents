# Tmux Event Visualization Dashboard

Real-time web dashboard for visualizing multi-agent orchestration events from tmux sessions.

## Features

- **Live Event Stream**: Real-time chat-style message stream with markdown rendering
- **Session Navigation**: Collapsible sidebar with window/pane tree
- **Aggregation Panel**: Stats for files touched, commands run, tests, and errors
- **High Performance**: Virtualized list supports 10k+ events

## Quick Start

```bash
# Install dependencies
npm install

# Start both server and UI
npm start

# Or run separately:
npm run server    # WebSocket server on port 3001
npm run dev       # Vite dev server on port 5173
```

## Usage

1. Start a tmux session (default name: `roundtable`)
2. Run `npm start` in the dashboard directory
3. Open http://localhost:5173

### Custom Session

```bash
npm run server -- mysession
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   tmux      │────▶│   Python    │────▶│  WebSocket  │
│   panes     │     │  collector  │     │   server    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   React     │
                                        │  Dashboard  │
                                        └─────────────┘
```

## File Structure

```
dashboard/
├── scripts/
│   └── collector.py       # Python tmux event collector
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx    # Window/Pane navigation
│   │   ├── LogViewer.tsx  # Chat-style event stream
│   │   ├── StatsPanel.tsx # Aggregation panel
│   │   └── MessageBubble.tsx
│   ├── lib/
│   │   ├── normalizer.ts  # JSON → Markdown transformer
│   │   ├── types.ts       # TypeScript interfaces
│   │   └── websocket.ts   # WS client hook
│   └── server/
│       └── index.ts       # Express + WebSocket server
└── package.json
```

## Development

```bash
# Type check
npx tsc --noEmit

# Lint
npm run lint

# Build for production
npm run build
```
