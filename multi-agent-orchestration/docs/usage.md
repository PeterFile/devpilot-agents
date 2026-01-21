# 使用指南

## 适用范围

该流程用于把 spec 目录（requirements.md/design.md/tasks.md）转成可执行的多代理任务流。代码任务由 codex 执行，UI 任务由 gemini 执行，review 任务由 codex-review 执行。

## 前置条件

- Python 3.x
- codeagent-wrapper（建议在 PATH；或设置 `CODEAGENT_WRAPPER=/path/to/codeagent-wrapper`）
- tmux（可选；无 tmux 或权限受限时设置 `CODEAGENT_NO_TMUX=1`）

## 常用环境变量

- `CODEAGENT_WRAPPER` / `CODEAGENT_WRAPPER_PATH`：指定 `codeagent-wrapper` 可执行文件路径（覆盖 PATH/本地探测）
- `CODEAGENT_NO_TMUX=1`：禁用 tmux 可视化（`dispatch_batch.py` / `dispatch_reviews.py` 会自动回退）
- `CODEAGENT_FULL_OUTPUT=1`：让 `codeagent-wrapper --parallel` 输出更完整的 JSON 报告（可能更慢/更大）

## 快速开始

注：Skill 安装后脚本位于 `~/.codex/skills/<skill>/scripts/` 或 `~/.claude/skills/<skill>/scripts/`；本仓库源代码位于 `multi-agent-orchestration/skill/scripts/`。

### 1) 初始化

运行：

```bash
python multi-agent-orchestration/skill/scripts/init_orchestration.py <spec_path> --session roundtable --mode codex --json
```

拿到输出中的：
- AGENT_STATE.json
- TASKS_PARSED.json
- PROJECT_PULSE.md

### 1b) 一键自动循环（llm，默认，推荐给 opencode CLI）

该模式每轮通过 `codeagent-wrapper` 启动一次“全新 orchestrator”（默认 `--backend opencode`），读取 state/pulse/tasks 并输出本轮 actions（JSON），适合更动态的决策与恢复。

从 spec 一键启动：

```bash
python multi-agent-orchestration/skill/scripts/orchestration_loop.py --spec <spec_path> --workdir . --assign-backend codex --max-iterations 50 --sleep 1
```

从已有 state 恢复：

```bash
python multi-agent-orchestration/skill/scripts/orchestration_loop.py --state AGENT_STATE.json --pulse PROJECT_PULSE.md --tasks TASKS_PARSED.json --workdir . --assign-backend codex
```

默认值：
- `--mode llm --backend opencode`
- 如需指定 agent：设置 `CODEAGENT_OPENCODE_AGENT=<agent_name>`

### 1c) 固定顺序循环（deterministic）

该模式以固定顺序循环执行：`assign_dispatch(如需要) -> dispatch_batch -> dispatch_reviews -> consolidate_reviews -> sync_pulse`，直到所有 **Dispatch Unit** 完成或出现 `pending_decisions`（需要人工）。

从 spec 一键启动：

```bash
python multi-agent-orchestration/skill/scripts/orchestration_loop.py --spec <spec_path> --workdir . --mode deterministic --assign-backend codex --max-iterations 50 --sleep 1
```

从已有 state 恢复：

```bash
python multi-agent-orchestration/skill/scripts/orchestration_loop.py --state AGENT_STATE.json --pulse PROJECT_PULSE.md --tasks TASKS_PARSED.json --workdir . --mode deterministic --assign-backend codex
```

退出码：
- `0`：所有 Dispatch Unit 已完成
- `1`：停止/未完成（max iterations/no progress/显式 halt 等）
- `2`：存在 `pending_decisions`（需要人工输入）

SECURITY: 该循环会自动执行 `codeagent-wrapper` 和任务脚本，可能修改大量文件；建议先在独立分支运行。

### 2) 填写调度决策

通常不需要手工：在 `orchestration_loop.py`（deterministic/llm）且存在 `TASKS_PARSED.json` 时，会自动生成并写回 Dispatch Unit 的 `owner_agent/target_window/criticality/writes/reads`。本节仅用于调试或手工覆盖。

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
python -c "import json; d=json.load(open('AGENT_STATE.json')); tasks=d.get('tasks',[]); units=[t for t in tasks if t.get('subtasks') or (not t.get('parent_id') and not t.get('subtasks'))]; incomplete=[t for t in units if t.get('status')!='completed']; print(f'Incomplete dispatch units: {len(incomplete)}/{len(units)}')"
```

## 并行执行规则

- writes 不冲突的任务可并行
- 没有 writes/reads 的任务默认串行

## 常见问题

- 报错缺少 owner_agent/target_window：回到第 2 步补全 Dispatch Unit 字段
- codeagent-wrapper 找不到：确认已安装且在 PATH 中；或设置 `CODEAGENT_WRAPPER` 指向二进制
- tmux 报错（连接 /tmp/tmux、权限问题、无 tmux）：设置 `CODEAGENT_NO_TMUX=1`
