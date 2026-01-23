# Multi-Agent Orchestration Makefile

.PHONY: help build test clean changelog

help:
	@echo "Multi-Agent Orchestration Framework"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build      - Build codeagent-wrapper binary"
	@echo "  test       - Run all tests"
	@echo "  test-go    - Run Go tests for codeagent-wrapper"
	@echo "  test-py    - Run Python tests for orchestration scripts"
	@echo "  clean      - Clean build artifacts"
	@echo "  changelog  - Update CHANGELOG.md using git-cliff"
	@echo "  help       - Show this help message"

# Build codeagent-wrapper
build:
	@echo "Building codeagent-wrapper..."
	@cd codeagent-wrapper && go build -o codeagent-wrapper .
	@echo "✅ Build complete: codeagent-wrapper/codeagent-wrapper"

# Run all tests
test: test-go test-py

# Run Go tests
test-go:
	@echo "Running Go tests..."
	@cd codeagent-wrapper && go test -v ./...

# Run Python tests
test-py:
	@echo "Running Python tests..."
	@cd skills/multi-agent-orchestration/scripts && python -m pytest -v

# Clean build artifacts
clean:
	@echo "Cleaning artifacts..."
	@rm -f codeagent-wrapper/codeagent-wrapper
	@rm -f codeagent-wrapper/codeagent-wrapper.exe
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned!"

# Update CHANGELOG.md using git-cliff
changelog:
	@echo "Updating CHANGELOG.md..."
	@if ! command -v git-cliff > /dev/null 2>&1; then \
		echo "❌ git-cliff not found. Install: cargo install git-cliff"; \
		exit 1; \
	fi
	@git-cliff -o CHANGELOG.md
	@echo "✅ CHANGELOG.md updated!"
