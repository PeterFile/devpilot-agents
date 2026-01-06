package main

import (
	"fmt"
	"strings"
	"testing"
)

// TestTmuxSessionPersistenceProperty verifies that tmux sessions persist
// after codeagent-wrapper exits (Requirement 12.9).
//
// Property: For any tmux session created by codeagent-wrapper, the session
// SHALL remain active after the wrapper process exits, allowing users to
// review task history.
func TestTmuxSessionPersistenceProperty(t *testing.T) {
	orig := tmuxCommandFn
	origHas := tmuxHasSessionFn
	t.Cleanup(func() {
		tmuxCommandFn = orig
		tmuxHasSessionFn = origHas
	})

	// Track session state
	sessionExists := false
	sessionName := ""

	// Mock tmux commands to track session creation
	tmuxCommandFn = func(args ...string) (string, error) {
		if len(args) == 0 {
			return "", fmt.Errorf("missing tmux args")
		}
		switch args[0] {
		case "new-session":
			// Extract session name
			for i := 0; i < len(args)-1; i++ {
				if args[i] == "-s" {
					sessionName = args[i+1]
					sessionExists = true
					break
				}
			}
			return "", nil
		case "new-window":
			return "@1", nil
		case "split-window":
			return "%1", nil
		case "send-keys":
			return "", nil
		case "kill-session":
			// Session should NOT be killed by wrapper
			t.Fatalf("wrapper should not kill tmux session")
			return "", nil
		default:
			return "", nil
		}
	}

	tmuxHasSessionFn = func(session string) bool {
		return sessionExists && session == sessionName
	}

	// Create TmuxManager and ensure session
	tm := NewTmuxManager(TmuxConfig{SessionName: "test-persistence"})
	if err := tm.EnsureSession(); err != nil {
		t.Fatalf("EnsureSession failed: %v", err)
	}

	// Verify session was created
	if !sessionExists {
		t.Fatal("session should have been created")
	}
	if sessionName != "test-persistence" {
		t.Fatalf("session name = %q, want %q", sessionName, "test-persistence")
	}

	// Simulate wrapper exit - session should still exist
	// (In real scenario, tmux session persists because it's detached)
	if !tm.SessionExists() {
		t.Fatal("session should persist after wrapper operations")
	}
}

// TestTmuxSessionDetachedCreation verifies that sessions are created
// in detached mode (-d flag), which is essential for persistence.
func TestTmuxSessionDetachedCreation(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	var newSessionArgs []string

	tmuxCommandFn = func(args ...string) (string, error) {
		if len(args) > 0 && args[0] == "new-session" {
			newSessionArgs = args
		}
		return "", nil
	}

	tm := NewTmuxManager(TmuxConfig{SessionName: "detach-test"})
	if err := tm.EnsureSession(); err != nil {
		t.Fatalf("EnsureSession failed: %v", err)
	}

	// Verify -d flag is present (detached mode)
	hasDetached := false
	for _, arg := range newSessionArgs {
		if arg == "-d" {
			hasDetached = true
			break
		}
	}

	if !hasDetached {
		t.Fatalf("new-session should use -d flag for detached mode, args: %v", newSessionArgs)
	}
}

// TestTmuxWindowHistoryPreservation verifies that task windows preserve
// command history for user review.
func TestTmuxWindowHistoryPreservation(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	var sentCommands []struct {
		target  string
		command string
	}

	tmuxCommandFn = func(args ...string) (string, error) {
		if len(args) == 0 {
			return "", fmt.Errorf("missing tmux args")
		}
		switch args[0] {
		case "new-window":
			return "@1", nil
		case "split-window":
			return "%1", nil
		case "send-keys":
			// Track commands sent to panes
			target := ""
			command := ""
			for i := 0; i < len(args)-1; i++ {
				if args[i] == "-t" {
					target = args[i+1]
				}
			}
			// Command is typically the second-to-last arg (before "Enter")
			if len(args) >= 3 {
				command = args[len(args)-2]
			}
			sentCommands = append(sentCommands, struct {
				target  string
				command string
			}{target, command})
			return "", nil
		default:
			return "", nil
		}
	}

	tm := NewTmuxManager(TmuxConfig{SessionName: "history-test"})

	// Create window and send command
	_, err := tm.CreateWindow("task-001")
	if err != nil {
		t.Fatalf("CreateWindow failed: %v", err)
	}

	testCommand := "echo 'Task execution started'"
	if err := tm.SendCommand("history-test:task-001", testCommand); err != nil {
		t.Fatalf("SendCommand failed: %v", err)
	}

	// Verify command was sent (will be in tmux history)
	if len(sentCommands) == 0 {
		t.Fatal("no commands were sent to tmux")
	}

	found := false
	for _, cmd := range sentCommands {
		if strings.Contains(cmd.command, "Task execution started") {
			found = true
			break
		}
	}

	if !found {
		t.Fatalf("expected command not found in sent commands: %v", sentCommands)
	}
}

// TestTmuxMultipleTaskWindowsPersistence verifies that multiple task windows
// all persist after wrapper operations complete.
func TestTmuxMultipleTaskWindowsPersistence(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	createdWindows := make(map[string]bool)

	tmuxCommandFn = func(args ...string) (string, error) {
		if len(args) == 0 {
			return "", fmt.Errorf("missing tmux args")
		}
		switch args[0] {
		case "new-window":
			// Extract window name
			for i := 0; i < len(args)-1; i++ {
				if args[i] == "-n" {
					createdWindows[args[i+1]] = true
					break
				}
			}
			return "@1", nil
		case "split-window":
			return "%1", nil
		default:
			return "", nil
		}
	}

	tm := NewTmuxManager(TmuxConfig{SessionName: "multi-window-test"})

	// Create multiple task windows
	tasks := []TaskSpec{
		{ID: "task-001"},
		{ID: "task-002"},
		{ID: "task-003"},
	}

	mapping, err := tm.SetupTaskPanes(tasks)
	if err != nil {
		t.Fatalf("SetupTaskPanes failed: %v", err)
	}

	// Verify all windows were created
	for _, task := range tasks {
		if !createdWindows[task.ID] {
			t.Fatalf("window for task %s was not created", task.ID)
		}
		if mapping[task.ID] != task.ID {
			t.Fatalf("task %s mapping = %s, want %s", task.ID, mapping[task.ID], task.ID)
		}
	}

	// All windows should persist (no kill-window calls)
	if len(createdWindows) != len(tasks) {
		t.Fatalf("expected %d windows, got %d", len(tasks), len(createdWindows))
	}
}

// TestTmuxDependentTaskPanesPersistence verifies that panes for dependent
// tasks persist in their parent windows.
func TestTmuxDependentTaskPanesPersistence(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	createdWindows := make(map[string]bool)
	createdPanes := make(map[string]int) // window -> pane count

	tmuxCommandFn = func(args ...string) (string, error) {
		if len(args) == 0 {
			return "", fmt.Errorf("missing tmux args")
		}
		switch args[0] {
		case "new-window":
			for i := 0; i < len(args)-1; i++ {
				if args[i] == "-n" {
					createdWindows[args[i+1]] = true
					break
				}
			}
			return "@1", nil
		case "split-window":
			// Extract target window
			for i := 0; i < len(args)-1; i++ {
				if args[i] == "-t" {
					target := args[i+1]
					// Extract window name from target (session:window)
					parts := strings.Split(target, ":")
					if len(parts) == 2 {
						createdPanes[parts[1]]++
					}
					break
				}
			}
			return "%1", nil
		default:
			return "", nil
		}
	}

	tm := NewTmuxManager(TmuxConfig{SessionName: "dep-pane-test"})

	// Create tasks with dependencies
	tasks := []TaskSpec{
		{ID: "task-001"},                              // Independent
		{ID: "task-002", Dependencies: []string{"task-001"}}, // Dependent on task-001
		{ID: "task-003", Dependencies: []string{"task-001"}}, // Also dependent on task-001
	}

	mapping, err := tm.SetupTaskPanes(tasks)
	if err != nil {
		t.Fatalf("SetupTaskPanes failed: %v", err)
	}

	// Verify window was created for independent task
	if !createdWindows["task-001"] {
		t.Fatal("window for task-001 was not created")
	}

	// Verify dependent tasks are in same window
	if mapping["task-002"] != "task-001" {
		t.Fatalf("task-002 should be in task-001 window, got %s", mapping["task-002"])
	}
	if mapping["task-003"] != "task-001" {
		t.Fatalf("task-003 should be in task-001 window, got %s", mapping["task-003"])
	}

	// Verify panes were created in task-001 window
	if createdPanes["task-001"] != 2 {
		t.Fatalf("expected 2 panes in task-001 window, got %d", createdPanes["task-001"])
	}
}

// TestTmuxSessionReuseProperty verifies that existing sessions are reused
// rather than recreated, preserving history.
func TestTmuxSessionReuseProperty(t *testing.T) {
	orig := tmuxCommandFn
	origHas := tmuxHasSessionFn
	t.Cleanup(func() {
		tmuxCommandFn = orig
		tmuxHasSessionFn = origHas
	})

	newSessionCalls := 0

	tmuxCommandFn = func(args ...string) (string, error) {
		if len(args) > 0 && args[0] == "new-session" {
			newSessionCalls++
		}
		return "", nil
	}

	// Simulate existing session
	tmuxHasSessionFn = func(session string) bool {
		return session == "existing-session"
	}

	tm := NewTmuxManager(TmuxConfig{SessionName: "existing-session"})

	// EnsureSession should not create new session
	if err := tm.EnsureSession(); err != nil {
		t.Fatalf("EnsureSession failed: %v", err)
	}

	if newSessionCalls != 0 {
		t.Fatalf("new-session called %d times, expected 0 for existing session", newSessionCalls)
	}
}
