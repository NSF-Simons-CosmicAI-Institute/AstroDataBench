#!/usr/bin/env bash
# One-shot entrypoint: run the candidate model over the task bank, grade every
# response with the judge model, and build the summary report.
#
# Usage:
#   ./scripts/run_benchmark.sh [--model claude-sonnet-5] [--judge-model claude-opus-5]
#                               [--filter category=optical] [--trials 1] [--run-id <id>]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
MODEL=""
JUDGE_MODEL=""
FILTER=""
TRIALS="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --judge-model) JUDGE_MODEL="$2"; shift 2 ;;
    --filter) FILTER="$2"; shift 2 ;;
    --trials) TRIALS="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

RUN_ARGS=(--run-id "$RUN_ID" --trials "$TRIALS")
GRADE_ARGS=(--run-id "$RUN_ID")
[[ -n "$MODEL" ]] && RUN_ARGS+=(--model "$MODEL")
[[ -n "$JUDGE_MODEL" ]] && GRADE_ARGS+=(--judge-model "$JUDGE_MODEL")
[[ -n "$FILTER" ]] && RUN_ARGS+=(--filter "$FILTER")

echo "== Run $RUN_ID: generating candidate answers =="
python3 "$SCRIPT_DIR/run.py" "${RUN_ARGS[@]}"

echo "== Run $RUN_ID: grading with judge model =="
python3 "$SCRIPT_DIR/grade.py" "${GRADE_ARGS[@]}"

echo "== Run $RUN_ID: building report =="
python3 "$SCRIPT_DIR/report.py" --run-id "$RUN_ID"

echo
echo "Done. Results: $ROOT_DIR/results/$RUN_ID/summary.csv"
