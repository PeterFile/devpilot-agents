# 开发命令参考

> 多代理编排框架的技能和命令。

## 概述

框架使用**技能**，Claude 根据自然语言自动触发。无需斜杠命令 — 只需描述你的需求。

## 核心技能

### multi-agent-orchestrator

从 Kiro 规范编排多代理工作流。

**触发：**

- "Start orchestration from spec at `.kiro/specs/my-feature`"
- "Run orchestration for `<feature-name>`"
- "Execute multi-agent workflow"

**功能：**

1. 解析 Kiro 规范并创建 `AGENT_STATE.json`
2. 将任务分发给 Codex（代码）和 Gemini（UI）执行者
3. 评审和整合变更
4. 同步到 `PROJECT_PULSE.md`

### kiro-specs

规范驱动开发：需求 → 设计 → 任务。

**触发：**

- "Create requirements for..."
- "Draft design for..."
- "Generate implementation tasks"
- 任何提及 `.kiro/specs/`

### test-driven-development

红-绿-重构 TDD 工作流。

**触发：**

- "Help me write tests first"
- "Use TDD for this"
- "Write failing test"

---

## 脚本参考

核心脚本位于 `skills/multi-agent-orchestration/scripts/`：

| 脚本                     | 用途                        |
| ------------------------ | --------------------------- |
| `orchestration_loop.py`  | 主自动循环运行器            |
| `init_orchestration.py`  | 解析规范并构建状态          |
| `dispatch_batch.py`      | 将任务分发给执行者          |
| `dispatch_reviews.py`    | 分发评审任务                |
| `consolidate_reviews.py` | 整合评审发现                |
| `sync_pulse.py`          | 同步状态到 PROJECT_PULSE.md |

---

## 最佳实践

1. **自然语言**：只需描述任务 — 技能自动激活。
2. **明确范围**：使用 `@` 语法引用文件（如 `@src/auth.ts`）。
3. **活动上下文**：技能在 `AGENT_STATE.json` 和 `PROJECT_PULSE.md` 中维护状态。
