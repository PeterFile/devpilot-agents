#!/bin/bash
# Sequential Runner - Ralph-style single-task-per-iteration loop
# Self-contained, no external dependencies
# Usage: ./runner.sh --spec <spec_path> [--max-iterations N] [--delay SECONDS]

set -e

# Defaults
MAX_ITERATIONS=50
DELAY=5
SPEC_PATH=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --spec)
            SPEC_PATH="$2"
            shift 2
            ;;
        --max-iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        --delay)
            DELAY="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$SPEC_PATH" ]; then
    echo "Usage: ./runner.sh --spec <spec_path> [--max-iterations N] [--delay SECONDS]"
    exit 1
fi

# Resolve paths
# Spec: .kiro/specs/my-feature/
# State: .kiro/specs/sequential_state.json (parent of spec)
SPEC_DIR="$(cd "$SPEC_PATH" && pwd)"
PARENT_DIR="$(dirname "$SPEC_DIR")"
STATE_FILE="$PARENT_DIR/sequential_state.json"
PROGRESS_FILE="$PARENT_DIR/sequential_progress.txt"

# Initialize state if not exists
if [ ! -f "$STATE_FILE" ]; then
    echo '{"completed": []}' > "$STATE_FILE"
    echo "# Sequential Execution Progress" > "$PROGRESS_FILE"
    echo "" >> "$PROGRESS_FILE"
    echo "Spec: $SPEC_DIR" >> "$PROGRESS_FILE"
    echo "Started: $(date -Iseconds)" >> "$PROGRESS_FILE"
    echo "" >> "$PROGRESS_FILE"
fi

# Resolve codeagent-wrapper
resolve_wrapper() {
    if [ -n "$CODEAGENT_WRAPPER" ]; then
        echo "$CODEAGENT_WRAPPER"
    elif command -v codeagent-wrapper &> /dev/null; then
        echo "codeagent-wrapper"
    else
        echo "codeagent-wrapper"
    fi
}

# Build prompt with paths injected
build_prompt() {
    cat "$SCRIPT_DIR/prompt.md" | \
        sed "s|{{SPEC_PATH}}|$SPEC_DIR|g" | \
        sed "s|{{STATE_FILE}}|$STATE_FILE|g" | \
        sed "s|{{PROGRESS_FILE}}|$PROGRESS_FILE|g"
}

WRAPPER=$(resolve_wrapper)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Sequential Runner - Self-Contained                          ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Spec:       $SPEC_DIR"
echo "║  State:      $STATE_FILE"
echo "║  Progress:   $PROGRESS_FILE"
echo "║  Max Iter:   $MAX_ITERATIONS"
echo "║  Delay:      ${DELAY}s between iterations"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Iteration $i of $MAX_ITERATIONS"
    echo "═══════════════════════════════════════════════════════════"
    
    # Build and send prompt to agent
    PROMPT=$(build_prompt)
    OUTPUT=$($WRAPPER - <<< "$PROMPT" 2>&1 | tee /dev/stderr) || true
    
    # Check for completion signal
    if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
        echo ""
        echo "✅ All tasks completed!"
        echo "   Finished at iteration $i of $MAX_ITERATIONS"
        echo "" >> "$PROGRESS_FILE"
        echo "Completed: $(date -Iseconds)" >> "$PROGRESS_FILE"
        exit 0
    fi
    
    # Check for halt signal
    if echo "$OUTPUT" | grep -q "<promise>HALT</promise>"; then
        echo ""
        echo "⏸️  Halted - Human input required"
        exit 2
    fi
    
    echo "[sequential] Iteration $i complete. Sleeping ${DELAY}s..."
    sleep "$DELAY"
done

echo ""
echo "⚠️  Reached max iterations ($MAX_ITERATIONS) without completing all tasks."
echo "   Check $STATE_FILE for remaining tasks."
exit 1
