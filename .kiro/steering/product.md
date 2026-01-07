# Product Overview

Claude Code Multi-Agent Workflow System - AI-powered development automation with multi-backend execution.

## Core Concept

Dual-agent architecture with pluggable AI backends:
- **Orchestrator (Claude Code)**: Planning, context gathering, verification, user interaction
- **Executor (codeagent-wrapper)**: Code editing, test execution via Codex/Claude/Gemini backends

## Key Workflows

| Workflow | Command | Use Case |
|----------|---------|----------|
| Dev Workflow | `/dev` | Primary workflow - feature development with 90% test coverage gate |
| BMAD Agile | `/bmad-pilot` | Enterprise agile with 6 specialized agents |
| Requirements-Driven | `/requirements-pilot` | Lightweight requirements-to-code pipeline |
| Development Essentials | `/code`, `/debug`, `/test`, etc. | Quick daily coding tasks |

## Installation

```bash
python3 install.py --install-dir ~/.claude
```

Installs to `~/.claude/` with modular configuration via `config.json`.
