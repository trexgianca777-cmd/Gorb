#!/usr/bin/env bash
# wave2.sh — fill benchmark gaps left by wave 1 (429/502 cooldowns).
# Runs in background; waits for each model's 1h rate-limit window to clear.
set -u
BENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BENCH_DIR" || exit 1

wait_until() { # epoch seconds
  local target="$1" now
  now="$(date +%s)"
  if [ "$now" -lt "$target" ]; then
    echo "sleeping $((target - now))s until $(date -u -d "@$target" '+%H:%M UTC')"
    sleep "$((target - now))"
  fi
}

# Cooldown clear times (1h after last 429/5xx, observed 2026-10-15 ~19:10 UTC):
#   gpt-oss-20b:            clear 19:18 UTC -> run 19:23
#   gemini-3.8-flash:       clear 19:42 UTC -> run 19:47
#   gemini-3.5-flash-lite:  clear 19:44 UTC -> run 19:49
#   gpt-oss-120b:           clear 19:48 UTC -> run 19:53
#   gemini-3-flash-preview: clear 19:50 UTC -> run 19:55
# (5 min margin on each; recompute if the run-2 agent refreshes any 429 mark.)

export SWARM_SKIP_UNHEALTHY=0   # windows cleared; let retry logic handle stragglers
export SWARM_STAGGER_SECS=8

echo "=== wave2a: gpt-oss-20b (10 tasks) ==="
wait_until 1792093400
export SWARM_MODELS="openai/gpt-oss-20b"
./run-benchmark.sh 01-factual-precision 02-multi-step-arithmetic 03-code-prime 04-structured-json 05-constrained-instructions 06-summary-coverage 07-date-reasoning 08-unit-conversion 09-classification 10-calibration-refusal >> results/wave2.out 2>&1

echo "=== wave2b: gemini-3.8-flash (10 tasks) ==="
wait_until 1792094840
export SWARM_MODELS="gemini-3.8-flash"
./run-benchmark.sh 01-factual-precision 02-multi-step-arithmetic 03-code-prime 04-structured-json 05-constrained-instructions 06-summary-coverage 07-date-reasoning 08-unit-conversion 09-classification 10-calibration-refusal >> results/wave2.out 2>&1

echo "=== wave2c: gemini-3.5-flash-lite (tasks 05-10) ==="
wait_until 1792094960
export SWARM_MODELS="gemini-3.5-flash-lite"
./run-benchmark.sh 05-constrained-instructions 06-summary-coverage 07-date-reasoning 08-unit-conversion 09-classification 10-calibration-refusal >> results/wave2.out 2>&1

echo "=== wave2d: gpt-oss-120b (10 tasks) ==="
wait_until 1792095200
export SWARM_MODELS="openai/gpt-oss-120b"
./run-benchmark.sh 01-factual-precision 02-multi-step-arithmetic 03-code-prime 04-structured-json 05-constrained-instructions 06-summary-coverage 07-date-reasoning 08-unit-conversion 09-classification 10-calibration-refusal >> results/wave2.out 2>&1

echo "=== wave2e: gemini-3-flash-preview (task 10) ==="
wait_until 1792095320
export SWARM_MODELS="gemini-3-flash-preview"
./run-benchmark.sh 10-calibration-refusal >> results/wave2.out 2>&1

echo "wave2 complete: $(date -u '+%H:%M UTC')"
