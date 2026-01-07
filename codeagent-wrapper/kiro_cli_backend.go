package main

import "strings"

// KiroCliBackend implements the Backend interface for kiro-cli.
type KiroCliBackend struct{}

func (KiroCliBackend) Name() string { return "kiro-cli" }
func (KiroCliBackend) Command() string {
	return "kiro"
}

func (KiroCliBackend) BuildArgs(cfg *Config, targetArg string) []string {
	args := []string{"chat"}
	if cfg != nil && strings.TrimSpace(cfg.WorkDir) != "" && cfg.WorkDir != "." {
		args = append(args, "-C", cfg.WorkDir)
	}
	args = append(args, "--json", targetArg)
	return args
}
