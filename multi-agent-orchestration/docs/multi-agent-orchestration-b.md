# Multi-Agent Orchestration 全流程说明

本文档梳理 multi-agent-orchestration 的完整流程、涉及的代码与产物，并说明为什么这一套能稳定生效。

## 目标与核心概念
- 目标：把 Kiro 规格（requirements/design/tasks）转成可执行的多代理任务流，并在实现、审查、修复、同步状态之间形成闭环。
- 关键产物：`TASKS_PARSED.json`（解析结果）、`AGENT_STATE.json`（状态与调度中枢）、`PROJECT_PULSE.md`（对外可读的进度与风险叙事）。
- 执行器：`codeagent-wrapper` 负责并行执行并写回执行结果；Python 脚本负责解析/调度/审查/修复/同步。

## 输入与输出
输入（Spec 目录）：
- `requirements.md`：需求来源。
- `design.md`：架构与心智模型来源。
- `tasks.md`：任务列表与细节；支持依赖、可选项与文件清单。

输出（与 spec 同级或指定输出目录）：
- `TASKS_PARSED.json`：结构化任务清单，供 Codex 决策使用。
- `AGENT_STATE.json`：统一状态机与调度字段的唯一事实来源。
- `PROJECT_PULSE.md`：面向团队的进展、风险、语义锚点。

## 流程主干（从触发到完成）
1) 初始化
- 入口：`multi-agent-orchestration/skill/scripts/init_orchestration.py`
- 作用：校验 spec，解析 tasks，生成三类产物（TASKS_PARSED/AGENT_STATE/PULSE 模板）。

2) Codex 决策补全（必须人工/模型补全）
- 在 `AGENT_STATE.json` 中补全 `owner_agent`、`target_window`、`criticality`。
- 用 `design.md` 填充 `PROJECT_PULSE.md` 的 Mental Model。

3) 调度循环（直到全部完成）
- 批量执行：`dispatch_batch.py`
- 评审派发：`dispatch_reviews.py`
- 同步叙事：`sync_pulse.py`
- 循环条件：`AGENT_STATE.json` 中仍有非 completed 任务。

4) 评审合并与收尾
- `consolidate_reviews.py` 汇总 review_findings，生成 final_reports。
- 通过或进入修复闭环后才进入 completed。

## 关键代码与职责
解析与状态初始化
- `multi-agent-orchestration/skill/scripts/spec_parser.py`
  - 解析 tasks.md（支持父子任务、依赖、_writes/_reads 文件清单）。
  - 依赖展开：父任务依赖被展开为叶子任务依赖。
- `multi-agent-orchestration/skill/scripts/init_orchestration.py`
  - 校验 spec、生成状态骨架；默认不自动分配 agent 与 window。

调度与执行
- `multi-agent-orchestration/skill/scripts/dispatch_batch.py`
  - 只派发叶子任务；依赖必须“严格完成”（status=completed）。
  - 文件冲突检测：对写冲突的任务分批串行化。
  - 调用 `codeagent-wrapper --parallel` 并写回执行结果。
- `codeagent-wrapper/state.go`
  - 原子写回 AGENT_STATE.json，合并执行字段且保留编排字段。
- `codeagent-wrapper/state_validation.go`
  - 保护执行侧状态迁移，防止非法跳转。

评审与修复闭环
- `multi-agent-orchestration/skill/scripts/dispatch_reviews.py`
  - 根据 criticality 派发 1~2 个 Codex review。
  - 评审结果写入 `review_findings`，并推进至 final_review。
- `multi-agent-orchestration/skill/scripts/consolidate_reviews.py`
  - 聚合多 review 结果，写入 final_reports，并决定是否需要 fix loop。
- `multi-agent-orchestration/skill/scripts/fix_loop.py`
  - 重大问题进入 fix_required；阻塞依赖任务。
  - 失败次数达阈值后自动升级到 Codex 或触发人工介入。

叙事与同步
- `multi-agent-orchestration/skill/scripts/sync_pulse.py`
  - 统计进度、阻塞、待决策、技术债，并写回 PULSE 文档。
- `multi-agent-orchestration/skill/references/agent-state-schema.json`
  - 约束 `AGENT_STATE.json` 的结构与可用字段。

## 为什么会有效（核心机制）
1) 单一事实源
- `AGENT_STATE.json` 统一了任务状态、依赖、评审与执行结果，避免多处状态漂移。

2) 严格依赖 + 叶子任务调度
- 依赖只在 completed 后满足，避免“未审即下游开工”的质量风险。
- 父任务只作为聚合器，实际执行仅发生在叶子任务。

3) 文件冲突控制
- 通过 `_writes/_reads` 清单进行写冲突分批，降低并行写导致的竞态与回滚成本。

4) 审查闭环 + 修复升级
- 评审结果进入 fix loop，支持重试、升级、人工介入三阶段，确保高风险变更不会“带病完成”。

5) 原子写回与状态校验
- Go wrapper 原子更新执行结果，保留编排字段，防止脚本结果被覆盖。
- 状态迁移验证为系统提供“护栏”。

6) 叙事同步降低认知负担
- PULSE 持续更新“进展/风险/待决策/语义锚点”，让多代理并行仍能保持可解释性。

## 入口与触发
- Codex CLI：`multi-agent-orchestration/prompts/orchestrate.md`
- Claude Code：`multi-agent-orchestration/commands/orchestrate.md`
- 手动执行：依序运行 `init_orchestration.py` → 决策补全 → `dispatch_batch.py` → `dispatch_reviews.py` → `sync_pulse.py` 循环。

## 备注
- 文档依赖仓内实现：Python 脚本负责编排，Go wrapper 负责执行写回。
- 可用测试位于 `multi-agent-orchestration/skill/scripts/test_*.py`。

## Skill 结构与职责
- `multi-agent-orchestration/skill/SKILL.md`：定义编排器角色、自动化约束与执行循环规则。
- `multi-agent-orchestration/skill/scripts/*.py`：实现解析、调度、评审、修复、同步的主流程能力。
- `multi-agent-orchestration/skill/references/*`：提供状态机与 schema 约束，保证 `AGENT_STATE.json` 与流程一致。

## tmux 与并行执行
### tmux 在流程中的作用
- `codeagent-wrapper --parallel` 会在指定的 tmux session 内为每个任务创建窗口/面板，保证多任务并行、可视化观察与隔离执行。
- `AGENT_STATE.json` 中的 `window_mapping` 记录 task_id 与 tmux window_id 的映射，便于后续状态追溯与跨批次依赖处理。

### 典型启动与派发示例（tmux session = orchestration）
```
codeagent-wrapper --parallel \
  --tmux-session orchestration \
  --state-file /path/to/AGENT_STATE.json \
  <<'EOF'
---TASK---
id: task-001
backend: kiro-cli
workdir: .
target_window: backend
---CONTENT---
Implement user authentication...
EOF
```

### tmux 状态与可视观察建议
- session 命名：与 spec 或功能一致（例如 `orch-my-feature`）。
- window 分组：与 `target_window` 对齐（例如 `setup`/`backend`/`frontend`/`tests`/`verify`）。
- 失败排查：通过 `AGENT_STATE.json` 里的 `window_id`/`pane_id` 迅速定位执行面板。

## Mermaid 流程图
### 主流程与闭环（执行 + 评审 + 修复 + 同步）
```mermaid
flowchart TB
    A[Spec: requirements/design/tasks] --> B[init_orchestration.py]
    B --> C[TASKS_PARSED.json]
    B --> D[AGENT_STATE.json (scaffold)]
    B --> E[PROJECT_PULSE.md (template)]
    C --> F[Codex 决策补全
owner_agent / target_window / criticality]
    D --> F
    F --> G[dispatch_batch.py
codeagent-wrapper --parallel]
    G --> H[Task Execution (tmux panes)]
    H --> I[AGENT_STATE.json
execution fields]
    I --> J[dispatch_reviews.py]
    J --> K[Review Results]
    K --> L[consolidate_reviews.py]
    L --> M{Critical/Major?}
    M -- 否 --> N[completed]
    M -- 是 --> O[fix_loop.py
fix_required]
    O --> G
    I --> P[sync_pulse.py]
    P --> Q[PROJECT_PULSE.md 更新]
```

-b
