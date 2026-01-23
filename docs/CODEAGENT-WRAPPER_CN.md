中文 | [English](CODEAGENT-WRAPPER.md)

# codeagent-wrapper：执行引擎

多代理编排框架的 Go 运行时。提供统一的跨平台接口，用于跨多个 AI 后端的并行代码执行。

## 系统中的角色

在编排循环中，`codeagent-wrapper` 充当**执行层**：

- **并行分发**：解析任务依赖并同时执行独立任务。
- **后端隔离**：每个任务在自己的会话上下文中运行，防止状态泄漏。
- **结构化报告**：将覆盖率、修改的文件和测试结果提取为统一的 JSON 格式。

## 安装

```bash
# 从项目根目录
cd codeagent-wrapper
go build -o codeagent-wrapper .
```

二进制文件生成在 `codeagent-wrapper/codeagent-wrapper`（Windows 上为 `.exe`）。

## 后端命令

wrapper 将任务路由到适当的后端：

| 后端         | 标志                 | 适用于                   |
| ------------ | -------------------- | ------------------------ |
| **Codex**    | `--backend codex`    | 代码实现和重构           |
| **Gemini**   | `--backend gemini`   | 前端组件、样式、UI 原型  |
| **Claude**   | `--backend claude`   | 架构推理和安全审计       |
| **OpenCode** | `--backend opencode` | 通过本地模型进行编排决策 |

## 并行执行格式

编排器使用结构化 HEREDOC 与 wrapper 通信：

```bash
codeagent-wrapper --parallel <<'EOF'
---TASK---
id: task-001
backend: codex
workdir: ./src
---CONTENT---
基于 @agent-state.json 实现 JWT 服务。

---TASK---
id: task-002
backend: gemini
dependencies: task-001
---CONTENT---
设计一个使用 JWT 服务的登录表单。
EOF
```

## 环境变量

| 变量                    | 用途                                 |
| ----------------------- | ------------------------------------ |
| `CODEX_TIMEOUT`         | 执行超时（毫秒，默认：2 小时）       |
| `CODEAGENT_NO_TMUX=1`   | 禁用终端进度可视化                   |
| `CODEAGENT_FULL_OUTPUT` | 在最终报告中提供详细任务日志         |
| `CODEAGENT_WRAPPER`     | wrapper 二进制文件路径（供脚本使用） |

---

_wrapper 是 AI 推理与现实世界文件系统变更之间的桥梁。_
