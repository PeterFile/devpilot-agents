# Repository Guidelines

## Project Structure & Module Organization
This repo packages a multi-backend workflow system. Key paths:
- `codeagent-wrapper/` Go CLI wrapper (main runtime).
- Workflow packs: `dev-workflow/`, `development-essentials/`, `bmad-agile-workflow/`, `requirements-driven-workflow/` with `commands/` and `agents/`.
- Shared resources: `skills/`, `hooks/`, `scripts/`, `docs/`, `memorys/`.
- Install/config: `install.py`, `install.sh`, `config.json`, `config.schema.json`, `Makefile`.

## Build, Test, and Development Commands
- `python3 install.py --install-dir ~/.claude` installs the default modules.
- `python3 install.py --module dev` installs a single module.
- `make deploy-essentials` or `make deploy-bmad` copies commands/agents into `~/.claude`.
- `go test ./codeagent-wrapper/...` runs Go tests from the repo root (workspace). You can also run `go test ./...` inside `codeagent-wrapper/`.
- `make changelog` updates `CHANGELOG.md` via `git-cliff`.

## Coding Style & Naming Conventions
- Go: format with `gofmt`; keep files in `codeagent-wrapper/` and tests named `*_test.go`.
- Markdown: workflow docs live under `*/commands/` and `*/agents/` using kebab-case filenames (e.g., `bmad-pilot.md`).
- JSON: keep schemas/instances valid; pre-commit uses `jq` for validation.

## Testing Guidelines
- Use `(cd codeagent-wrapper && go test ./... -short)` for quick validation (mirrors `hooks/pre-commit.sh`).
- Add unit tests for new behavior and integration tests when touching CLI orchestration (see `*_integration_test.go` patterns).

## Commit & Pull Request Guidelines
- Follow Conventional Commits with optional scope: `feat(dev-workflow): ...`, `fix: ...`, `docs: ...`.
- PRs should include: concise summary, tests run, and any workflow/module impact; link issues when relevant.
- If you change user-facing commands or install flow, update matching docs in `docs/` or `README.md`.

## Automation & Hooks
- `hooks/pre-commit.sh` checks `gofmt`, runs `go test -short`, and validates JSON.
- Keep hook behavior in sync with repo conventions; update `hooks/hooks-config.json` if adding new hooks.
