package main

import "strings"

// KiroCliBackend implements the Backend interface for kiro-cli.
// Kiro CLI chat command reference: https://kiro.dev/docs/cli/reference/cli-commands
//
// Usage: kiro chat [OPTIONS] [INPUT]
// Key options:
//   --no-interactive: Print first response to STDOUT without interactive mode
//   --trust-all-tools: Allow the model to use any tool without confirmation
//   --json: Output in JSON format
//   INPUT: The first question to ask (positional argument), use "-" to read from stdin
type KiroCliBackend struct{}

func (KiroCliBackend) Name() string { return "kiro-cli" }
func (KiroCliBackend) Command() string {
	return "kiro-cli"
}

func (KiroCliBackend) BuildArgs(cfg *Config, targetArg string) []string {
	args := []string{"chat", "--no-interactive", "--trust-all-tools"}
	if cfg != nil && strings.TrimSpace(cfg.WorkDir) != "" && cfg.WorkDir != "." {
		args = append(args, "-C", cfg.WorkDir)
	}
	// kiro-cli chat takes INPUT as positional argument directly
	// The prompt is always passed as the final positional argument
	if targetArg != "" {
		args = append(args, targetArg)
	}
	return args
}

// SupportsStdin returns false because kiro-cli does not support stdin input.
// The prompt must be passed as a positional argument.
func (KiroCliBackend) SupportsStdin() bool {
	return false
}
