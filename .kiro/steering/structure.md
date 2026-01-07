# Project Structure

```
myclaude/
├── codeagent-wrapper/          # Go binary - multi-backend AI executor
│   ├── main.go                 # Entry point, CLI handling
│   ├── backend.go              # Backend interface (Codex/Claude/Gemini)
│   ├── executor.go             # Task execution and parallel processing
│   ├── config.go               # Configuration and argument parsing
│   ├── parser.go               # Output parsing
│   ├── filter.go               # Output filtering
│   ├── logger.go               # Logging utilities
│   └── *_test.go               # Test files (extensive coverage)
│
├── dev-workflow/               # Primary development workflow
│   ├── commands/dev.md         # /dev command definition
│   └── agents/                 # Dev workflow agents
│
├── bmad-agile-workflow/        # Enterprise agile workflow
│   ├── commands/bmad-pilot.md  # /bmad-pilot command
│   └── agents/                 # 6 specialized agents (PO, Architect, SM, Dev, QA, Review)
│
├── requirements-driven-workflow/ # Requirements-to-code pipeline
│   ├── commands/               # /requirements-pilot command
│   └── agents/                 # Requirements agents
│
├── development-essentials/     # Quick development commands
│   ├── commands/               # /code, /debug, /test, /review, etc.
│   └── agents/                 # Supporting agents
│
├── skills/                     # Skill definitions
│   ├── codeagent/SKILL.md      # Main codeagent-wrapper skill
│   ├── codex/SKILL.md          # Codex backend skill
│   ├── gemini/                 # Gemini backend with scripts
│   ├── product-requirements/   # PRD generation skill
│   ├── prototype-prompt-generator/ # UI prototype prompts
│   └── skill-rules.json        # Skill activation triggers
│
├── memorys/CLAUDE.md           # Core role and guidelines
├── hooks/                      # Automation hooks
├── docs/                       # Documentation
│
├── config.json                 # Module installation config
├── config.schema.json          # JSON Schema for config
├── install.py                  # Python installer (recommended)
├── install.sh                  # Legacy bash installer
├── install.bat                 # Windows installer
├── Makefile                    # Build and deployment targets
└── go.work                     # Go workspace configuration
```

## Key Conventions

- **Commands**: Markdown files in `*/commands/` defining slash commands
- **Agents**: Markdown files in `*/agents/` defining agent behaviors
- **Skills**: `SKILL.md` files with frontmatter metadata
- **Tests**: Go test files with `_test.go` suffix, colocated with source
- **Docs**: Markdown files in `docs/` for user documentation
