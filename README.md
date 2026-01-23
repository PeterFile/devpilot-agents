[中文版](README_CN.md) | English

# DevPilot Agents: Multi-Agent Orchestration Framework

> **"Arthur's Excalibur is drawn from the stone... Will you march forth into battle beside your King?"**

A high-fidelity **Multi-Agent Orchestration System** for complex software engineering tasks. Uses a "Round Table" philosophy where **King Arthur** (orchestrator) coordinates specialized agents to implement, review, and synchronize codebase changes at scale.

## Core Architecture: The Round Table

| Role                  | Agent           | Responsibility                                                  |
| :-------------------- | :-------------- | :-------------------------------------------------------------- |
| **King Arthur**       | Orchestrator    | Planning, delegation, quality gates, and project sync.          |
| **Gawain**            | Decision Knight | Inner-loop decision making, strict JSON output, and validation. |
| **Codex/Gemini**      | Workers         | Distributed execution of code (Codex) and UI (Gemini) tasks.    |
| **codeagent-wrapper** | Execution Layer | Go runtime that drives backends in parallel.                    |

## Prerequisites

- **Go 1.21+**: Required to build `codeagent-wrapper`
- **Claude Code / OpenCode**: Required to trigger skills

## Installation

### Step 1: Install Skills

```bash
npx skills add PeterFile/devpilot-agents
```

This installs all skills from this repository into your agent environment.

### Step 2: Build codeagent-wrapper

```bash
git clone https://github.com/PeterFile/devpilot-agents.git
cd devpilot-agents/codeagent-wrapper
go build -o codeagent-wrapper .
```

On Windows:

```powershell
go build -o codeagent-wrapper.exe .
```

### Step 3: Add to PATH

**Linux/macOS:**

```bash
export PATH="$PWD:$PATH"
```

**Windows (PowerShell):**

```powershell
$env:PATH = "$PWD;$env:PATH"
```

## Using Skills

Skills are triggered automatically when you describe your task in natural language:

| Trigger Example                                             | Skill                    |
| ----------------------------------------------------------- | ------------------------ |
| "Start orchestration from spec at `.kiro/specs/my-feature`" | multi-agent-orchestrator |
| "Run orchestration for `payment-integration`"               | multi-agent-orchestrator |
| "Create requirements for a new feature"                     | kiro-specs               |
| "Help me write tests first"                                 | test-driven-development  |

### Available Skills

| Skill                        | Description                                                   |
| ---------------------------- | ------------------------------------------------------------- |
| **multi-agent-orchestrator** | Orchestrate multi-agent workflows from Kiro specs             |
| **kiro-specs**               | Spec-driven workflow: requirements → design → tasks → execute |
| **test-driven-development**  | Red-Green-Refactor TDD workflow                               |

## Project Structure

```
├── skills/
│   ├── multi-agent-orchestration/   # Core orchestration skill
│   ├── kiro-specs/                  # Spec-driven workflow skill
│   └── test-driven-development/     # TDD skill
├── .opencode/agents/                # Agent definitions
├── codeagent-wrapper/               # Go execution engine
└── docs/                            # Documentation
```

## Flowchart

[![Multi-Agent Orchestration Flowchart](flowchart.png)](https://peterfile.github.io/devpilot-agents/)

**[View Interactive Flowchart](https://peterfile.github.io/devpilot-agents/)** - Click through to see each step with animations.

The `flowchart/` directory contains the source code. To run locally:

```bash
cd flowchart
npm install
npm run dev
```

## Documentation

- **[Architecture (docs/ARCHITECTURE.md)](docs/ARCHITECTURE.md)**: The Round Table agent collaboration.
- **[Quick Start Guide (docs/QUICK-START.md)](docs/QUICK-START.md)**: Getting started.

## Acknowledgments

This project builds upon the work of several excellent open-source projects:

| Component                | Source                                              |
| ------------------------ | --------------------------------------------------- |
| **codeagent-wrapper**    | [cexll/myclaude](https://github.com/cexll/myclaude) |
| **Orchestration Loop**   | [ralph](https://github.com/snarktank/ralph)                                     |
| **Skills Specification** | [claude_skills](https://github.com/anthropics/skills)                     |

---

**Claude Code + Distributed Orchestration = The Future of Autonomous Engineering.**
