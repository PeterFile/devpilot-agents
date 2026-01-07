package main

import "fmt"

var validTaskStatuses = map[string]struct{}{
	"not_started":   {},
	"in_progress":   {},
	"pending_review": {},
	"under_review":  {},
	"final_review":  {},
	"completed":     {},
	"blocked":       {},
}

var validCriticalityLevels = map[string]struct{}{
	"standard":          {},
	"complex":           {},
	"security-sensitive": {},
}

var validStateTransitions = map[string]map[string]struct{}{
	"not_started": {
		"in_progress": {},
		"blocked":     {},
	},
	"in_progress": {
		"pending_review": {},
		"blocked":        {},
	},
	"pending_review": {
		"under_review": {},
	},
	"under_review": {
		"final_review": {},
	},
	"final_review": {
		"completed":  {},
		"in_progress": {},
	},
	"blocked": {
		"in_progress": {},
		"not_started": {},
	},
	"completed": {},
}

func isValidTaskStatus(status string) bool {
	_, ok := validTaskStatuses[status]
	return ok
}

func isValidCriticality(level string) bool {
	_, ok := validCriticalityLevels[level]
	return ok
}

func validateTransition(from, to string) bool {
	if to == "" {
		logError("state transition rejected: empty target status")
		return false
	}
	if from == "" && to == "not_started" {
		return true
	}
	if from == "" {
		from = "not_started"
	}
	allowed := validStateTransitions[from]
	if allowed == nil {
		logError(fmt.Sprintf("state transition rejected: unknown from status %q", from))
		return false
	}
	if _, ok := allowed[to]; !ok {
		logError(fmt.Sprintf("state transition rejected: %s -> %s", from, to))
		return false
	}
	return true
}
