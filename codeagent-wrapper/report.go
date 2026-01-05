package main

import "time"

// ExecutionSummary captures aggregate results for a batch run.
type ExecutionSummary struct {
	Total          int     `json:"total"`
	Passed         int     `json:"passed"`
	Failed         int     `json:"failed"`
	BelowCoverage  int     `json:"below_coverage"`
	CoverageTarget float64 `json:"coverage_target"`
}

// ExecutionReport is the structured output for parallel execution.
type ExecutionReport struct {
	Summary     ExecutionSummary `json:"summary"`
	Tasks       []TaskResult     `json:"tasks"`
	GeneratedAt time.Time        `json:"generated_at"`
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
	for _, res := range results {
		if res.ExitCode == 0 && res.Error == "" {
			success++
			target := res.CoverageTarget
			if target <= 0 {
				target = reportCoverageTarget
			}
			if res.Coverage != "" && target > 0 && res.CoverageNum < target {
				belowTarget++
			}
		} else {
			failed++
		}
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
			Total:          len(results),
			Passed:         success,
			Failed:         failed,
			BelowCoverage:  belowTarget,
			CoverageTarget: reportCoverageTarget,
		},
		Tasks:       tasks,
		GeneratedAt: time.Now().UTC(),
	}
}
