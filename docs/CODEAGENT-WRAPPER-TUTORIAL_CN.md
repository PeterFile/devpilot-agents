# codeagent-wrapper 编译与使用教程

本教程覆盖：从源码编译 `codeagent-wrapper`，到用它执行单任务、stdin、多任务并行（`--parallel`）与会话续跑（`resume`）。

## 前置条件

- Go 1.21+（本仓库 `go.work` / `codeagent-wrapper/go.mod`）
- 至少安装一个 backend CLI：`codex` / `claude` / `gemini`
- （可选）`tmux`：仅在 `--tmux-session` 模式需要（常用于 `multi-agent-orchestration`）

验证：

```powershell
go version
```

## 编译（Windows / PowerShell）

在仓库根目录运行：

```powershell
cd codeagent-wrapper
go build -o ..\bin\codeagent-wrapper.exe .
..\bin\codeagent-wrapper.exe --version
```

## 编译（Linux / macOS）

在仓库根目录运行：

```bash
cd codeagent-wrapper
go build -o ../bin/codeagent-wrapper .
../bin/codeagent-wrapper --version
```

## 放到 PATH（可选）

让脚本直接找到 `codeagent-wrapper`（例如 `multi-agent-orchestration` 会调用它）。

- Windows：把 `bin\codeagent-wrapper.exe` 放进 `%USERPROFILE%\bin\`，并把该目录加到 `PATH`
- Linux/macOS：把 `bin/codeagent-wrapper` 放进 `~/.local/bin/` 或 `~/.claude/bin/`，并把该目录加到 `PATH`

## 基础用法（单任务）

语法：

- `codeagent-wrapper "task" [workdir]`
- `codeagent-wrapper - [workdir]`（从 stdin 读任务）
- `codeagent-wrapper --backend codex|claude|gemini "task" [workdir]`

PowerShell 示例（stdin）：

```powershell
@'
解释一下这个仓库的结构，并指出入口文件：
- @README.md
- @go.work
'@ | .\bin\codeagent-wrapper.exe --backend codex -
```

指定工作目录：

```powershell
.\bin\codeagent-wrapper.exe "run tests" "E:\path\to\project"
```

## --parallel（并行执行多个任务）

`--parallel` 从 stdin 读取配置。每个任务块格式：

- `---TASK---` 开始
- meta 行（可选字段）：`id:`（必填）、`workdir:`、`backend:`、`dependencies:`（逗号分隔）、`session_id:`（触发 resume）、`target_window:`（tmux 分窗）
- `---CONTENT---` 后面是任务正文

PowerShell 示例：

```powershell
@'
---TASK---
id: api
workdir: E:\repo\backend
backend: codex
---CONTENT---
实现 /api/health，返回 JSON

---TASK---
id: ui
workdir: E:\repo\frontend
backend: gemini
dependencies: api
---CONTENT---
加一个页面展示 /api/health 的返回值
'@ | .\bin\codeagent-wrapper.exe --parallel
```

说明：

- 无依赖任务会并行；有依赖的任务会等待
- 依赖任务失败时，下游任务会被阻塞/跳过（不会强行继续）
- 需要完整输出调试时用 `--full-output`
- 并发上限可用 `CODEAGENT_MAX_PARALLEL_WORKERS` 控制（不设置=不限制；上限 100，超过会被 cap）

## resume（会话续跑，不是 retry）

`resume` 不是自动重试机制；它是“继续同一个 backend 会话/线程”的显式操作。

用法：

```powershell
.\bin\codeagent-wrapper.exe resume <session_id> "继续这个任务：补充单元测试"
```

`--parallel` 里也可以在 meta 区写 `session_id: <session_id>`，该任务会走 resume。

## Codex Skills 与 Prompts（本项目会用到）

### Skills（可复用能力包）

Codex 会递归扫描 `~/.codex/skills/**/SKILL.md` 加载 Skills。

使用方式：

- 在对话里引用：`$skill-name`
- 在 Codex TUI 里输入 `/skills` 浏览并插入

安装本项目的 orchestrator skill（示例）：

```bash
mkdir -p ~/.codex/skills/multi-agent-orchestrator
cp -R multi-agent-orchestration/skill/* ~/.codex/skills/multi-agent-orchestrator/
```

PowerShell 等价命令：

```powershell
$CodexHome = Join-Path $HOME ".codex"
$SkillDir = Join-Path $CodexHome "skills\\multi-agent-orchestrator"
New-Item -ItemType Directory -Force $SkillDir | Out-Null
Copy-Item -Recurse -Force "multi-agent-orchestration\\skill\\*" $SkillDir
```

修改/新增 skill 后，重启 Codex 让它重新扫描加载。

### Prompts（自定义 slash commands）

Codex 支持把可复用 Prompt 做成 `/prompts:<name>` 命令：把 Markdown 文件放到 `~/.codex/prompts/`。

文件格式要点：

- YAML frontmatter：`description`（必填），`argument-hint`（可选）
- Prompt 正文里可用 `$VAR` 占位符；调用时传参替换

安装并调用本项目的 `/prompts:orchestrate`：

```bash
mkdir -p ~/.codex/prompts
cp multi-agent-orchestration/prompts/orchestrate.md ~/.codex/prompts/
```

PowerShell 等价命令：

```powershell
$CodexHome = Join-Path $HOME ".codex"
$PromptsDir = Join-Path $CodexHome "prompts"
New-Item -ItemType Directory -Force $PromptsDir | Out-Null
Copy-Item -Force "multi-agent-orchestration\\prompts\\orchestrate.md" (Join-Path $PromptsDir "orchestrate.md")
```

在 Codex TUI 里执行：

```text
/prompts:orchestrate SPEC_PATH=.kiro/specs/my-feature
```

## 常见问题

### backend 找不到（exit code 127）

确保对应 CLI 在 `PATH` 里：

```powershell
codex --version
claude --version
gemini --version
```

### 超时（exit code 124）

`CODEX_TIMEOUT` 控制单次任务超时（推荐按毫秒设置）：

```powershell
$env:CODEX_TIMEOUT = "3600000"  # 1h
.\bin\codeagent-wrapper.exe "run tests"
```

### 查看日志

每个任务都会写一份 log 到系统临时目录（例如 Windows 的 `%TEMP%`）。
并行模式的 JSON 报告里也会带 `log_path`，用于定位失败原因。

### 🔒 Sandbox / 权限限制

如果你需要绕过 sandbox/权限（只建议在受信环境）：

- `CODEX_BYPASS_SANDBOX=true`（影响 `codex` 子进程参数）
- `CODEAGENT_SKIP_PERMISSIONS=true`（跳过 wrapper 侧的权限检查）

### Windows 跑测试失败

在 Windows 上，`go test ./... -short` 可能因为缺少类 Unix 命令（例如 `echo`）、symlink 权限等原因失败。
优先用 `go build` + `codeagent-wrapper --help/--version` 做基础验证；需要完整测试建议在 Linux/WSL 运行。
