package main

import "testing"

func TestStateTransitionValidityProperty(t *testing.T) {
	for from, allowed := range validStateTransitions {
		for to := range allowed {
			if !validateTransition(from, to) {
				t.Fatalf("expected valid transition %s -> %s", from, to)
			}
		}
	}
}

func TestInvalidTransitionRejectionProperty(t *testing.T) {
	statuses := []string{"not_started", "in_progress", "pending_review", "under_review", "final_review", "completed", "blocked"}
	for _, from := range statuses {
		for _, to := range statuses {
			_, allowed := validStateTransitions[from][to]
			if allowed {
				continue
			}
			if validateTransition(from, to) {
				t.Fatalf("expected invalid transition to be rejected: %s -> %s", from, to)
			}
		}
	}
}

func TestTaskStatusEnumValidityProperty(t *testing.T) {
	valid := []string{"not_started", "in_progress", "pending_review", "under_review", "final_review", "completed", "blocked"}
	for _, status := range valid {
		if !isValidTaskStatus(status) {
			t.Fatalf("expected valid status %q", status)
		}
	}
	invalid := []string{"", "in-progress", "pending", "done", "blocked ", "underreview"}
	for _, status := range invalid {
		if isValidTaskStatus(status) {
			t.Fatalf("expected invalid status %q", status)
		}
	}
}

func TestCriticalityEnumValidityProperty(t *testing.T) {
	valid := []string{"standard", "complex", "security-sensitive"}
	for _, level := range valid {
		if !isValidCriticality(level) {
			t.Fatalf("expected valid criticality %q", level)
		}
	}
	invalid := []string{"", "security", "high", "complex ", "SECURITY"}
	for _, level := range invalid {
		if isValidCriticality(level) {
			t.Fatalf("expected invalid criticality %q", level)
		}
	}
}
