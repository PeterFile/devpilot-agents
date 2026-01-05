# Tech Stack

## Languages & Runtimes

- **Go 1.21+**: codeagent-wrapper binary (main executor)
- **Python 3**: Installation system (`install.py`)
- **Bash/PowerShell**: Shell scripts for installation and hooks
- **Markdown**: Agent definitions, commands, skills, documentation

## Project Structure

```
codeagent-wrapper/     # Go binary - multi-backend AI executor
├── go.mod             # Go module (go 1.21)
├── main.go            # Entry point
├── backend.go         # Backend interface (Codex/Claude/Gemini)
├── executor.go        # Task execution logic
├── config.go          # CLI parsing and configuration
└── *_test.go          # Test files
```

## Build & Test Commands

### Go (codeagent-wrapper)

```bash
# Build
cd codeagent-wrapper && go build -o codeagent-wrapper .

# Test
cd codeagent-wrapper && go test ./...

# Test with coverage
cd codeagent-wrapper && go test -cover ./...
```

### Installation

```bash
# Full installation (recommended)
python3 install.py --install-dir ~/.claude

# List available modules
python3 install.py --list-modules

# Install specific module
python3 install.py --module dev

# Force overwrite
python3 install.py --force
```

### Makefile Targets

```bash
make deploy-all        # Deploy all commands and agents
make deploy-bmad       # Deploy BMAD workflow only
make deploy-essentials # Deploy development essentials
make changelog         # Update CHANGELOG.md via git-cliff
make clean             # Clean generated artifacts
```

## Dependencies

- **Go**: Standard library only (no external dependencies)
- **Python**: `jsonschema` (optional, for config validation)
- **External CLIs**: `codex`, `claude`, `gemini` (AI backends)

## Configuration

- `config.json`: Module installation configuration
- `config.schema.json`: JSON Schema for validation
- `skills/skill-rules.json`: Skill activation triggers
