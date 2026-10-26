#!/usr/bin/env bash
# run-benchmark.sh — run benchmark tasks through the swarm, saving raw outputs.
# Usage: ./run-benchmark.sh [task-id ...]   (default: all tasks in tasks.json)
# Env knobs honored: SWARM_MODE (default wide), SWARM_SKIP_UNHEALTHY (default 1).
set -u
BENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BENCH_DIR" || exit 1

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
export SWARM_EXCLUDE="${SWARM_EXCLUDE:-allam-2-7b}"
export SWARM_SKIP_UNHEALTHY="${SWARM_SKIP_UNHEALTHY:-1}"
export SWARM_STAGGER_SECS="${SWARM_STAGGER_SECS:-5}"
export SWARM_MODE="${SWARM_MODE:-wide}"
export SWARM_PRESET="${SWARM_PRESET:-default}"
export SWARM_TIMEOUT="${SWARM_TIMEOUT:-120}"

# Unified API key resolved in-memory from the server DB (never printed).
FREELLMAPI_API_KEY="$(python3 -c "
import sqlite3
db = sqlite3.connect('$HOME/workspace/freellmapi/server/data/freeapi.db')
row = db.execute(\"SELECT value FROM settings WHERE key='unified_api_key'\").fetchone()
print(row[0] if row else '')
")"
export FREELLMAPI_API_KEY
[ -n "$FREELLMAPI_API_KEY" ] || { echo "FATAL: no API key resolved" >&2; exit 1; }

TASKS=("$@")
if [ ${#TASKS[@]} -eq 0 ]; then
  mapfile -t TASKS < <(python3 -c "
import json
d = json.load(open('tasks.json'))
for t in d['tasks']: print(t['id'])")
fi

LOG="results/run-$(date +%Y%m%d-%H%M%S).log"
mkdir -p results/raw

for tid in "${TASKS[@]}"; do
  echo "=== $tid ===" | tee -a "$LOG"
  prompt="$(python3 -c "
import json,sys
d = json.load(open('tasks.json'))
t = next(x for x in d['tasks'] if x['id'] == '$tid')
sys.stdout.write(t['prompt'])")"
  pf="$(mktemp /tmp/bench-prompt-XXXXXX.txt)"
  printf '%s' "$prompt" > "$pf"
  outdir="$(mktemp -d /tmp/bench-out-XXXXXX)"
  run_out="$(../swarm-call.sh -f "$pf" "$outdir" 2>&1)"
  echo "$run_out" | tee -a "$LOG"
  mkdir -p "results/raw/$tid"
  for f in "$outdir"/*.txt; do
    [ -f "$f" ] || continue
    bn="$(basename "$f")"
    [ "$bn" = "prompt.txt" ] && continue
    cp "$f" "results/raw/$tid/$bn"
  done
  rm -f "$pf"; rm -rf "$outdir"
done
echo "done. raw outputs in results/raw/" | tee -a "$LOG"
