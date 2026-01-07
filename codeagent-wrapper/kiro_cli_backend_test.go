package main

import (
	"reflect"
	"testing"
)

func TestKiroCliBackendBuildArgs(t *testing.T) {
	backend := KiroCliBackend{}
	cfg := &Config{WorkDir: "/tmp"}
	args := backend.BuildArgs(cfg, "task")
	expected := []string{"chat", "-C", "/tmp", "--json", "task"}
	if !reflect.DeepEqual(args, expected) {
		t.Fatalf("expected %v, got %v", expected, args)
	}

	cfg = &Config{WorkDir: "."}
	args = backend.BuildArgs(cfg, "task")
	expected = []string{"chat", "--json", "task"}
	if !reflect.DeepEqual(args, expected) {
		t.Fatalf("expected %v, got %v", expected, args)
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
