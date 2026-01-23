# AGENTS.md

Multi-agent orchestration framework for complex software engineering tasks.

## Setup commands

- Install skills: `npx skills add PeterFile/devpilot-agents`
- Build wrapper: `cd codeagent-wrapper && go build -o codeagent-wrapper .`
- Run Go tests: `cd codeagent-wrapper && go test -v ./...`
- Run Python tests: `cd skills/multi-agent-orchestration/scripts && python -m pytest -v`

## Project structure

- `skills/multi-agent-orchestration/` - Core orchestration skill with Python scripts
- `skills/kiro-specs/` - Spec-driven workflow skill (requirements → design → tasks)
- `skills/test-driven-development/` - TDD skill
- `codeagent-wrapper/` - Go execution engine for parallel task dispatch
- `.opencode/agents/` - Agent definitions (king-arthur.md, gawain.md)

## Code style

### Go (codeagent-wrapper/)

- Go 1.21+
- Standard library preferred
- Error handling: return errors, don't panic
- Use `go fmt` and `go vet`

### Python (skills/\*/scripts/)

- Python 3.x
- Type hints encouraged
- Use pytest for testing
- Follow existing module patterns

## Testing

- Go: `go test -v ./...` in `codeagent-wrapper/`
- Python: `python -m pytest -v` in script directories
- Integration: `pytest test_e2e_orchestration.py`

## Key files

- `skills/multi-agent-orchestration/SKILL.md` - Orchestrator skill definition
- `skills/multi-agent-orchestration/scripts/orchestration_loop.py` - Main loop runner
- `skills/multi-agent-orchestration/references/agent-state-schema.json` - State schema

## Workflow

The orchestration workflow follows: init → dispatch → review → consolidate → sync

1. Parse Kiro spec (`tasks.md`) into `AGENT_STATE.json`
2. Dispatch tasks to Codex (code) or Gemini (UI) backends
3. Review changes with codex-review
4. Consolidate and sync to `PROJECT_PULSE.md`
