//go:build unix || darwin || linux
// +build unix darwin linux

package main

import (
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

func TestRunCodexTask_SignalHandling(t *testing.T) {
	defer resetTestHooks()
	codexCommand = "sleep"
	buildCodexArgsFn = func(cfg *Config, targetArg string) []string { return []string{"5"} }

	resultCh := make(chan TaskResult, 1)
	go func() { resultCh <- runCodexTask(TaskSpec{Task: "ignored"}, false, 5) }()

	time.Sleep(200 * time.Millisecond)
	syscall.Kill(os.Getpid(), syscall.SIGTERM)

	res := <-resultCh
	signal.Reset(syscall.SIGINT, syscall.SIGTERM)

	if res.ExitCode == 0 || res.Error == "" {
		t.Fatalf("expected non-zero exit after signal, got %+v", res)
	}
}

func TestRun_LoggerRemovedOnSignal(t *testing.T) {
	// Skip in CI due to unreliable signal delivery in containerized environments
	if os.Getenv("CI") != "" || os.Getenv("GITHUB_ACTIONS") != "" {
		t.Skip("Skipping signal test in CI environment")
	}

	defer resetTestHooks()
	defer signal.Reset(syscall.SIGINT, syscall.SIGTERM)

	// Set shorter delays for faster test
	forceKillDelay.Store(1)

	tempDir := t.TempDir()
	t.Setenv("TMPDIR", tempDir)
	logPath := filepath.Join(tempDir, fmt.Sprintf("codeagent-wrapper-%d.log", os.Getpid()))

	scriptPath := filepath.Join(tempDir, "sleepy-codex.sh")
	script := `#!/bin/sh
printf '%s\n' '{"type":"thread.started","thread_id":"sig-thread"}'
sleep 2
printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"late"}}'`
	if err := os.WriteFile(scriptPath, []byte(script), 0o755); err != nil {
		t.Fatalf("failed to write script: %v", err)
	}

	restore := withBackend(scriptPath, buildCodexArgs)
	defer restore()
	isTerminalFn = func() bool { return true }
	stdinReader = strings.NewReader("")
	os.Args = []string{"codeagent-wrapper", "task"}

	exitCh := make(chan int, 1)
	go func() { exitCh <- run() }()

	deadline := time.Now().Add(1 * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(logPath); err == nil {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	_ = syscall.Kill(os.Getpid(), syscall.SIGINT)

	var exitCode int
	select {
	case exitCode = <-exitCh:
	case <-time.After(5 * time.Second):
		t.Fatalf("run() did not return after signal")
	}

	if exitCode != 130 {
		t.Fatalf("exit code = %d, want 130", exitCode)
	}
	// Log file is always removed after completion (new behavior)
	if _, err := os.Stat(logPath); !os.IsNotExist(err) {
		t.Fatalf("log file should be removed after completion")
	}
}
