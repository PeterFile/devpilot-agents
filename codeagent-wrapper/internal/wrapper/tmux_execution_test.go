package wrapper

import (
	"os"
	"testing"
)

func TestTmuxExecutionWindowCreationProperty(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	recorder := &tmuxRecorder{}
	tmuxCommandFn = recorder.run

	tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
	runner := newTmuxTaskRunner(tm, nil, false, "")

	for i := 0; i < 20; i++ {
		taskID := nextExecutorTestTaskID("win")
		if _, err := runner.prepareTarget(TaskSpec{ID: taskID}); err != nil {
			t.Fatalf("prepare target failed: %v", err)
		}
	}

	if len(recorder.windowNames) != 20 {
		t.Fatalf("expected 20 windows, got %d", len(recorder.windowNames))
	}
}

func TestTmuxExecutionPaneCreationProperty(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	recorder := &tmuxRecorder{}
	tmuxCommandFn = recorder.run

	tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
	runner := newTmuxTaskRunner(tm, nil, false, "task-001")

	if _, err := runner.prepareTarget(TaskSpec{ID: "task-002"}); err != nil {
		t.Fatalf("prepare target failed: %v", err)
	}

	if len(recorder.paneTargets) != 1 {
		t.Fatalf("expected 1 pane creation, got %d", len(recorder.paneTargets))
	}
	target := recorder.paneTargets[0]
	if target != "session:task-001" {
		t.Fatalf("expected pane target session:task-001, got %s", target)
	}
}

func TestTmuxExecutionCrossBatchDependencyLookup(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	recorder := &tmuxRecorder{}
	tmuxCommandFn = recorder.run

	// Create a temp state file with pre-existing window mapping
	tmpFile, err := os.CreateTemp("", "agent-state-*.json")
	if err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}
	defer os.Remove(tmpFile.Name())

	// Write initial state with window mapping from "previous batch"
	initialState := `{
		"tasks": [],
		"window_mapping": {
			"task-from-batch-1": "task-from-batch-1"
		}
	}`
	if err := os.WriteFile(tmpFile.Name(), []byte(initialState), 0o644); err != nil {
		t.Fatalf("failed to write initial state: %v", err)
	}

	stateWriter := NewStateWriter(tmpFile.Name())
	tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
	runner := newTmuxTaskRunner(tm, stateWriter, false, "")

	// Task in "batch 2" depends on task from "batch 1"
	task := TaskSpec{
		ID:           "task-from-batch-2",
		Dependencies: []string{"task-from-batch-1"},
	}

	target, err := runner.prepareTarget(task)
	if err != nil {
		t.Fatalf("prepareTarget failed for cross-batch dependency: %v", err)
	}

	// Should have found the window from persisted state
	if target.windowName != "task-from-batch-1" {
		t.Fatalf("expected window name 'task-from-batch-1', got '%s'", target.windowName)
	}

	// Should have created a pane in the existing window
	if len(recorder.paneTargets) != 1 {
		t.Fatalf("expected 1 pane creation, got %d", len(recorder.paneTargets))
	}
	if recorder.paneTargets[0] != "session:task-from-batch-1" {
		t.Fatalf("expected pane target 'session:task-from-batch-1', got '%s'", recorder.paneTargets[0])
	}
}

func TestTmuxExecutionCrossBatchDependencyNotFound(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	recorder := &tmuxRecorder{}
	tmuxCommandFn = recorder.run

	// Create a temp state file with empty window mapping
	tmpFile, err := os.CreateTemp("", "agent-state-*.json")
	if err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}
	defer os.Remove(tmpFile.Name())

	initialState := `{"tasks": [], "window_mapping": {}}`
	if err := os.WriteFile(tmpFile.Name(), []byte(initialState), 0o644); err != nil {
		t.Fatalf("failed to write initial state: %v", err)
	}

	stateWriter := NewStateWriter(tmpFile.Name())
	tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
	runner := newTmuxTaskRunner(tm, stateWriter, false, "")

	// Task depends on non-existent task
	task := TaskSpec{
		ID:           "task-orphan",
		Dependencies: []string{"non-existent-task"},
	}

	_, err = runner.prepareTarget(task)
	if err == nil {
		t.Fatal("expected error for missing dependency, got nil")
	}

	expectedErr := `dependency window not found for task "task-orphan" (dependency: "non-existent-task")`
	if err.Error() != expectedErr {
		t.Fatalf("expected error '%s', got '%s'", expectedErr, err.Error())
	}
}

func TestTmuxExecutionLocalBatchTakesPrecedence(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	recorder := &tmuxRecorder{}
	tmuxCommandFn = recorder.run

	// Create a temp state file with window mapping
	tmpFile, err := os.CreateTemp("", "agent-state-*.json")
	if err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}
	defer os.Remove(tmpFile.Name())

	// Persisted state has a different window for the dependency
	initialState := `{
		"tasks": [],
		"window_mapping": {
			"dep-task": "old-window"
		}
	}`
	if err := os.WriteFile(tmpFile.Name(), []byte(initialState), 0o644); err != nil {
		t.Fatalf("failed to write initial state: %v", err)
	}

	stateWriter := NewStateWriter(tmpFile.Name())
	tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
	runner := newTmuxTaskRunner(tm, stateWriter, false, "")

	// First, create the dependency task in current batch (creates new window)
	depTask := TaskSpec{ID: "dep-task"}
	_, err = runner.prepareTarget(depTask)
	if err != nil {
		t.Fatalf("prepareTarget failed for dep task: %v", err)
	}

	// Now create dependent task - should use local batch mapping, not persisted
	task := TaskSpec{
		ID:           "child-task",
		Dependencies: []string{"dep-task"},
	}

	target, err := runner.prepareTarget(task)
	if err != nil {
		t.Fatalf("prepareTarget failed: %v", err)
	}

	// Should use local batch window (dep-task), not persisted (old-window)
	if target.windowName != "dep-task" {
		t.Fatalf("expected window name 'dep-task' (from local batch), got '%s'", target.windowName)
	}
}
