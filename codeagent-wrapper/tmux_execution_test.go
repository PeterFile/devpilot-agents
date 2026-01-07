package main

import "testing"

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
