[中文版](QUICK-START_CN.md) | English

# Quick Start Guide

> Get started with the Multi-Agent Orchestration Framework.

## Prerequisites

| Dependency               | Version | Purpose                 |
| ------------------------ | ------- | ----------------------- |
| **Node.js**              | 18+     | Run `npx skills add`    |
| **Python**               | 3.9+    | Orchestration scripts   |
| **Go**                   | 1.21+   | Build codeagent-wrapper |
| **Claude Code/OpenCode** | Latest  | Trigger skills          |

## Installation

### Step 1: Install Skills

```bash
npx skills add PeterFile/devpilot-agents
```

### Step 2: Build codeagent-wrapper

```bash
git clone https://github.com/PeterFile/devpilot-agents.git
cd devpilot-agents/codeagent-wrapper
go build -o codeagent-wrapper .
```

Verify:

```bash
./codeagent-wrapper --version
# Output: codeagent-wrapper version 5.4.0
```

### Step 3: Add to PATH

```bash
export PATH="$PWD:$PATH"
```

---

## Using Skills

Open Claude Code or OpenCode, then describe your task:

### Multi-Agent Orchestrator

**Triggers:**

- "Start orchestration from spec at `.kiro/specs/my-feature`"
- "Run orchestration for `user-authentication`"

### Kiro Specs

**Triggers:**

- "Create requirements for a new feature"
- "Draft design for `api-gateway`"

### Test-Driven Development

**Triggers:**

- "Help me write tests first"
- "Use TDD for this feature"

---

## Verification Checklist

| Check         | Command                         |
| ------------- | ------------------------------- |
| Go installed  | `go version`                    |
| Wrapper built | `./codeagent-wrapper --version` |

**You're ready!** Describe your task in natural language.
