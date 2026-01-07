package main

import (
	"fmt"
	"os/exec"
	"strings"
)

// TmuxConfig holds tmux-related configuration.
type TmuxConfig struct {
	SessionName string
	MainWindow  string
	WindowFor   string
	StateFile   string
}

// TmuxManager manages tmux sessions, windows, and panes.
type TmuxManager struct {
	config TmuxConfig
}

// Test hooks for tmux command execution.
var (
	tmuxHasSessionFn = func(session string) bool {
		if strings.TrimSpace(session) == "" {
			return false
		}
		cmd := exec.Command("tmux", "has-session", "-t", session)
		return cmd.Run() == nil
	}
	tmuxCommandFn = func(args ...string) (string, error) {
		cmd := exec.Command("tmux", args...)
		output, err := cmd.CombinedOutput()
		out := strings.TrimSpace(string(output))
		if err != nil {
			if out == "" {
				return "", fmt.Errorf("tmux %s failed: %w", strings.Join(args, " "), err)
			}
			return "", fmt.Errorf("tmux %s failed: %s: %w", strings.Join(args, " "), out, err)
		}
		return out, nil
	}
)

// NewTmuxManager creates a new manager with defaults applied.
func NewTmuxManager(cfg TmuxConfig) *TmuxManager {
	if strings.TrimSpace(cfg.MainWindow) == "" {
		cfg.MainWindow = "main"
	}
	return &TmuxManager{config: cfg}
}

// SessionExists checks if the tmux session exists.
func (tm *TmuxManager) SessionExists() bool {
	if tm == nil {
		return false
	}
	return tmuxHasSessionFn(tm.config.SessionName)
}

// EnsureSession creates the tmux session with a main window if needed.
func (tm *TmuxManager) EnsureSession() error {
	if tm == nil {
		return fmt.Errorf("tmux manager is nil")
	}
	if strings.TrimSpace(tm.config.SessionName) == "" {
		return fmt.Errorf("tmux session name is required")
	}
	if tm.SessionExists() {
		return nil
	}
	if _, err := tmuxCommandFn(
		"new-session",
		"-d",
		"-s", tm.config.SessionName,
		"-n", tm.config.MainWindow,
	); err != nil {
		return err
	}
	_, _ = tmuxCommandFn(
		"split-window",
		"-t", fmt.Sprintf("%s:%s", tm.config.SessionName, tm.config.MainWindow),
	)
	return nil
}

// CreateWindow creates a new tmux window for a task.
func (tm *TmuxManager) CreateWindow(taskID string) (string, error) {
	if tm == nil {
		return "", fmt.Errorf("tmux manager is nil")
	}
	taskID = strings.TrimSpace(taskID)
	if taskID == "" {
		return "", fmt.Errorf("task id is required")
	}
	output, err := tmuxCommandFn(
		"new-window",
		"-t", tm.config.SessionName,
		"-n", taskID,
		"-P", "-F", "#{window_id}",
	)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(output), nil
}

// CreatePane creates a new pane in an existing window.
func (tm *TmuxManager) CreatePane(targetWindow string) (string, error) {
	if tm == nil {
		return "", fmt.Errorf("tmux manager is nil")
	}
	targetWindow = strings.TrimSpace(targetWindow)
	if targetWindow == "" {
		return "", fmt.Errorf("target window is required")
	}
	target := fmt.Sprintf("%s:%s", tm.config.SessionName, targetWindow)
	output, err := tmuxCommandFn(
		"split-window",
		"-t", target,
		"-P", "-F", "#{pane_id}",
	)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(output), nil
}

// SendCommand sends a command to a target pane or window.
func (tm *TmuxManager) SendCommand(target string, command string) error {
	if tm == nil {
		return fmt.Errorf("tmux manager is nil")
	}
	target = strings.TrimSpace(target)
	if target == "" {
		return fmt.Errorf("target is required")
	}
	_, err := tmuxCommandFn(
		"send-keys",
		"-t", target,
		command,
		"Enter",
	)
	return err
}

// SetupTaskPanes creates windows or panes for a batch of tasks.
// It returns a task-to-window mapping.
func (tm *TmuxManager) SetupTaskPanes(tasks []TaskSpec) (map[string]string, error) {
	if tm == nil {
		return nil, fmt.Errorf("tmux manager is nil")
	}
	taskToWindow := make(map[string]string, len(tasks))

	for _, task := range tasks {
		taskID := strings.TrimSpace(task.ID)
		if taskID == "" {
			return nil, fmt.Errorf("task id is required")
		}
		if len(task.Dependencies) == 0 {
			if _, err := tm.CreateWindow(taskID); err != nil {
				return nil, err
			}
			taskToWindow[taskID] = taskID
			continue
		}

		depID := strings.TrimSpace(task.Dependencies[0])
		window, ok := taskToWindow[depID]
		if !ok {
			return nil, fmt.Errorf("dependency window not found for task %q", taskID)
		}
		if _, err := tm.CreatePane(window); err != nil {
			return nil, err
		}
		taskToWindow[taskID] = window
	}

	return taskToWindow, nil
}
