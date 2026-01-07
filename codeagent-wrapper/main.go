package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"reflect"
	"strings"
	"sync/atomic"
	"time"
)

const (
	version               = "5.4.0"
	defaultWorkdir        = "."
	defaultTimeout        = 7200 // seconds (2 hours)
	defaultCoverageTarget = 90.0
	codexLogLineLimit     = 1000
	stdinSpecialChars     = "\n\\\"'`$"
	stderrCaptureLimit    = 4 * 1024
	defaultBackendName    = "codex"
	defaultCodexCommand   = "codex"

	// stdout close reasons
	stdoutCloseReasonWait  = "wait-done"
	stdoutCloseReasonDrain = "drain-timeout"
	stdoutCloseReasonCtx   = "context-cancel"
	stdoutDrainTimeout     = 100 * time.Millisecond
)

var useASCIIMode = os.Getenv("CODEAGENT_ASCII_MODE") == "true"

// Test hooks for dependency injection
var (
	stdinReader  io.Reader = os.Stdin
	isTerminalFn           = defaultIsTerminal
	codexCommand           = defaultCodexCommand
	cleanupHook  func()
	loggerPtr    atomic.Pointer[Logger]

	buildCodexArgsFn   = buildCodexArgs
	selectBackendFn    = selectBackend
	commandContext     = exec.CommandContext
	jsonMarshal        = json.Marshal
	cleanupLogsFn      = cleanupOldLogs
	signalNotifyFn     = signal.Notify
	signalStopFn       = signal.Stop
	terminateCommandFn = terminateCommand
	defaultBuildArgsFn = buildCodexArgs
	runTaskFn          = runCodexTask
	exitFn             = os.Exit
)

var forceKillDelay atomic.Int32

func init() {
	forceKillDelay.Store(5) // seconds - default value
}

func runStartupCleanup() {
	if cleanupLogsFn == nil {
		return
	}
	defer func() {
		if r := recover(); r != nil {
			logWarn(fmt.Sprintf("cleanupOldLogs panic: %v", r))
		}
	}()
	if _, err := cleanupLogsFn(); err != nil {
		logWarn(fmt.Sprintf("cleanupOldLogs error: %v", err))
	}
}

func runCleanupMode() int {
	if cleanupLogsFn == nil {
		fmt.Fprintln(os.Stderr, "Cleanup failed: log cleanup function not configured")
		return 1
	}

	stats, err := cleanupLogsFn()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Cleanup failed: %v\n", err)
		return 1
	}

	fmt.Println("Cleanup completed")
	fmt.Printf("Files scanned: %d\n", stats.Scanned)
	fmt.Printf("Files deleted: %d\n", stats.Deleted)
	if len(stats.DeletedFiles) > 0 {
		for _, f := range stats.DeletedFiles {
			fmt.Printf("  - %s\n", f)
		}
	}
	fmt.Printf("Files kept: %d\n", stats.Kept)
	if len(stats.KeptFiles) > 0 {
		for _, f := range stats.KeptFiles {
			fmt.Printf("  - %s\n", f)
		}
	}
	if stats.Errors > 0 {
		fmt.Printf("Deletion errors: %d\n", stats.Errors)
	}
	return 0
}

func main() {
	exitCode := run()
	exitFn(exitCode)
}

// run is the main logic, returns exit code for testability
func run() (exitCode int) {
	name := currentWrapperName()
	// Handle --version and --help first (no logger needed)
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "--version", "-v":
			fmt.Printf("%s version %s\n", name, version)
			return 0
		case "--help", "-h":
			printHelp()
			return 0
		case "--cleanup":
			return runCleanupMode()
		}
	}

	// Initialize logger for all other commands
	logger, err := NewLogger()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: failed to initialize logger: %v\n", err)
		return 1
	}
	setLogger(logger)

	defer func() {
		logger := activeLogger()
		if logger != nil {
			logger.Flush()
		}
		if err := closeLogger(); err != nil {
			fmt.Fprintf(os.Stderr, "ERROR: failed to close logger: %v\n", err)
		}
		// On failure, extract and display recent errors before removing log
		if logger != nil {
			if exitCode != 0 {
				if errors := logger.ExtractRecentErrors(10); len(errors) > 0 {
					fmt.Fprintln(os.Stderr, "\n=== Recent Errors ===")
					for _, entry := range errors {
						fmt.Fprintln(os.Stderr, entry)
					}
					fmt.Fprintf(os.Stderr, "Log file: %s (deleted)\n", logger.Path())
				}
			}
			if err := logger.RemoveLogFile(); err != nil && !os.IsNotExist(err) {
				// Silently ignore removal errors
			}
		}
	}()
	defer runCleanupHook()

	// Clean up stale logs from previous runs.
	runStartupCleanup()

	// Handle remaining commands
	if len(os.Args) > 1 {
		args := os.Args[1:]
		parallelIndex := -1
		for i, arg := range args {
			if arg == "--parallel" {
				parallelIndex = i
				break
			}
		}

		if parallelIndex != -1 {
			backendName := defaultBackendName
			fullOutput := false
			tmuxSession := ""
			tmuxAttach := false
			windowFor := ""
			stateFile := ""
			isReview := false
			var extras []string

			for i := 0; i < len(args); i++ {
				arg := args[i]
				switch {
				case arg == "--parallel":
					continue
				case arg == "--full-output":
					fullOutput = true
				case arg == "--backend":
					if i+1 >= len(args) {
						fmt.Fprintln(os.Stderr, "ERROR: --backend flag requires a value")
						return 1
					}
					backendName = args[i+1]
					i++
				case strings.HasPrefix(arg, "--backend="):
					value := strings.TrimPrefix(arg, "--backend=")
					if value == "" {
						fmt.Fprintln(os.Stderr, "ERROR: --backend flag requires a value")
						return 1
					}
					backendName = value
				case arg == "--tmux-session":
					if i+1 >= len(args) {
						fmt.Fprintln(os.Stderr, "ERROR: --tmux-session flag requires a value")
						return 1
					}
					tmuxSession = args[i+1]
					i++
				case strings.HasPrefix(arg, "--tmux-session="):
					value := strings.TrimPrefix(arg, "--tmux-session=")
					if value == "" {
						fmt.Fprintln(os.Stderr, "ERROR: --tmux-session flag requires a value")
						return 1
					}
					tmuxSession = value
				case arg == "--tmux-attach":
					tmuxAttach = true
				case strings.HasPrefix(arg, "--tmux-attach="):
					tmuxAttach = parseBoolFlag(strings.TrimPrefix(arg, "--tmux-attach="), tmuxAttach)
				case arg == "--window-for":
					if i+1 >= len(args) {
						fmt.Fprintln(os.Stderr, "ERROR: --window-for flag requires a value")
						return 1
					}
					windowFor = args[i+1]
					i++
				case strings.HasPrefix(arg, "--window-for="):
					value := strings.TrimPrefix(arg, "--window-for=")
					if value == "" {
						fmt.Fprintln(os.Stderr, "ERROR: --window-for flag requires a value")
						return 1
					}
					windowFor = value
				case arg == "--state-file":
					if i+1 >= len(args) {
						fmt.Fprintln(os.Stderr, "ERROR: --state-file flag requires a value")
						return 1
					}
					stateFile = args[i+1]
					i++
				case strings.HasPrefix(arg, "--state-file="):
					value := strings.TrimPrefix(arg, "--state-file=")
					if value == "" {
						fmt.Fprintln(os.Stderr, "ERROR: --state-file flag requires a value")
						return 1
					}
					stateFile = value
				case arg == "--review":
					isReview = true
				case strings.HasPrefix(arg, "--review="):
					isReview = parseBoolFlag(strings.TrimPrefix(arg, "--review="), isReview)
				default:
					extras = append(extras, arg)
				}
			}

			if len(extras) > 0 {
				fmt.Fprintln(os.Stderr, "ERROR: --parallel reads its task configuration from stdin; only --backend, --full-output, and tmux/state flags are allowed.")
				fmt.Fprintln(os.Stderr, "Usage examples:")
				fmt.Fprintf(os.Stderr, "  %s --parallel < tasks.txt\n", name)
				fmt.Fprintf(os.Stderr, "  echo '...' | %s --parallel\n", name)
				fmt.Fprintf(os.Stderr, "  %s --parallel <<'EOF'\n", name)
				fmt.Fprintf(os.Stderr, "  %s --parallel --full-output <<'EOF'  # include full task output\n", name)
				return 1
			}
			if windowFor != "" {
				fmt.Fprintln(os.Stderr, "ERROR: --window-for is only supported in single-task mode")
				return 1
			}

			backend, err := selectBackendFn(backendName)
			if err != nil {
				fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
				return 1
			}
			backendName = backend.Name()

			data, err := io.ReadAll(stdinReader)
			if err != nil {
				fmt.Fprintf(os.Stderr, "ERROR: failed to read stdin: %v\n", err)
				return 1
			}

			cfg, err := parseParallelConfig(data)
			if err != nil {
				fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
				return 1
			}

			cfg.GlobalBackend = backendName
			for i := range cfg.Tasks {
				if strings.TrimSpace(cfg.Tasks[i].Backend) == "" {
					cfg.Tasks[i].Backend = backendName
				}
			}

			timeoutSec := resolveTimeout()
			layers, err := topologicalSort(cfg.Tasks)
			if err != nil {
				fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
				return 1
			}

			var results []TaskResult
			if tmuxSession != "" {
				tmuxMgr := NewTmuxManager(TmuxConfig{
					SessionName: tmuxSession,
					MainWindow:  "main",
					StateFile:   stateFile,
				})
				if err := tmuxMgr.EnsureSession(); err != nil {
					fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
					return 1
				}
				var stateWriter *StateWriter
				if strings.TrimSpace(stateFile) != "" {
					stateWriter = NewStateWriter(stateFile)
				}
				runner := newTmuxTaskRunner(tmuxMgr, stateWriter, isReview, "")
				results = executeConcurrentWithContextAndRunner(context.Background(), layers, timeoutSec, resolveMaxParallelWorkers(), runner.run)
			} else {
				results = executeConcurrent(layers, timeoutSec)
			}

			// Extract structured report fields from each result
			for i := range results {
				results[i].CoverageTarget = defaultCoverageTarget
				if results[i].Message == "" {
					continue
				}

				lines := strings.Split(results[i].Message, "\n")

				// Coverage extraction
				results[i].Coverage = extractCoverageFromLines(lines)
				results[i].CoverageNum = extractCoverageNum(results[i].Coverage)

				// Files changed
				results[i].FilesChanged = extractFilesChangedFromLines(lines)

				// Test results
				results[i].TestsPassed, results[i].TestsFailed = extractTestResultsFromLines(lines)

				// Key output summary
				results[i].KeyOutput = extractKeyOutputFromLines(lines, 150)
			}

			report := buildExecutionReport(results, fullOutput)
			payload, err := jsonMarshal(report)
			if err != nil {
				fmt.Fprintf(os.Stderr, "ERROR: failed to serialize execution report: %v\n", err)
				return 1
			}
			fmt.Println(string(payload))

			exitCode = 0
			for _, res := range results {
				if res.ExitCode != 0 {
					exitCode = res.ExitCode
				}
			}

			if tmuxAttach && tmuxSession != "" {
				_ = attachTmuxSession(tmuxSession)
			}

			return exitCode
		}
	}

	logInfo("Script started")

	cfg, err := parseArgs()
	if err != nil {
		logError(err.Error())
		return 1
	}
	logInfo(fmt.Sprintf("Parsed args: mode=%s, task_len=%d, backend=%s", cfg.Mode, len(cfg.Task), cfg.Backend))

	backend, err := selectBackendFn(cfg.Backend)
	if err != nil {
		logError(err.Error())
		return 1
	}
	cfg.Backend = backend.Name()

	cmdInjected := codexCommand != defaultCodexCommand
	argsInjected := buildCodexArgsFn != nil && reflect.ValueOf(buildCodexArgsFn).Pointer() != reflect.ValueOf(defaultBuildArgsFn).Pointer()

	// Wire selected backend into runtime hooks for the rest of the execution,
	// but preserve any injected test hooks for the default backend.
	if backend.Name() != defaultBackendName || !cmdInjected {
		codexCommand = backend.Command()
	}
	if backend.Name() != defaultBackendName || !argsInjected {
		buildCodexArgsFn = backend.BuildArgs
	}
	logInfo(fmt.Sprintf("Selected backend: %s", backend.Name()))

	timeoutSec := resolveTimeout()
	logInfo(fmt.Sprintf("Timeout: %ds", timeoutSec))
	cfg.Timeout = timeoutSec

	var taskText string
	var piped bool

	if cfg.ExplicitStdin {
		logInfo("Explicit stdin mode: reading task from stdin")
		data, err := io.ReadAll(stdinReader)
		if err != nil {
			logError("Failed to read stdin: " + err.Error())
			return 1
		}
		taskText = string(data)
		if taskText == "" {
			logError("Explicit stdin mode requires task input from stdin")
			return 1
		}
		piped = !isTerminal()
	} else {
		pipedTask, err := readPipedTask()
		if err != nil {
			logError("Failed to read piped stdin: " + err.Error())
			return 1
		}
		piped = pipedTask != ""
		if piped {
			taskText = pipedTask
		} else {
			taskText = cfg.Task
		}
	}

	useStdin := cfg.ExplicitStdin || shouldUseStdin(taskText, piped)

	targetArg := taskText
	if useStdin {
		targetArg = "-"
	}

	if strings.TrimSpace(cfg.TmuxSession) != "" {
		return runTmuxMode(cfg, taskText, useStdin)
	}

	codexArgs := buildCodexArgsFn(cfg, targetArg)

	// Print startup information to stderr
	fmt.Fprintf(os.Stderr, "[%s]\n", name)
	fmt.Fprintf(os.Stderr, "  Backend: %s\n", cfg.Backend)
	fmt.Fprintf(os.Stderr, "  Command: %s %s\n", codexCommand, strings.Join(codexArgs, " "))
	fmt.Fprintf(os.Stderr, "  PID: %d\n", os.Getpid())
	fmt.Fprintf(os.Stderr, "  Log: %s\n", logger.Path())

	if useStdin {
		var reasons []string
		if piped {
			reasons = append(reasons, "piped input")
		}
		if cfg.ExplicitStdin {
			reasons = append(reasons, "explicit \"-\"")
		}
		if strings.Contains(taskText, "\n") {
			reasons = append(reasons, "newline")
		}
		if strings.Contains(taskText, "\\") {
			reasons = append(reasons, "backslash")
		}
		if strings.Contains(taskText, "\"") {
			reasons = append(reasons, "double-quote")
		}
		if strings.Contains(taskText, "'") {
			reasons = append(reasons, "single-quote")
		}
		if strings.Contains(taskText, "`") {
			reasons = append(reasons, "backtick")
		}
		if strings.Contains(taskText, "$") {
			reasons = append(reasons, "dollar")
		}
		if len(taskText) > 800 {
			reasons = append(reasons, "length>800")
		}
		if len(reasons) > 0 {
			logWarn(fmt.Sprintf("Using stdin mode for task due to: %s", strings.Join(reasons, ", ")))
		}
	}

	logInfo(fmt.Sprintf("%s running...", cfg.Backend))

	taskSpec := TaskSpec{
		Task:      taskText,
		WorkDir:   cfg.WorkDir,
		Mode:      cfg.Mode,
		SessionID: cfg.SessionID,
		UseStdin:  useStdin,
	}

	result := runTaskFn(taskSpec, false, cfg.Timeout)

	if result.ExitCode != 0 {
		return result.ExitCode
	}

	fmt.Println(result.Message)
	if result.SessionID != "" {
		fmt.Printf("\n---\nSESSION_ID: %s\n", result.SessionID)
	}

	return 0
}

func setLogger(l *Logger) {
	loggerPtr.Store(l)
}

func closeLogger() error {
	logger := loggerPtr.Swap(nil)
	if logger == nil {
		return nil
	}
	return logger.Close()
}

func activeLogger() *Logger {
	return loggerPtr.Load()
}

func logInfo(msg string) {
	if logger := activeLogger(); logger != nil {
		logger.Info(msg)
	}
}

func logWarn(msg string) {
	if logger := activeLogger(); logger != nil {
		logger.Warn(msg)
	}
}

func logError(msg string) {
	if logger := activeLogger(); logger != nil {
		logger.Error(msg)
	}
}

func runCleanupHook() {
	if logger := activeLogger(); logger != nil {
		logger.Flush()
	}
	if cleanupHook != nil {
		cleanupHook()
	}
}

func printHelp() {
	name := currentWrapperName()
	help := fmt.Sprintf(`%[1]s - Go wrapper for AI CLI backends

Usage:
    %[1]s "task" [workdir]
    %[1]s --backend claude "task" [workdir]
    %[1]s - [workdir]              Read task from stdin
    %[1]s resume <session_id> "task" [workdir]
    %[1]s resume <session_id> - [workdir]
    %[1]s --tmux-session <name> "task" [workdir]
    %[1]s --tmux-session <name> --window-for <task_id> "task" [workdir]
    %[1]s --parallel               Run tasks in parallel (config from stdin)
    %[1]s --parallel --full-output Run tasks in parallel with full output in JSON report
    %[1]s --version
    %[1]s --help

Parallel mode examples:
    %[1]s --parallel < tasks.txt
    echo '...' | %[1]s --parallel
    %[1]s --parallel --full-output < tasks.txt
    %[1]s --parallel <<'EOF'

Environment Variables:
    CODEX_TIMEOUT         Timeout in milliseconds (default: 7200000)
    CODEAGENT_ASCII_MODE  Use ASCII symbols instead of Unicode (PASS/WARN/FAIL)

Tmux Flags:
    --tmux-session <name>  Enable tmux visualization mode
    --tmux-attach          Attach to tmux session after completion
    --window-for <task_id> Create pane in existing task window (single-task mode)
    --state-file <path>    Write AGENT_STATE.json updates
    --review               Mark tasks as review tasks for state updates

Exit Codes:
    0    Success
    1    General error (missing args, no output)
    124  Timeout
    127  backend command not found
    130  Interrupted (Ctrl+C)
    *    Passthrough from backend process`, name)
	fmt.Println(help)
}
