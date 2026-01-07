package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

func runTmuxMode(cfg *Config, taskText string, useStdin bool) int {
	if cfg == nil {
		logError("tmux mode requires configuration")
		return 1
	}
	if strings.TrimSpace(cfg.TmuxSession) == "" {
		logError("tmux mode requires --tmux-session")
		return 1
	}

	tmuxMgr := NewTmuxManager(TmuxConfig{
		SessionName: cfg.TmuxSession,
		MainWindow:  "main",
		WindowFor:   cfg.WindowFor,
		StateFile:   cfg.StateFile,
	})
	if err := tmuxMgr.EnsureSession(); err != nil {
		logError(err.Error())
		return 1
	}

	var stateWriter *StateWriter
	if strings.TrimSpace(cfg.StateFile) != "" {
		stateWriter = NewStateWriter(cfg.StateFile)
	}

	taskID := generateTaskID()
	taskSpec := TaskSpec{
		ID:        taskID,
		Task:      taskText,
		WorkDir:   cfg.WorkDir,
		Mode:      cfg.Mode,
		SessionID: cfg.SessionID,
		Backend:   cfg.Backend,
		UseStdin:  useStdin,
	}

	runner := newTmuxTaskRunner(tmuxMgr, stateWriter, cfg.IsReview, cfg.WindowFor)
	result := runner.run(taskSpec, cfg.Timeout)

	if result.ExitCode == 0 && result.Message != "" {
		fmt.Println(result.Message)
		if result.SessionID != "" {
			fmt.Printf("\n---\nSESSION_ID: %s\n", result.SessionID)
		}
	}

	if cfg.TmuxAttach {
		_ = attachTmuxSession(cfg.TmuxSession)
	}

	return result.ExitCode
}

func attachTmuxSession(session string) error {
	if strings.TrimSpace(session) == "" {
		return fmt.Errorf("tmux session name is required")
	}
	return execCommand("tmux", "attach", "-t", session)
}

func generateTaskID() string {
	return fmt.Sprintf("task-%d", time.Now().UnixNano())
}

func execCommand(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
