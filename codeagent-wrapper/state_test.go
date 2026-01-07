package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestStateWriterSchemaConformanceProperty(t *testing.T) {
	for i := 0; i < 25; i++ {
		dir := t.TempDir()
		path := filepath.Join(dir, "AGENT_STATE.json")
		writer := NewStateWriter(path)

		result := TaskResultState{
			TaskID:      fmt.Sprintf("task-%d", i),
			Status:      "in_progress",
			ExitCode:    0,
			CompletedAt: time.Now().UTC(),
		}
		if err := writer.WriteTaskResult(result); err != nil {
			t.Fatalf("write task result: %v", err)
		}

		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("read state file: %v", err)
		}
		if err := validateAgentStateShape(data); err != nil {
			t.Fatalf("schema conformance failed: %v", err)
		}
	}
}

func TestStateWriterUpdateProperty(t *testing.T) {
	for i := 0; i < 25; i++ {
		dir := t.TempDir()
		path := filepath.Join(dir, "AGENT_STATE.json")
		writer := NewStateWriter(path)

		taskID := fmt.Sprintf("task-%d", i)
		result := TaskResultState{
			TaskID:      taskID,
			Status:      "in_progress",
			ExitCode:    0,
			CompletedAt: time.Now().UTC(),
		}

		if err := writer.WriteTaskResult(result); err != nil {
			t.Fatalf("write task result: %v", err)
		}

		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("read state file: %v", err)
		}
		var state AgentState
		if err := json.Unmarshal(data, &state); err != nil {
			t.Fatalf("unmarshal state: %v", err)
		}

		found := false
		for _, task := range state.Tasks {
			if task.TaskID == taskID {
				found = true
				if task.Status != result.Status {
					t.Fatalf("expected status %s, got %s", result.Status, task.Status)
				}
				break
			}
		}
		if !found {
			t.Fatalf("task %s not found in state", taskID)
		}
	}
}

func validateAgentStateShape(data []byte) error {
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}

	required := []string{
		"spec_path",
		"session_name",
		"tasks",
		"review_findings",
		"final_reports",
		"blocked_items",
		"pending_decisions",
		"deferred_fixes",
		"window_mapping",
	}

	for _, key := range required {
		if _, ok := raw[key]; !ok {
			return fmt.Errorf("missing field %s", key)
		}
	}

	if _, ok := raw["spec_path"].(string); !ok {
		return fmt.Errorf("spec_path must be string")
	}
	if _, ok := raw["session_name"].(string); !ok {
		return fmt.Errorf("session_name must be string")
	}
	if _, ok := raw["tasks"].([]any); !ok {
		return fmt.Errorf("tasks must be array")
	}
	if _, ok := raw["review_findings"].([]any); !ok {
		return fmt.Errorf("review_findings must be array")
	}
	if _, ok := raw["final_reports"].([]any); !ok {
		return fmt.Errorf("final_reports must be array")
	}
	if _, ok := raw["blocked_items"].([]any); !ok {
		return fmt.Errorf("blocked_items must be array")
	}
	if _, ok := raw["pending_decisions"].([]any); !ok {
		return fmt.Errorf("pending_decisions must be array")
	}
	if _, ok := raw["deferred_fixes"].([]any); !ok {
		return fmt.Errorf("deferred_fixes must be array")
	}
	if _, ok := raw["window_mapping"].(map[string]any); !ok {
		return fmt.Errorf("window_mapping must be object")
	}
	return nil
}
