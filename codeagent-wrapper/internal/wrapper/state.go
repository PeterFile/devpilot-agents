package wrapper

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
// This struct contains ALL task fields to support both:
// - Orchestration fields (set by Python scripts): owner_agent, dependencies, subtasks, etc.
// - Execution fields (set by Go wrapper): exit_code, output, error, etc.
//
// When WriteTaskResult() is called, only execution-related fields are updated,
// preserving existing orchestration fields set by Python scripts.
// Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
type TaskResultState struct {
	// Core identification
	TaskID      string `json:"task_id"`
	Description string `json:"description,omitempty"`
	Type        string `json:"type,omitempty"` // "code", "ui", "review"
	Status      string `json:"status"`

	// Orchestration fields (preserved during execution updates)
	OwnerAgent         string           `json:"owner_agent,omitempty"`
	Dependencies       []string         `json:"dependencies,omitempty"`
	Criticality        string           `json:"criticality,omitempty"`
	IsOptional         bool             `json:"is_optional,omitempty"`
	ParentID           *string          `json:"parent_id,omitempty"`
	Subtasks           []string         `json:"subtasks,omitempty"`
	Details            []string         `json:"details,omitempty"`
	Writes             []string         `json:"writes,omitempty"`
	Reads              []string         `json:"reads,omitempty"`
	FixAttempts        int              `json:"fix_attempts,omitempty"`
	MaxFixAttempts     int              `json:"max_fix_attempts,omitempty"`
	Escalated          bool             `json:"escalated,omitempty"`
	EscalatedAt        *string          `json:"escalated_at,omitempty"`
	OriginalAgent      *string          `json:"original_agent,omitempty"`
	LastReviewSeverity *string          `json:"last_review_severity,omitempty"`
	ReviewHistory      []map[string]any `json:"review_history,omitempty"`
	BlockedReason      *string          `json:"blocked_reason,omitempty"`
	BlockedBy          *string          `json:"blocked_by,omitempty"`
	CreatedAt          string           `json:"created_at,omitempty"`

	// Execution result fields (updated by Go wrapper)
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
			// Merge execution fields into existing task, preserving orchestration fields
			// Requirements: 9.1, 9.2, 9.3, 9.4
			existing := &state.Tasks[idx]
			mergeExecutionFields(existing, &result)
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

// mergeExecutionFields updates only execution-related fields in the existing task,
// preserving orchestration fields set by Python scripts.
// Requirements: 9.1, 9.2, 9.3, 9.4
func mergeExecutionFields(existing *TaskResultState, result *TaskResultState) {
	// Always update status if provided
	if result.Status != "" {
		existing.Status = result.Status
	}

	// Update execution result fields (these come from Go wrapper execution)
	if result.ExitCode != 0 || !result.CompletedAt.IsZero() {
		existing.ExitCode = result.ExitCode
	}
	if !result.CompletedAt.IsZero() {
		existing.CompletedAt = result.CompletedAt
	}

	// Update optional execution fields even when empty to clear stale results
	existing.Output = result.Output
	existing.Error = result.Error
	existing.FilesChanged = result.FilesChanged
	existing.Coverage = result.Coverage
	existing.CoverageNum = result.CoverageNum
	existing.TestsPassed = result.TestsPassed
	existing.TestsFailed = result.TestsFailed
	if result.WindowID != "" {
		existing.WindowID = result.WindowID
	}
	if result.PaneID != "" {
		existing.PaneID = result.PaneID
	}

	// Note: Orchestration fields are NOT updated here:
	// - OwnerAgent, Dependencies, Criticality, IsOptional
	// - ParentID, Subtasks, Details
	// - Writes, Reads
	// - FixAttempts, MaxFixAttempts, Escalated, EscalatedAt, OriginalAgent
	// - LastReviewSeverity, ReviewHistory
	// - BlockedReason, BlockedBy, CreatedAt
	// These are managed by Python orchestration scripts
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

// GetWindowMapping returns the window mapping from AGENT_STATE.
// This allows cross-batch dependency resolution by looking up windows
// from previous batches that were persisted to state.
// Requirements: 11.1, 11.2, 11.3, 11.4
func (sw *StateWriter) GetWindowMapping() (map[string]string, error) {
	if sw == nil {
		return nil, errors.New("state writer is nil")
	}
	if strings.TrimSpace(sw.path) == "" {
		return nil, errors.New("state file path is required")
	}

	sw.mu.Lock()
	defer sw.mu.Unlock()

	state, err := sw.readState()
	if err != nil {
		return nil, err
	}
	if state.WindowMapping == nil {
		return map[string]string{}, nil
	}
	// Return a copy to avoid concurrent modification
	result := make(map[string]string, len(state.WindowMapping))
	for k, v := range state.WindowMapping {
		result[k] = v
	}
	return result, nil
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
