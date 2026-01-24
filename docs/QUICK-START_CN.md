中文 | [English](QUICK-START.md)

# 快速入门指南

> 快速上手多代理编排框架。

## 前置要求

| 依赖项                   | 版本   | 用途                   |
| ------------------------ | ------ | ---------------------- |
| **Node.js**              | 18+    | 运行 `npx skills add`  |
| **Python**               | 3.9+   | 编排脚本               |
| **Go**                   | 1.21+  | 编译 codeagent-wrapper |
| **Claude Code/OpenCode** | 最新版 | 触发技能               |

## 安装步骤

### 步骤 1：安装技能

```bash
npx skills add PeterFile/devpilot-agents
```

### 步骤 2：编译 codeagent-wrapper

```bash
git clone https://github.com/PeterFile/devpilot-agents.git
cd devpilot-agents/codeagent-wrapper
go build -o codeagent-wrapper .
```

验证：

```bash
./codeagent-wrapper --version
# 输出: codeagent-wrapper version 5.4.0
```

### 步骤 3：添加到 PATH

```bash
export PATH="$PWD:$PATH"
```

---

## 使用技能

打开 Claude Code 或 OpenCode，然后描述你的任务：

### 多代理编排器

**触发：**

- "Start orchestration from spec at `.kiro/specs/my-feature`"
- "Run orchestration for `user-authentication`"

### Kiro 规范

**触发：**

- "Create requirements for a new feature"
- "Draft design for `api-gateway`"

### 测试驱动开发

**触发：**

- "Help me write tests first"
- "Use TDD for this feature"

---

## 验证清单

| 检查           | 命令                            |
| -------------- | ------------------------------- |
| Go 已安装      | `go version`                    |
| Wrapper 已编译 | `./codeagent-wrapper --version` |

**准备就绪！** 用自然语言描述你的任务。
