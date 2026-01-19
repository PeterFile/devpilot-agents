# 使用指南

## 适用范围

该流程用于把 spec 目录（requirements.md/design.md/tasks.md）转成可执行的多代理任务流。代码任务由 codex 执行，UI 任务由 gemini 执行，review 任务由 codex-review 执行。

## 前置条件

- Python 3.x
- codeagent-wrapper
- tmux（Linux/macOS）

## 快速开始

### 1) 初始化

运行：

```bash
python multi-agent-orchestration/skill/scripts/init_orchestration.py <spec_path> --session orchestration --mode codex --json
```

拿到输出中的：
- AGENT_STATE.json
- TASKS_PARSED.json
- PROJECT_PULSE.md

### 2) 填写调度决策

只为 **Dispatch Unit** 填写字段（有 subtasks 的 parent task，或无 parent 且无 subtasks 的 standalone task）。

先用 `codeagent-wrapper` 生成调度字段（必须）：

```bash
codeagent-wrapper --backend codex - <<'EOF'
You are generating dispatch assignments for multi-agent orchestration.

Inputs:
- @AGENT_STATE.json
- @TASKS_PARSED.json

Rules:
- Only assign Dispatch Units (parent tasks or standalone tasks).
- Do NOT assign leaf tasks with parents.
- owner_agent: codex | gemini | codex-review
- target_window: task-<task_id> or grouped names (max 9)
- criticality: standard | complex | security-sensitive
- writes/reads: list of files (best-effort)

Output JSON only:
{
  "dispatch_units": [
    {
      "task_id": "1",
      "owner_agent": "codex",
      "target_window": "task-1",
      "criticality": "standard",
      "writes": ["src/example.py"],
      "reads": ["src/config.py"]
    }
  ],
  "window_mapping": {
    "1": "task-1"
  }
}
EOF
```

把输出结果写回 AGENT_STATE.json，然后继续下述字段检查。

必填字段：
- owner_agent：`codex`（code）、`gemini`（UI）、`codex-review`（review）
- target_window：每个 Dispatch Unit 一个 window（最多 9 个）
- criticality：`standard` / `complex` / `security-sensitive`

建议字段：
- writes：该任务会修改的文件列表
- reads：该任务会读取但不修改的文件列表

示例：

```json
{
  "task_id": "1",
  "owner_agent": "codex",
  "target_window": "backend",
  "criticality": "standard",
  "writes": ["src/api/auth.py"],
  "reads": ["src/config.py"]
}
```

### 3) 调度循环

```bash
python multi-agent-orchestration/skill/scripts/dispatch_batch.py AGENT_STATE.json
python multi-agent-orchestration/skill/scripts/dispatch_reviews.py AGENT_STATE.json
python multi-agent-orchestration/skill/scripts/consolidate_reviews.py AGENT_STATE.json
python multi-agent-orchestration/skill/scripts/sync_pulse.py AGENT_STATE.json PROJECT_PULSE.md
```

检查是否完成（未完成则重复调度循环）：

```bash
python -c "import json; d=json.load(open('AGENT_STATE.json')); tasks=d['tasks']; incomplete=[t for t in tasks if t.get('status')!='completed']; print(f'Incomplete: {len(incomplete)}/{len(tasks)}')"
```

## 并行执行规则

- writes 不冲突的任务可并行
- 没有 writes/reads 的任务默认串行

## 常见问题

- 报错缺少 owner_agent/target_window：回到第 2 步补全 Dispatch Unit 字段
- codeagent-wrapper 找不到：确认已安装且在 PATH 中
