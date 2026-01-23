# codeagent-wrapper: The Execution Engine

The Go runtime for the Multi-Agent Orchestration Framework. Provides a unified, cross-platform interface for parallel code execution across multiple AI backends.

## Role in the System

In the orchestration loop, `codeagent-wrapper` acts as the **Execution Layer**:

- **Parallel Dispatch**: Resolves task dependencies and executes independent tasks concurrently.
- **Backend Isolation**: Each task runs in its own session context to prevent state leakage.
- **Structural Reporting**: Extracts coverage, modified files, and test results into unified JSON format.

## Installation

```bash
# From project root
bash install.sh
```

The binary is built to `codeagent-wrapper/codeagent-wrapper` (or `.exe` on Windows).

## Backend Commands

The wrapper routes tasks to the appropriate backend:

| Backend      | Flag                 | Ideal For                                     |
| :----------- | :------------------- | :-------------------------------------------- |
| **Codex**    | `--backend codex`    | Code implementation and refactoring.          |
| **Gemini**   | `--backend gemini`   | Frontend components, styling, UI prototyping. |
| **Claude**   | `--backend claude`   | Architectural reasoning and security audits.  |
| **OpenCode** | `--backend opencode` | Orchestration decisions via local models.     |

## Parallel Execution Format

The orchestrator communicates with the wrapper using structured HEREDOC:

```bash
codeagent-wrapper --parallel <<'EOF'
---TASK---
id: task-001
backend: codex
workdir: ./src
---CONTENT---
Implement a JWT service based on @agent-state.json.

---TASK---
id: task-002
backend: gemini
dependencies: task-001
---CONTENT---
Design a login form that consumes the JWT service.
EOF
```

## Environment Variables

| Variable                | Purpose                                               |
| :---------------------- | :---------------------------------------------------- |
| `CODEX_TIMEOUT`         | Execution timeout in milliseconds (default: 2 hours). |
| `CODEAGENT_NO_TMUX=1`   | Disables terminal progress visualization.             |
| `CODEAGENT_FULL_OUTPUT` | Provides verbose task logs in final report.           |
| `CODEAGENT_WRAPPER`     | Path to wrapper binary (for scripts).                 |

---

_The wrapper bridges AI reasoning and real-world file system mutations._
