package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// TaskResultState represents a task result in AGENT_STATE.json.
type TaskResultState struct {
	TaskID       string    `json:"task_id"`
	Status       string    `json:"status"`
	ExitCode     int       `json:"exit_code"`
	Output       string    `json:"output,omitempty"`
	Error        string    `json:"error,omitempty"`
	FilesChanged []string  `json:"files_changed,omitempty"`
	Coverage     string    `json:"coverage,omitempty"`
	CoverageNum  float64   `json:"coverage_num,omitempty"`
	TestsPassed  int       `json:"tests_passed,omitempty"`
	TestsFailed  int       `json:"tests_failed,omitempty"`
	WindowID     string    `json:"window_id,omitempty"`
	PaneID       string    `json:"pane_id,omitempty"`
	CompletedAt  time.Time `json:"completed_at"`
}

// ReviewFindingState represents a review finding.
type ReviewFindingState struct {
	TaskID    string    `json:"task_id"`
	Reviewer  string    `json:"reviewer"`
	Severity  string    `json:"severity"`
	Summary   string    `json:"summary"`
	Details   string    `json:"details,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

// FinalReportState represents a consolidated review report.
type FinalReportState struct {
	TaskID          string    `json:"task_id"`
	OverallSeverity string    `json:"overall_severity"`
	Summary         string    `json:"summary"`
	FindingCount    int       `json:"finding_count"`
	CreatedAt       time.Time `json:"created_at"`
}

// BlockedItemState represents a blocked task entry.
type BlockedItemState struct {
	TaskID             string    `json:"task_id"`
	BlockingReason     string    `json:"blocking_reason"`
	RequiredResolution string    `json:"required_resolution"`
	CreatedAt          time.Time `json:"created_at"`
}

// PendingDecisionState represents a decision awaiting human input.
type PendingDecisionState struct {
	ID        string    `json:"id"`
	TaskID    string    `json:"task_id"`
	Context   string    `json:"context"`
	Options   []string  `json:"options"`
	CreatedAt time.Time `json:"created_at"`
}

// DeferredFixState represents a fix deferred for later.
type DeferredFixState struct {
	TaskID      string    `json:"task_id"`
	Description string    `json:"description"`
	Severity    string    `json:"severity"`
	CreatedAt   time.Time `json:"created_at"`
}

// AgentState represents the AGENT_STATE.json structure.
type AgentState struct {
	SpecPath         string                 `json:"spec_path"`
	SessionName      string                 `json:"session_name"`
	Tasks            []TaskResultState      `json:"tasks"`
	ReviewFindings   []ReviewFindingState   `json:"review_findings"`
	FinalReports     []FinalReportState     `json:"final_reports"`
	BlockedItems     []BlockedItemState     `json:"blocked_items"`
	PendingDecisions []PendingDecisionState `json:"pending_decisions"`
	DeferredFixes    []DeferredFixState     `json:"deferred_fixes"`
	WindowMapping    map[string]string      `json:"window_mapping"`
}

// StateWriter handles atomic writes to AGENT_STATE.json.
type StateWriter struct {
	path string
	mu   sync.Mutex
}

func NewStateWriter(path string) *StateWriter {
	return &StateWriter{path: path}
}

func (sw *StateWriter) WriteTaskResult(result TaskResultState) error {
	return sw.updateState(func(state *AgentState) error {
		idx := -1
		prevStatus := ""
		for i, t := range state.Tasks {
			if t.TaskID == result.TaskID {
				idx = i
				prevStatus = t.Status
				break
			}
		}
		if result.Status != "" && !validateTransition(prevStatus, result.Status) {
			return fmt.Errorf("invalid state transition for %s: %s -> %s", result.TaskID, prevStatus, result.Status)
		}
		if idx >= 0 {
			state.Tasks[idx] = result
		} else {
			state.Tasks = append(state.Tasks, result)
		}
		if result.WindowID != "" {
			if state.WindowMapping == nil {
				state.WindowMapping = make(map[string]string)
			}
			state.WindowMapping[result.TaskID] = result.WindowID
		}
		return nil
	})
}

func (sw *StateWriter) WriteReviewFinding(finding ReviewFindingState) error {
	return sw.updateState(func(state *AgentState) error {
		state.ReviewFindings = append(state.ReviewFindings, finding)
		return nil
	})
}

func (sw *StateWriter) WriteFinalReport(report FinalReportState) error {
	return sw.updateState(func(state *AgentState) error {
		state.FinalReports = append(state.FinalReports, report)
		return nil
	})
}

func (sw *StateWriter) WriteBlockedItem(item BlockedItemState) error {
	return sw.updateState(func(state *AgentState) error {
		state.BlockedItems = append(state.BlockedItems, item)
		return nil
	})
}

func (sw *StateWriter) WritePendingDecision(decision PendingDecisionState) error {
	return sw.updateState(func(state *AgentState) error {
		state.PendingDecisions = append(state.PendingDecisions, decision)
		return nil
	})
}

func (sw *StateWriter) WriteDeferredFix(fix DeferredFixState) error {
	return sw.updateState(func(state *AgentState) error {
		state.DeferredFixes = append(state.DeferredFixes, fix)
		return nil
	})
}

func (sw *StateWriter) updateState(updateFn func(state *AgentState) error) error {
	if sw == nil {
		return errors.New("state writer is nil")
	}
	if strings.TrimSpace(sw.path) == "" {
		return errors.New("state file path is required")
	}

	sw.mu.Lock()
	defer sw.mu.Unlock()

	state, err := sw.readState()
	if err != nil {
		return err
	}
	if err := updateFn(&state); err != nil {
		return err
	}
	normalizeAgentState(&state)
	return sw.writeState(state)
}

func (sw *StateWriter) readState() (AgentState, error) {
	path := sw.path
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return defaultAgentState(), nil
		}
		return AgentState{}, err
	}
	if len(bytes.TrimSpace(data)) == 0 {
		return defaultAgentState(), nil
	}
	var state AgentState
	if err := json.Unmarshal(data, &state); err != nil {
		return AgentState{}, err
	}
	normalizeAgentState(&state)
	return state, nil
}

func (sw *StateWriter) writeState(state AgentState) error {
	dir := filepath.Dir(sw.path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}

	tmpFile, err := os.CreateTemp(dir, "agent-state-*.json")
	if err != nil {
		return err
	}
	tmpName := tmpFile.Name()
	defer func() {
		_ = tmpFile.Close()
		_ = os.Remove(tmpName)
	}()

	if _, err := tmpFile.Write(data); err != nil {
		return err
	}
	if err := tmpFile.Sync(); err != nil {
		return err
	}
	if err := tmpFile.Close(); err != nil {
		return err
	}

	return os.Rename(tmpName, sw.path)
}

func defaultAgentState() AgentState {
	state := AgentState{
		Tasks:            []TaskResultState{},
		ReviewFindings:   []ReviewFindingState{},
		FinalReports:     []FinalReportState{},
		BlockedItems:     []BlockedItemState{},
		PendingDecisions: []PendingDecisionState{},
		DeferredFixes:    []DeferredFixState{},
		WindowMapping:    map[string]string{},
	}
	return state
}

func normalizeAgentState(state *AgentState) {
	if state.Tasks == nil {
		state.Tasks = []TaskResultState{}
	}
	if state.ReviewFindings == nil {
		state.ReviewFindings = []ReviewFindingState{}
	}
	if state.FinalReports == nil {
		state.FinalReports = []FinalReportState{}
	}
	if state.BlockedItems == nil {
		state.BlockedItems = []BlockedItemState{}
	}
	if state.PendingDecisions == nil {
		state.PendingDecisions = []PendingDecisionState{}
	}
	if state.DeferredFixes == nil {
		state.DeferredFixes = []DeferredFixState{}
	}
	if state.WindowMapping == nil {
		state.WindowMapping = map[string]string{}
	}
}
