package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

type tmuxTaskRunner struct {
	manager     *TmuxManager
	stateWriter *StateWriter
	isReview    bool
	windowFor   string
	mu          sync.Mutex
	windowByTask map[string]string
}

func newTmuxTaskRunner(manager *TmuxManager, stateWriter *StateWriter, isReview bool, windowFor string) *tmuxTaskRunner {
	return &tmuxTaskRunner{
		manager:      manager,
		stateWriter:  stateWriter,
		isReview:     isReview,
		windowFor:    windowFor,
		windowByTask: make(map[string]string),
	}
}

type tmuxTarget struct {
	windowName string
	paneID     string
	target     string
}

func (r *tmuxTaskRunner) prepareTarget(task TaskSpec) (tmuxTarget, error) {
	taskID := strings.TrimSpace(task.ID)
	if taskID == "" {
		return tmuxTarget{}, fmt.Errorf("task id is required")
	}

	if r.windowFor != "" {
		paneID, err := r.manager.CreatePane(r.windowFor)
		if err != nil {
			return tmuxTarget{}, err
		}
		r.mu.Lock()
		r.windowByTask[taskID] = r.windowFor
		r.mu.Unlock()
		return tmuxTarget{
			windowName: r.windowFor,
			paneID:     paneID,
			target:     paneID,
		}, nil
	}

	if len(task.Dependencies) == 0 {
		if _, err := r.manager.CreateWindow(taskID); err != nil {
			return tmuxTarget{}, err
		}
		r.mu.Lock()
		r.windowByTask[taskID] = taskID
		r.mu.Unlock()
		target := fmt.Sprintf("%s:%s", r.manager.config.SessionName, taskID)
		return tmuxTarget{
			windowName: taskID,
			target:     target,
		}, nil
	}

	depID := strings.TrimSpace(task.Dependencies[0])
	r.mu.Lock()
	windowName := r.windowByTask[depID]
	r.mu.Unlock()
	if windowName == "" {
		return tmuxTarget{}, fmt.Errorf("dependency window not found for task %q", taskID)
	}
	paneID, err := r.manager.CreatePane(windowName)
	if err != nil {
		return tmuxTarget{}, err
	}
	r.mu.Lock()
	r.windowByTask[taskID] = windowName
	r.mu.Unlock()
	return tmuxTarget{
		windowName: windowName,
		paneID:     paneID,
		target:     paneID,
	}, nil
}

func (r *tmuxTaskRunner) run(task TaskSpec, timeoutSec int) TaskResult {
	result := TaskResult{TaskID: task.ID}
	if r.manager == nil {
		result.ExitCode = 1
		result.Error = "tmux manager is not configured"
		return result
	}

	if task.WorkDir == "" {
		task.WorkDir = defaultWorkdir
	}
	if task.Mode == "" {
		task.Mode = "new"
	}
	if task.UseStdin || shouldUseStdin(task.Task, false) {
		task.UseStdin = true
	}

	backendName := task.Backend
	if backendName == "" {
		backendName = defaultBackendName
	}
	backend, err := selectBackendFn(backendName)
	if err != nil {
		result.ExitCode = 1
		result.Error = err.Error()
		return result
	}

	target, err := r.prepareTarget(task)
	if err != nil {
		result.ExitCode = 1
		result.Error = err.Error()
		return result
	}

	cfg := &Config{
		Mode:            task.Mode,
		Task:            task.Task,
		SessionID:       task.SessionID,
		WorkDir:         task.WorkDir,
		Backend:         backend.Name(),
		SkipPermissions: envFlagEnabled("CODEAGENT_SKIP_PERMISSIONS"),
	}

	targetArg := task.Task
	if task.UseStdin {
		targetArg = "-"
	}
	args := backend.BuildArgs(cfg, targetArg)

	outPath, err := createTempPath("codeagent-tmux-out-", task.ID)
	if err != nil {
		result.ExitCode = 1
		result.Error = err.Error()
		return result
	}
	errPath, err := createTempPath("codeagent-tmux-err-", task.ID)
	if err != nil {
		result.ExitCode = 1
		result.Error = err.Error()
		return result
	}
	exitPath, err := createTempPath("codeagent-tmux-exit-", task.ID)
	if err != nil {
		result.ExitCode = 1
		result.Error = err.Error()
		return result
	}

	var inputPath string
	if task.UseStdin {
		inputPath, err = createTempPath("codeagent-tmux-input-", task.ID)
		if err != nil {
			result.ExitCode = 1
			result.Error = err.Error()
			return result
		}
		if err := os.WriteFile(inputPath, []byte(task.Task), 0o600); err != nil {
			result.ExitCode = 1
			result.Error = err.Error()
			return result
		}
		defer os.Remove(inputPath)
	}

	doneSignal := fmt.Sprintf("codeagent-done-%s-%d", sanitizeToken(task.ID), time.Now().UnixNano())
	command := buildTmuxCommand(task, backend.Command(), args, outPath, errPath, exitPath, inputPath, doneSignal)
	if err := r.manager.SendCommand(target.target, command); err != nil {
		result.ExitCode = 1
		result.Error = err.Error()
		return result
	}

	windowID := target.windowName
	if r.stateWriter != nil {
		_ = r.stateWriter.WriteTaskResult(TaskResultState{
			TaskID:      task.ID,
			Status:      statusForStart(r.isReview),
			ExitCode:    0,
			WindowID:    windowID,
			PaneID:      target.paneID,
			CompletedAt: time.Now().UTC(),
		})
	}

	ctx := context.Background()
	if timeoutSec > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, time.Duration(timeoutSec)*time.Second)
		defer cancel()
	}
	if err := tmuxWaitForFn(ctx, doneSignal); err != nil {
		result.ExitCode = 124
		result.Error = err.Error()
		if errors.Is(err, context.DeadlineExceeded) {
			result.Error = "tmux task timeout"
		}
		return result
	}

	exitCode, exitErr := readExitCode(exitPath)
	if exitErr != nil {
		exitCode = 1
	}

	message, threadID, parseErr := parseTmuxOutput(outPath)
	result.ExitCode = exitCode
	result.SessionID = threadID
	result.Message = message
	result.LogPath = outPath

	if parseErr != nil && result.ExitCode == 0 {
		result.ExitCode = 1
		result.Error = parseErr.Error()
	}

	if result.ExitCode != 0 && result.Error == "" {
		result.Error = readErrorOutput(errPath)
		if result.Error == "" {
			result.Error = fmt.Sprintf("tmux task exited with status %d", result.ExitCode)
		}
	}

	if r.stateWriter != nil {
		_ = r.stateWriter.WriteTaskResult(TaskResultState{
			TaskID:      task.ID,
			Status:      statusForCompletion(r.isReview, result.ExitCode, result.Error),
			ExitCode:    result.ExitCode,
			Output:      result.Message,
			Error:       result.Error,
			WindowID:    windowID,
			PaneID:      target.paneID,
			CompletedAt: time.Now().UTC(),
		})
	}

	return result
}

func buildTmuxCommand(task TaskSpec, command string, args []string, outPath, errPath, exitPath, inputPath, doneSignal string) string {
	cmdTokens := make([]string, 0, len(args)+1)
	cmdTokens = append(cmdTokens, shellEscape(command))
	for _, arg := range args {
		cmdTokens = append(cmdTokens, shellEscape(arg))
	}
	commandWithArgs := strings.Join(cmdTokens, " ")

	pipeline := commandWithArgs
	if inputPath != "" {
		pipeline = fmt.Sprintf("cat %s | %s", shellEscape(inputPath), commandWithArgs)
	}
	pipeline = fmt.Sprintf("%s 2> %s | tee %s", pipeline, shellEscape(errPath), shellEscape(outPath))

	steps := []string{"set -o pipefail"}
	if task.WorkDir != "" && task.WorkDir != "." {
		steps = append(steps, fmt.Sprintf("cd %s", shellEscape(task.WorkDir)))
	}
	steps = append(steps, pipeline)
	steps = append(steps, fmt.Sprintf("echo $? > %s", shellEscape(exitPath)))
	steps = append(steps, fmt.Sprintf("tmux wait-for -S %s", shellEscape(doneSignal)))
	script := strings.Join(steps, "; ")

	return fmt.Sprintf("bash -lc %s", shellEscape(script))
}

func parseTmuxOutput(path string) (string, string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", "", err
	}
	defer file.Close()

	message, threadID := parseJSONStreamInternal(file, logWarn, logInfo, nil, nil)
	if strings.TrimSpace(message) == "" {
		return "", threadID, fmt.Errorf("tmux task completed without agent_message output")
	}
	return message, threadID, nil
}

func readExitCode(path string) (int, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 1, err
	}
	text := strings.TrimSpace(string(data))
	if text == "" {
		return 1, fmt.Errorf("empty exit code")
	}
	code, err := strconv.Atoi(text)
	if err != nil {
		return 1, err
	}
	return code, nil
}

func readErrorOutput(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	trimmed := strings.TrimSpace(string(data))
	if len(trimmed) > 4000 {
		return trimmed[:4000]
	}
	return trimmed
}

func createTempPath(prefix, taskID string) (string, error) {
	name := sanitizeToken(taskID)
	if name == "" {
		name = "task"
	}
	file, err := os.CreateTemp(os.TempDir(), prefix+name+"-*")
	if err != nil {
		return "", err
	}
	path := file.Name()
	if err := file.Close(); err != nil {
		return "", err
	}
	return path, nil
}

func shellEscape(value string) string {
	if value == "" {
		return "''"
	}
	return "'" + strings.ReplaceAll(value, "'", "'\\''") + "'"
}

func sanitizeToken(value string) string {
	value = strings.TrimSpace(value)
	value = strings.ReplaceAll(value, string(filepath.Separator), "-")
	value = strings.ReplaceAll(value, " ", "-")
	value = strings.ReplaceAll(value, "\t", "-")
	return value
}

func statusForStart(_ bool) string {
	return "in_progress"
}

func statusForCompletion(_ bool, exitCode int, errText string) string {
	if exitCode != 0 || strings.TrimSpace(errText) != "" {
		return "blocked"
	}
	return "pending_review"
}

// tmuxWaitForFn allows testing without invoking tmux.
var tmuxWaitForFn = func(ctx context.Context, signal string) error {
	if ctx == nil {
		return errors.New("context is nil")
	}
	cmd := exec.CommandContext(ctx, "tmux", "wait-for", signal)
	return cmd.Run()
}
