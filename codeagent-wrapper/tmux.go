package main

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
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
	mu     sync.Mutex
	// tracked task windows (excludes main window)
	windowNames     map[string]bool
	windowCount     int
	windowCacheInit bool
	sessionID       string
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

const (
	sessionReadyChecks    = 20
	sessionReadyDelay     = 100 * time.Millisecond
	sessionReadyExtraWait = 50 * time.Millisecond
	MaxTaskWindows        = 9
)

// NewTmuxManager creates a new manager with defaults applied.
func NewTmuxManager(cfg TmuxConfig) *TmuxManager {
	if strings.TrimSpace(cfg.MainWindow) == "" {
		cfg.MainWindow = "main"
	}
	return &TmuxManager{
		config:      cfg,
		windowNames: make(map[string]bool),
	}
}

// SessionExists checks if the tmux session exists.
func (tm *TmuxManager) SessionExists() bool {
	if tm == nil {
		return false
	}
	tm.mu.Lock()
	defer tm.mu.Unlock()
	_, exists, _ := tm.resolveSessionTargetLocked()
	return exists
}

// EnsureSession creates the tmux session with a main window if needed.
func (tm *TmuxManager) EnsureSession() error {
	if tm == nil {
		return fmt.Errorf("tmux manager is nil")
	}
	if strings.TrimSpace(tm.config.SessionName) == "" {
		return fmt.Errorf("tmux session name is required")
	}
	tm.mu.Lock()
	defer tm.mu.Unlock()
	target, exists, err := tm.resolveSessionTargetLocked()
	if err != nil {
		return err
	}
	if exists {
		tm.windowCacheInit = false
		if err := tm.ensureSessionOptionsLocked(target); err != nil {
			return err
		}
		return nil
	}
	output, err := tmuxCommandFn(
		"new-session",
		"-d",
		"-P",
		"-F", "#{session_id}\t#{window_id}",
		"-s", tm.config.SessionName,
		"-n", tm.config.MainWindow,
	)
	if err != nil {
		return err
	}
	sessionID, mainWindowID := parseNewSessionOutput(output)
	if sessionID != "" {
		tm.sessionID = sessionID
	}
	target = tm.sessionTargetLocked()
	if err := waitForSessionReady(target); err != nil {
		return err
	}
	tm.windowCacheInit = false
	_ = tm.ensureSessionOptionsLocked(target)
	splitTarget := mainWindowID
	if strings.TrimSpace(splitTarget) == "" {
		splitTarget = fmt.Sprintf("%s:%s", target, tm.config.MainWindow)
	}
	_, _ = tmuxCommandFn("split-window", "-t", splitTarget)
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
	tm.mu.Lock()
	defer tm.mu.Unlock()
	output, err := tmuxCommandFn(
		"new-window",
		"-t", tm.sessionTargetLocked(),
		"-n", taskID,
		"-P", "-F", "#{window_id}",
	)
	if err != nil {
		return "", err
	}
	if !tm.windowNames[taskID] && taskID != tm.config.MainWindow {
		tm.windowNames[taskID] = true
		tm.windowCount++
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
	tm.mu.Lock()
	defer tm.mu.Unlock()
	target := fmt.Sprintf("%s:%s", tm.sessionTargetLocked(), targetWindow)
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
	tm.mu.Lock()
	defer tm.mu.Unlock()
	_, err := tmuxCommandFn(
		"send-keys",
		"-t", target,
		command,
		"Enter",
	)
	return err
}

func waitForSessionReady(target string) error {
	for i := 0; i < sessionReadyChecks; i++ {
		if tmuxHasSessionFn(target) {
			time.Sleep(sessionReadyExtraWait)
			return nil
		}
		time.Sleep(sessionReadyDelay)
	}
	return fmt.Errorf("session %s not ready after creation", target)
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
		if strings.TrimSpace(task.TargetWindow) != "" {
			windowName, created, err := tm.GetOrCreateWindow(task.TargetWindow)
			if err != nil {
				return nil, err
			}
			if !created {
				if _, err := tm.CreatePane(windowName); err != nil {
					return nil, err
				}
			}
			taskToWindow[taskID] = windowName
			continue
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

// SessionTarget returns the tmux target identifier for this manager.
func (tm *TmuxManager) SessionTarget() string {
	if tm == nil {
		return ""
	}
	tm.mu.Lock()
	defer tm.mu.Unlock()
	return tm.sessionTargetLocked()
}

// GetOrCreateWindow returns the window name and whether it was created.
func (tm *TmuxManager) GetOrCreateWindow(windowName string) (string, bool, error) {
	if tm == nil {
		return "", false, fmt.Errorf("tmux manager is nil")
	}
	windowName = strings.TrimSpace(windowName)
	if windowName == "" {
		return "", false, fmt.Errorf("target window is required")
	}
	tm.mu.Lock()
	defer tm.mu.Unlock()

	if windowName == tm.config.MainWindow {
		return windowName, false, nil
	}
	if err := tm.ensureWindowCacheLocked(); err != nil {
		return "", false, err
	}
	if tm.windowNames[windowName] {
		return windowName, false, nil
	}
	if tm.windowCount >= MaxTaskWindows {
		return "", false, fmt.Errorf("max window limit (%d) reached", MaxTaskWindows)
	}
	if _, err := tmuxCommandFn(
		"new-window",
		"-t", tm.sessionTargetLocked(),
		"-n", windowName,
		"-P", "-F", "#{window_id}",
	); err != nil {
		return "", false, err
	}
	tm.windowNames[windowName] = true
	tm.windowCount++
	return windowName, true, nil
}

func (tm *TmuxManager) ensureWindowCacheLocked() error {
	if tm.windowCacheInit {
		return nil
	}
	output, err := tmuxCommandFn(
		"list-windows",
		"-t", tm.sessionTargetLocked(),
		"-F", "#{window_name}",
	)
	if err != nil {
		return err
	}
	tm.windowNames = make(map[string]bool)
	tm.windowCount = 0
	for _, line := range strings.Split(strings.TrimSpace(output), "\n") {
		name := strings.TrimSpace(line)
		if name == "" || name == tm.config.MainWindow {
			continue
		}
		if !tm.windowNames[name] {
			tm.windowNames[name] = true
			tm.windowCount++
		}
	}
	tm.windowCacheInit = true
	return nil
}

func (tm *TmuxManager) sessionTargetLocked() string {
	if strings.TrimSpace(tm.sessionID) != "" {
		return tm.sessionID
	}
	return tm.config.SessionName
}

func (tm *TmuxManager) resolveSessionTargetLocked() (string, bool, error) {
	if tm.sessionID != "" {
		if tmuxHasSessionFn(tm.sessionID) {
			return tm.sessionID, true, nil
		}
		tm.sessionID = ""
	}
	name := strings.TrimSpace(tm.config.SessionName)
	if name == "" {
		return "", false, fmt.Errorf("tmux session name is required")
	}
	if tmuxHasSessionFn(name) {
		if sessionID := tm.lookupSessionIDLocked(name); sessionID != "" {
			tm.sessionID = sessionID
			return sessionID, true, nil
		}
		return name, true, nil
	}
	sessionID, err := tm.findSessionIDByLabelLocked(name)
	if err != nil {
		return "", false, err
	}
	if sessionID != "" {
		tm.sessionID = sessionID
		return sessionID, true, nil
	}
	return "", false, nil
}

func (tm *TmuxManager) lookupSessionIDLocked(name string) string {
	output, err := tmuxCommandFn("display-message", "-p", "-t", name, "#{session_id}")
	if err == nil {
		if id := strings.TrimSpace(output); id != "" {
			return id
		}
	}
	sessionID, _ := tm.findSessionIDByLabelLocked(name)
	return sessionID
}

func (tm *TmuxManager) findSessionIDByLabelLocked(name string) (string, error) {
	output, err := tmuxCommandFn("list-sessions", "-F", "#{session_id}\t#{session_name}")
	if err != nil {
		return "", nil
	}
	for _, line := range strings.Split(strings.TrimSpace(output), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) != 2 {
			continue
		}
		sessionID := strings.TrimSpace(parts[0])
		sessionName := strings.TrimSpace(parts[1])
		if sessionName == name {
			return sessionID, nil
		}
		if label, ok := sessionLabel(sessionName); ok && label == name {
			return sessionID, nil
		}
	}
	return "", nil
}

func sessionLabel(name string) (string, bool) {
	sep := strings.IndexByte(name, '-')
	if sep <= 0 {
		return "", false
	}
	if _, err := strconv.Atoi(name[:sep]); err != nil {
		return "", false
	}
	return name[sep+1:], true
}

func parseNewSessionOutput(output string) (string, string) {
	trimmed := strings.TrimSpace(output)
	if trimmed == "" {
		return "", ""
	}
	parts := strings.SplitN(trimmed, "\t", 2)
	if len(parts) == 1 {
		return strings.TrimSpace(parts[0]), ""
	}
	return strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
}

func (tm *TmuxManager) ensureSessionOptionsLocked(target string) error {
	if strings.TrimSpace(target) == "" {
		return nil
	}
	if _, err := tmuxCommandFn("set-option", "-t", target, "allow-rename", "off"); err != nil {
		return err
	}
	if _, err := tmuxCommandFn("set-window-option", "-t", target, "automatic-rename", "off"); err != nil {
		return err
	}
	return nil
}
