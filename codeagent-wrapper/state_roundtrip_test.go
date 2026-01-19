package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// TestStateRoundTripPreservesOrchestrationFields verifies that WriteTaskResult()
// preserves orchestration fields set by Python scripts when updating execution results.
// Requirements: 9.1, 9.2, 9.3, 9.4
func TestStateRoundTripPreservesOrchestrationFields(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "AGENT_STATE.json")

	// Simulate Python script creating initial state with orchestration fields
	parentID := "1"
	escalatedAt := "2026-01-09T00:00:00Z"
	originalAgent := "codex"
	lastReviewSeverity := "major"
	blockedReason := "upstream failure"
	blockedBy := "task-0"

	initialState := AgentState{
		SpecPath:    "/path/to/spec",
		SessionName: "test-session",
		Tasks: []TaskResultState{
			{
				TaskID:      "task-1",
				Description: "Test task description",
				Type:        "code",
				Status:      "not_started",
				// Orchestration fields (set by Python)
				OwnerAgent:         "codex",
				Dependencies:       []string{"task-0"},
				Criticality:        "standard",
				IsOptional:         false,
				ParentID:           &parentID,
				Subtasks:           []string{"task-1.1", "task-1.2"},
				Details:            []string{"Detail 1", "Detail 2"},
				Writes:             []string{"src/main.go", "src/util.go"},
				Reads:              []string{"config.json"},
				FixAttempts:        1,
				MaxFixAttempts:     3,
				Escalated:          true,
				EscalatedAt:        &escalatedAt,
				OriginalAgent:      &originalAgent,
				LastReviewSeverity: &lastReviewSeverity,
				ReviewHistory: []map[string]any{
					{
						"attempt":     0,
						"severity":    "major",
						"reviewed_at": "2026-01-08T00:00:00Z",
					},
				},
				BlockedReason: &blockedReason,
				BlockedBy:     &blockedBy,
				CreatedAt:     "2026-01-07T00:00:00Z",
			},
		},
		ReviewFindings:   []ReviewFindingState{},
		FinalReports:     []FinalReportState{},
		BlockedItems:     []BlockedItemState{},
		PendingDecisions: []PendingDecisionState{},
		DeferredFixes:    []DeferredFixState{},
		WindowMapping:    map[string]string{},
	}

	// Write initial state (simulating Python script)
	data, err := json.MarshalIndent(initialState, "", "  ")
	if err != nil {
		t.Fatalf("marshal initial state: %v", err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		t.Fatalf("write initial state: %v", err)
	}

	// Now simulate Go wrapper updating execution results
	writer := NewStateWriter(path)
	executionResult := TaskResultState{
		TaskID:       "task-1",
		Status:       "in_progress",
		ExitCode:     0,
		Output:       "Task completed successfully",
		FilesChanged: []string{"src/main.go"},
		Coverage:     "85%",
		CoverageNum:  85.0,
		TestsPassed:  10,
		TestsFailed:  0,
		WindowID:     "window-1",
		PaneID:       "pane-1",
		CompletedAt:  time.Now().UTC(),
	}

	if err := writer.WriteTaskResult(executionResult); err != nil {
		t.Fatalf("write task result: %v", err)
	}

	// Read back and verify orchestration fields are preserved
	data, err = os.ReadFile(path)
	if err != nil {
		t.Fatalf("read state file: %v", err)
	}

	var finalState AgentState
	if err := json.Unmarshal(data, &finalState); err != nil {
		t.Fatalf("unmarshal final state: %v", err)
	}

	if len(finalState.Tasks) != 1 {
		t.Fatalf("expected 1 task, got %d", len(finalState.Tasks))
	}

	task := finalState.Tasks[0]

	// Verify execution fields were updated
	if task.Status != "in_progress" {
		t.Errorf("status: expected in_progress, got %s", task.Status)
	}
	if task.Output != "Task completed successfully" {
		t.Errorf("output: expected 'Task completed successfully', got %s", task.Output)
	}
	if task.ExitCode != 0 {
		t.Errorf("exit_code: expected 0, got %d", task.ExitCode)
	}
	if task.WindowID != "window-1" {
		t.Errorf("window_id: expected window-1, got %s", task.WindowID)
	}

	// Verify orchestration fields were preserved (Requirements: 9.2, 9.3)
	if task.Description != "Test task description" {
		t.Errorf("description: expected 'Test task description', got %s", task.Description)
	}
	if task.Type != "code" {
		t.Errorf("type: expected 'code', got %s", task.Type)
	}
	if task.OwnerAgent != "codex" {
		t.Errorf("owner_agent: expected codex, got %s", task.OwnerAgent)
	}
	if len(task.Dependencies) != 1 || task.Dependencies[0] != "task-0" {
		t.Errorf("dependencies: expected [task-0], got %v", task.Dependencies)
	}
	if task.Criticality != "standard" {
		t.Errorf("criticality: expected standard, got %s", task.Criticality)
	}
	if task.ParentID == nil || *task.ParentID != "1" {
		t.Errorf("parent_id: expected '1', got %v", task.ParentID)
	}
	if len(task.Subtasks) != 2 || task.Subtasks[0] != "task-1.1" {
		t.Errorf("subtasks: expected [task-1.1, task-1.2], got %v", task.Subtasks)
	}
	if len(task.Details) != 2 || task.Details[0] != "Detail 1" {
		t.Errorf("details: expected [Detail 1, Detail 2], got %v", task.Details)
	}
	if len(task.Writes) != 2 || task.Writes[0] != "src/main.go" {
		t.Errorf("writes: expected [src/main.go, src/util.go], got %v", task.Writes)
	}
	if len(task.Reads) != 1 || task.Reads[0] != "config.json" {
		t.Errorf("reads: expected [config.json], got %v", task.Reads)
	}
	if task.FixAttempts != 1 {
		t.Errorf("fix_attempts: expected 1, got %d", task.FixAttempts)
	}
	if task.MaxFixAttempts != 3 {
		t.Errorf("max_fix_attempts: expected 3, got %d", task.MaxFixAttempts)
	}
	if !task.Escalated {
		t.Errorf("escalated: expected true, got false")
	}
	if task.EscalatedAt == nil || *task.EscalatedAt != "2026-01-09T00:00:00Z" {
		t.Errorf("escalated_at: expected '2026-01-09T00:00:00Z', got %v", task.EscalatedAt)
	}
	if task.OriginalAgent == nil || *task.OriginalAgent != "codex" {
		t.Errorf("original_agent: expected 'codex', got %v", task.OriginalAgent)
	}
	if task.LastReviewSeverity == nil || *task.LastReviewSeverity != "major" {
		t.Errorf("last_review_severity: expected 'major', got %v", task.LastReviewSeverity)
	}
	if len(task.ReviewHistory) != 1 {
		t.Errorf("review_history: expected 1 entry, got %d", len(task.ReviewHistory))
	}
	if task.BlockedReason == nil || *task.BlockedReason != "upstream failure" {
		t.Errorf("blocked_reason: expected 'upstream failure', got %v", task.BlockedReason)
	}
	if task.BlockedBy == nil || *task.BlockedBy != "task-0" {
		t.Errorf("blocked_by: expected 'task-0', got %v", task.BlockedBy)
	}
	if task.CreatedAt != "2026-01-07T00:00:00Z" {
		t.Errorf("created_at: expected '2026-01-07T00:00:00Z', got %s", task.CreatedAt)
	}
}

// TestStateRoundTripMultipleUpdates verifies that multiple WriteTaskResult() calls
// preserve orchestration fields across updates.
// Requirements: 9.1, 9.2, 9.3, 9.4
func TestStateRoundTripMultipleUpdates(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "AGENT_STATE.json")

	// Create initial state with orchestration fields
	initialState := AgentState{
		SpecPath:    "/path/to/spec",
		SessionName: "test-session",
		Tasks: []TaskResultState{
			{
				TaskID:       "task-1",
				Status:       "not_started",
						OwnerAgent:   "codex",
				Dependencies: []string{"task-0"},
				Subtasks:     []string{"task-1.1"},
				Writes:       []string{"file.go"},
				Reads:        []string{"config.json"},
				FixAttempts:  0,
			},
		},
		ReviewFindings:   []ReviewFindingState{},
		FinalReports:     []FinalReportState{},
		BlockedItems:     []BlockedItemState{},
		PendingDecisions: []PendingDecisionState{},
		DeferredFixes:    []DeferredFixState{},
		WindowMapping:    map[string]string{},
	}

	data, _ := json.MarshalIndent(initialState, "", "  ")
	os.WriteFile(path, data, 0644)

	writer := NewStateWriter(path)

	// First update: in_progress
	if err := writer.WriteTaskResult(TaskResultState{
		TaskID:      "task-1",
		Status:      "in_progress",
		ExitCode:    0,
		CompletedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("first update: %v", err)
	}

	// Second update: pending_review with output
	if err := writer.WriteTaskResult(TaskResultState{
		TaskID:      "task-1",
		Status:      "pending_review",
		ExitCode:    0,
		Output:      "Implementation complete",
		CompletedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("second update: %v", err)
	}

	// Read final state
	data, _ = os.ReadFile(path)
	var finalState AgentState
	json.Unmarshal(data, &finalState)

	task := finalState.Tasks[0]

	// Verify final status
	if task.Status != "pending_review" {
		t.Errorf("status: expected pending_review, got %s", task.Status)
	}
	if task.Output != "Implementation complete" {
		t.Errorf("output: expected 'Implementation complete', got %s", task.Output)
	}

	// Verify orchestration fields still preserved after multiple updates
	if task.OwnerAgent != "codex" {
		t.Errorf("owner_agent lost after updates: expected codex, got %s", task.OwnerAgent)
	}
	if len(task.Dependencies) != 1 || task.Dependencies[0] != "task-0" {
		t.Errorf("dependencies lost after updates: expected [task-0], got %v", task.Dependencies)
	}
	if len(task.Subtasks) != 1 || task.Subtasks[0] != "task-1.1" {
		t.Errorf("subtasks lost after updates: expected [task-1.1], got %v", task.Subtasks)
	}
	if len(task.Writes) != 1 || task.Writes[0] != "file.go" {
		t.Errorf("writes lost after updates: expected [file.go], got %v", task.Writes)
	}
	if len(task.Reads) != 1 || task.Reads[0] != "config.json" {
		t.Errorf("reads lost after updates: expected [config.json], got %v", task.Reads)
	}
}

func TestStateWriterClearsExecutionFieldsOnSuccess(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "AGENT_STATE.json")
	writer := NewStateWriter(path)

	// First write: task starts and goes in_progress with some execution data
	if err := writer.WriteTaskResult(TaskResultState{
		TaskID:       "task-1",
		Status:       "in_progress",
		ExitCode:     1,
		Output:       "failed output",
		Error:        "boom",
		FilesChanged: []string{"a.go"},
		Coverage:     "50%",
		CoverageNum:  50,
		TestsPassed:  1,
		TestsFailed:  2,
		CompletedAt:  time.Now().UTC(),
	}); err != nil {
		t.Fatalf("write failed result: %v", err)
	}

	// Second write: task completes successfully (in_progress -> pending_review is valid)
	if err := writer.WriteTaskResult(TaskResultState{
		TaskID:      "task-1",
		Status:      "pending_review",
		ExitCode:    0,
		CompletedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("write success result: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read state file: %v", err)
	}

	var state AgentState
	if err := json.Unmarshal(data, &state); err != nil {
		t.Fatalf("unmarshal final state: %v", err)
	}
	if len(state.Tasks) != 1 {
		t.Fatalf("expected 1 task, got %d", len(state.Tasks))
	}

	task := state.Tasks[0]
	if task.Error != "" {
		t.Errorf("error not cleared: got %q", task.Error)
	}
	if task.Output != "" {
		t.Errorf("output not cleared: got %q", task.Output)
	}
	if len(task.FilesChanged) != 0 {
		t.Errorf("files_changed not cleared: got %v", task.FilesChanged)
	}
	if task.Coverage != "" {
		t.Errorf("coverage not cleared: got %q", task.Coverage)
	}
	if task.CoverageNum != 0 {
		t.Errorf("coverage_num not cleared: got %v", task.CoverageNum)
	}
	if task.TestsPassed != 0 {
		t.Errorf("tests_passed not cleared: got %d", task.TestsPassed)
	}
	if task.TestsFailed != 0 {
		t.Errorf("tests_failed not cleared: got %d", task.TestsFailed)
	}
}

// TestExecutionReportPythonCompatibility verifies that ExecutionReport contains
// fields expected by Python scripts (dispatch_batch.py, dispatch_reviews.py).
// Requirements: 10.1, 10.2, 10.3
func TestExecutionReportPythonCompatibility(t *testing.T) {
	results := []TaskResult{
		{
			TaskID:   "task-1",
			ExitCode: 0,
		},
		{
			TaskID:   "task-2",
			ExitCode: 1,
			Error:    "failed",
		},
	}

	report := buildExecutionReport(results, false)

	// Verify Python-compatible fields for dispatch_batch.py
	if report.TasksCompleted != 1 {
		t.Errorf("tasks_completed: expected 1, got %d", report.TasksCompleted)
	}
	if report.TasksFailed != 1 {
		t.Errorf("tasks_failed: expected 1, got %d", report.TasksFailed)
	}
	if len(report.TaskResults) != 2 {
		t.Errorf("task_results: expected 2, got %d", len(report.TaskResults))
	}

	// Verify Python-compatible fields for dispatch_reviews.py
	if report.ReviewsCompleted != 1 {
		t.Errorf("reviews_completed: expected 1, got %d", report.ReviewsCompleted)
	}
	if report.ReviewsFailed != 1 {
		t.Errorf("reviews_failed: expected 1, got %d", report.ReviewsFailed)
	}
	if len(report.ReviewResults) != 2 {
		t.Errorf("review_results: expected 2, got %d", len(report.ReviewResults))
	}

	// Verify JSON serialization includes all fields
	data, err := json.Marshal(report)
	if err != nil {
		t.Fatalf("marshal report: %v", err)
	}

	var raw map[string]any
	json.Unmarshal(data, &raw)

	requiredFields := []string{
		"summary",
		"tasks",
		"tasks_completed",
		"tasks_failed",
		"task_results",
		"reviews_completed",
		"reviews_failed",
		"review_results",
		"generated_at",
	}

	for _, field := range requiredFields {
		if _, ok := raw[field]; !ok {
			t.Errorf("missing required field: %s", field)
		}
	}
}

// TestStateRoundTripNewTaskPreservesAllFields verifies that when a new task is added
// (not updating existing), all fields are preserved.
func TestStateRoundTripNewTaskPreservesAllFields(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "AGENT_STATE.json")
	writer := NewStateWriter(path)

	parentID := "parent-1"
	newTask := TaskResultState{
		TaskID:         "new-task",
		Description:    "New task",
		Type:           "code",
		Status:         "in_progress",
		OwnerAgent:     "gemini",
		Dependencies:   []string{"dep-1", "dep-2"},
		Criticality:    "complex",
		IsOptional:     true,
		ParentID:       &parentID,
		Subtasks:       []string{"sub-1"},
		Details:        []string{"detail"},
		Writes:         []string{"output.txt"},
		Reads:          []string{"input.txt"},
		FixAttempts:    2,
		MaxFixAttempts: 3,
		ExitCode:       0,
		Output:         "done",
		CompletedAt:    time.Now().UTC(),
	}

	if err := writer.WriteTaskResult(newTask); err != nil {
		t.Fatalf("write new task: %v", err)
	}

	data, _ := os.ReadFile(path)
	var state AgentState
	json.Unmarshal(data, &state)

	if len(state.Tasks) != 1 {
		t.Fatalf("expected 1 task, got %d", len(state.Tasks))
	}

	task := state.Tasks[0]

	// Verify all fields are present for new task
	if task.TaskID != "new-task" {
		t.Errorf("task_id mismatch")
	}
	if task.Description != "New task" {
		t.Errorf("description mismatch")
	}
	if task.OwnerAgent != "gemini" {
		t.Errorf("owner_agent mismatch")
	}
	if len(task.Dependencies) != 2 {
		t.Errorf("dependencies mismatch")
	}
	if task.ParentID == nil || *task.ParentID != "parent-1" {
		t.Errorf("parent_id mismatch")
	}
	if len(task.Subtasks) != 1 {
		t.Errorf("subtasks mismatch")
	}
	if len(task.Writes) != 1 {
		t.Errorf("writes mismatch")
	}
	if len(task.Reads) != 1 {
		t.Errorf("reads mismatch")
	}
	if task.FixAttempts != 2 {
		t.Errorf("fix_attempts mismatch")
	}
}
