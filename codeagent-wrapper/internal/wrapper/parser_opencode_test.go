package wrapper

import (
	"strings"
	"testing"
)

func TestParseJSONStream_OpenCodeTextEvents(t *testing.T) {
	input := strings.Join([]string{
		`{"type":"text","sessionID":"ses_123","part":{"type":"text","text":"Hello "}}`,
		`{"type":"text","sessionID":"ses_123","part":{"type":"text","text":"world"}}`,
		`{"type":"step_finish","sessionID":"ses_123","part":{"type":"step_finish","reason":"stop"}}`,
	}, "\n")

	var completeCalls int
	message, threadID := parseJSONStreamInternal(
		strings.NewReader(input),
		nil,
		nil,
		nil,
		func() { completeCalls++ },
	)

	if message != "Hello world" {
		t.Fatalf("message=%q, want %q", message, "Hello world")
	}
	if threadID != "ses_123" {
		t.Fatalf("threadID=%q, want %q", threadID, "ses_123")
	}
	if completeCalls != 1 {
		t.Fatalf("completeCalls=%d, want %d", completeCalls, 1)
	}
}

func TestParseJSONStream_OpenCodeToolCallsDoesNotComplete(t *testing.T) {
	input := strings.Join([]string{
		`{"type":"text","sessionID":"ses_123","part":{"type":"text","text":"hello"}}`,
		`{"type":"step_finish","sessionID":"ses_123","part":{"type":"step_finish","reason":"tool-calls"}}`,
	}, "\n")

	var completeCalls int
	message, threadID := parseJSONStreamInternal(
		strings.NewReader(input),
		nil,
		nil,
		nil,
		func() { completeCalls++ },
	)

	if message != "hello" {
		t.Fatalf("message=%q, want %q", message, "hello")
	}
	if threadID != "ses_123" {
		t.Fatalf("threadID=%q, want %q", threadID, "ses_123")
	}
	if completeCalls != 0 {
		t.Fatalf("completeCalls=%d, want %d", completeCalls, 0)
	}
}
