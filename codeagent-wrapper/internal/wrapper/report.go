package wrapper

import "time"

// ExecutionSummary captures aggregate results for a batch run.
type ExecutionSummary struct {
	Total          int     `json:"total"`
	Passed         int     `json:"passed"`
	Failed         int     `json:"failed"`
	BelowCoverage  int     `json:"below_coverage"`
	CoverageTarget float64 `json:"coverage_target"`
	// Aggregate test results across all tasks
	TotalTestsPassed int `json:"total_tests_passed"`
	TotalTestsFailed int `json:"total_tests_failed"`
	// Aggregate file changes across all tasks
	TotalFilesChanged int `json:"total_files_changed"`
	// Average coverage across tasks with coverage data
	AverageCoverage float64 `json:"average_coverage,omitempty"`
}

// ExecutionReport is the structured output for parallel execution.
// This report is returned synchronously to the Orchestrator after all tasks complete.
//
// The report includes both original field names and Python-compatible aliases:
// - tasks / task_results: Array of task results
// - summary.passed / tasks_completed: Count of successful tasks
// - summary.failed / tasks_failed: Count of failed tasks
//
// Requirements: 9.2, 10.1, 10.2, 10.3, 12.8
type ExecutionReport struct {
	Summary     ExecutionSummary `json:"summary"`
	Tasks       []TaskResult     `json:"tasks"`
	GeneratedAt time.Time        `json:"generated_at"`
	// AllFilesChanged is a deduplicated list of all files changed across all tasks
	AllFilesChanged []string `json:"all_files_changed,omitempty"`
	// FailedTaskIDs lists task IDs that failed for quick reference
	FailedTaskIDs []string `json:"failed_task_ids,omitempty"`
	// PendingReviewTaskIDs lists task IDs ready for review
	PendingReviewTaskIDs []string `json:"pending_review_task_ids,omitempty"`

	// Python-compatible fields (aliases for dispatch_batch.py and dispatch_reviews.py)
	// Requirements: 10.1, 10.2, 10.3
	TasksCompleted int          `json:"tasks_completed"`
	TasksFailed    int          `json:"tasks_failed"`
	TaskResults    []TaskResult `json:"task_results"`
	// Review-specific fields for dispatch_reviews.py
	ReviewsCompleted int          `json:"reviews_completed"`
	ReviewsFailed    int          `json:"reviews_failed"`
	ReviewResults    []TaskResult `json:"review_results"`
	// Errors field for Python scripts
	Errors []string `json:"errors,omitempty"`
}

func buildExecutionReport(results []TaskResult, includeMessage bool) ExecutionReport {
	reportCoverageTarget := defaultCoverageTarget
	for _, res := range results {
		if res.CoverageTarget > 0 {
			reportCoverageTarget = res.CoverageTarget
			break
		}
	}

	success := 0
	failed := 0
	belowTarget := 0
	totalTestsPassed := 0
	totalTestsFailed := 0
	totalFilesChanged := 0
	coverageSum := 0.0
	coverageCount := 0

	var failedTaskIDs []string
	var pendingReviewTaskIDs []string
	filesSeen := make(map[string]struct{})
	var allFilesChanged []string

	for _, res := range results {
		// Aggregate test results
		totalTestsPassed += res.TestsPassed
		totalTestsFailed += res.TestsFailed

		// Aggregate files changed (deduplicated)
		for _, f := range res.FilesChanged {
			if _, seen := filesSeen[f]; !seen {
				filesSeen[f] = struct{}{}
				allFilesChanged = append(allFilesChanged, f)
			}
		}
		totalFilesChanged += len(res.FilesChanged)

		// Track coverage for averaging
		if res.CoverageNum > 0 {
			coverageSum += res.CoverageNum
			coverageCount++
		}

		if res.ExitCode == 0 && res.Error == "" {
			success++
			target := res.CoverageTarget
			if target <= 0 {
				target = reportCoverageTarget
			}
			if res.Coverage != "" && target > 0 && res.CoverageNum < target {
				belowTarget++
			}
			// Successful tasks are pending review
			if res.TaskID != "" {
				pendingReviewTaskIDs = append(pendingReviewTaskIDs, res.TaskID)
			}
		} else {
			failed++
			if res.TaskID != "" {
				failedTaskIDs = append(failedTaskIDs, res.TaskID)
			}
		}
	}

	// Calculate average coverage
	var avgCoverage float64
	if coverageCount > 0 {
		avgCoverage = coverageSum / float64(coverageCount)
	}

	tasks := make([]TaskResult, len(results))
	copy(tasks, results)
	if !includeMessage {
		for i := range tasks {
			tasks[i].Message = ""
		}
	}

	return ExecutionReport{
		Summary: ExecutionSummary{
			Total:             len(results),
			Passed:            success,
			Failed:            failed,
			BelowCoverage:     belowTarget,
			CoverageTarget:    reportCoverageTarget,
			TotalTestsPassed:  totalTestsPassed,
			TotalTestsFailed:  totalTestsFailed,
			TotalFilesChanged: totalFilesChanged,
			AverageCoverage:   avgCoverage,
		},
		Tasks:                tasks,
		GeneratedAt:          time.Now().UTC(),
		AllFilesChanged:      allFilesChanged,
		FailedTaskIDs:        failedTaskIDs,
		PendingReviewTaskIDs: pendingReviewTaskIDs,
		// Python-compatible fields (Requirements: 10.1, 10.2, 10.3)
		TasksCompleted:   success,
		TasksFailed:      failed,
		TaskResults:      tasks,
		ReviewsCompleted: success, // Same as tasks for review mode
		ReviewsFailed:    failed,
		ReviewResults:    tasks,
		Errors:           nil, // Populated by caller if needed
	}
}
