#!/usr/bin/env bash
# wave3.sh — remaining benchmark gaps after wave2.sh died mid-task-09.
set -u
BENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BENCH_DIR" || exit 1
export SWARM_SKIP_UNHEALTHY=0
export SWARM_STAGGER_SECS=8

echo "=== wave3a: gemini-3.5-flash-lite tasks 05-10 ==="
SWARM_MODELS="gemini-3.5-flash-lite" ./run-benchmark.sh \
  05-constrained-instructions 06-summary-coverage 07-date-reasoning \
  08-unit-conversion 09-classification 10-calibration-refusal >> results/wave3.out 2>&1

echo "=== wave3b: gpt-oss-120b all 10 tasks ==="
SWARM_MODELS="openai/gpt-oss-120b" ./run-benchmark.sh \
  01-factual-precision 02-multi-step-arithmetic 03-code-prime 04-structured-json \
  05-constrained-instructions 06-summary-coverage 07-date-reasoning \
  08-unit-conversion 09-classification 10-calibration-refusal >> results/wave3.out 2>&1

echo "=== wave3c: gemini-3-flash-preview task 10 ==="
SWARM_MODELS="gemini-3-flash-preview" ./run-benchmark.sh \
  10-calibration-refusal >> results/wave3.out 2>&1

echo "=== wave3d: gemini-3.8-flash tasks 09-10 (best effort) ==="
SWARM_MODELS="gemini-3.8-flash" ./run-benchmark.sh \
  09-classification 10-calibration-refusal >> results/wave3.out 2>&1

echo "wave3 complete: $(date -u '+%H:%M UTC')"
