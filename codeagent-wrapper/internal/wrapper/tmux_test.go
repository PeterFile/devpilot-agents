package wrapper

import (
	"fmt"
	"math/rand"
	"testing"
	"time"
)

type tmuxRecorder struct {
	windowNames []string
	paneTargets []string
}

func (r *tmuxRecorder) run(args ...string) (string, error) {
	if len(args) == 0 {
		return "", fmt.Errorf("missing tmux args")
	}
	switch args[0] {
	case "new-window":
		name := argValue(args, "-n")
		if name != "" {
			r.windowNames = append(r.windowNames, name)
		}
		return "@1", nil
	case "split-window":
		target := argValue(args, "-t")
		if target != "" {
			r.paneTargets = append(r.paneTargets, target)
		}
		return "%1", nil
	case "send-keys":
		return "", nil
	default:
		return "", nil
	}
}

func argValue(args []string, key string) string {
	for i := 0; i < len(args)-1; i++ {
		if args[i] == key {
			return args[i+1]
		}
	}
	return ""
}

func generateTasks(rng *rand.Rand, count int) []TaskSpec {
	if count < 1 {
		count = 1
	}
	tasks := make([]TaskSpec, 0, count)
	for i := 0; i < count; i++ {
		id := fmt.Sprintf("task-%02d", i+1)
		task := TaskSpec{ID: id}
		if i > 0 && rng.Intn(2) == 0 {
			depCount := 1 + rng.Intn(min(3, i))
			deps := make([]string, 0, depCount)
			seen := make(map[string]struct{}, depCount)
			for len(deps) < depCount {
				dep := fmt.Sprintf("task-%02d", 1+rng.Intn(i))
				if _, ok := seen[dep]; ok {
					continue
				}
				seen[dep] = struct{}{}
				deps = append(deps, dep)
			}
			task.Dependencies = deps
		}
		tasks = append(tasks, task)
	}
	return tasks
}

func TestSetupTaskPanesPlacementProperty(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	for i := 0; i < 40; i++ {
		rng := rand.New(rand.NewSource(time.Now().UnixNano() + int64(i)))
		recorder := &tmuxRecorder{}
		tmuxCommandFn = recorder.run

		tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
		tasks := generateTasks(rng, 1+rng.Intn(12))
		mapping, err := tm.SetupTaskPanes(tasks)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mapping) != len(tasks) {
			t.Fatalf("expected %d mappings, got %d", len(tasks), len(mapping))
		}

		for _, task := range tasks {
			if len(task.Dependencies) == 0 {
				if mapping[task.ID] != task.ID {
					t.Fatalf("independent task %s mapped to %s", task.ID, mapping[task.ID])
				}
				continue
			}
			dep := task.Dependencies[0]
			if mapping[task.ID] != mapping[dep] {
				t.Fatalf("dependent task %s mapped to %s; expected %s", task.ID, mapping[task.ID], mapping[dep])
			}
		}
	}
}

func TestSetupTaskPanesWindowNamingProperty(t *testing.T) {
	orig := tmuxCommandFn
	t.Cleanup(func() { tmuxCommandFn = orig })

	rng := rand.New(rand.NewSource(42))
	recorder := &tmuxRecorder{}
	tmuxCommandFn = recorder.run

	tm := NewTmuxManager(TmuxConfig{SessionName: "session"})
	tasks := generateTasks(rng, 20)
	_, err := tm.SetupTaskPanes(tasks)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	noDep := make(map[string]struct{})
	for _, task := range tasks {
		if len(task.Dependencies) == 0 {
			noDep[task.ID] = struct{}{}
		}
	}

	if len(recorder.windowNames) != len(noDep) {
		t.Fatalf("expected %d windows, got %d", len(noDep), len(recorder.windowNames))
	}
	for _, name := range recorder.windowNames {
		if _, ok := noDep[name]; !ok {
			t.Fatalf("window name %s does not match an independent task", name)
		}
	}
}
