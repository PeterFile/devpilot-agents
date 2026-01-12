package main

import (
	"reflect"
	"testing"
)

func TestKiroCliBackendBuildArgs(t *testing.T) {
	backend := KiroCliBackend{}
	cfg := &Config{WorkDir: "/tmp"}
	args := backend.BuildArgs(cfg, "hello world")
	// Expected: chat --no-interactive --trust-all-tools -C /tmp "hello world"
	expected := []string{"chat", "--no-interactive", "--trust-all-tools", "-C", "/tmp", "hello world"}
	if !reflect.DeepEqual(args, expected) {
		t.Fatalf("expected %v, got %v", expected, args)
	}

	cfg = &Config{WorkDir: "."}
	args = backend.BuildArgs(cfg, "test prompt")
	// Expected: chat --no-interactive --trust-all-tools "test prompt"
	expected = []string{"chat", "--no-interactive", "--trust-all-tools", "test prompt"}
	if !reflect.DeepEqual(args, expected) {
		t.Fatalf("expected %v, got %v", expected, args)
	}

	// Test with nil config
	args = backend.BuildArgs(nil, "hello world")
	expected = []string{"chat", "--no-interactive", "--trust-all-tools", "hello world"}
	if !reflect.DeepEqual(args, expected) {
		t.Fatalf("expected %v, got %v", expected, args)
	}

	// Test empty targetArg
	args = backend.BuildArgs(nil, "")
	expected = []string{"chat", "--no-interactive", "--trust-all-tools"}
	if !reflect.DeepEqual(args, expected) {
		t.Fatalf("expected %v, got %v", expected, args)
	}
}

func TestKiroCliBackendSupportsStdin(t *testing.T) {
	backend := KiroCliBackend{}
	if backend.SupportsStdin() {
		t.Fatal("KiroCliBackend should not support stdin")
	}
}

func TestKiroCliBackendRegistration(t *testing.T) {
	backend, err := selectBackend("kiro-cli")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if backend.Name() != "kiro-cli" {
		t.Fatalf("expected backend name kiro-cli, got %s", backend.Name())
	}
}
