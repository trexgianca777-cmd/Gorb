#!/usr/bin/env bash
# route.sh — per-task-type router for SwarmZero benchmark v2.
# Usage: ./route.sh <task-id>   (e.g. ./route.sh 01-factual-precision)
#
# Looks up the task's category in router-map.json, picks the top-ranked
# model for that category, and runs the v1 task prompt through
# ~/workspace/freellmapi/swarm-call.sh with SWARM_MODELS set to that
# single model. On transport failure (non-200 / empty output), falls back
# to the next model in the ranked list. Max 3 attempts.
#
# Prints SELECTED_MODEL=<model> and the model output on success.
# Exit 0 on success, 1 if all attempts fail.
#
# Read-only use of ~/workspace/freellmapi/swarm-call.sh: nothing under
# ~/workspace/freellmapi/ is modified. The API key is resolved inside
# swarm-call.sh itself and is never printed or logged here.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAP="$SCRIPT_DIR/router-map.json"
TASKS_JSON="$SCRIPT_DIR/../benchmark/tasks.json"
SWARM_CALL="$HOME/workspace/freellmapi/swarm-call.sh"

[ -n "${1:-}" ] || { echo "usage: route.sh <task-id>" >&2; exit 2; }
TASK_ID="$1"

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"

# Unified API key resolved in-memory from the server DB (never printed,
# never logged). Same pattern as benchmark/run-benchmark.sh.
FREELLMAPI_API_KEY="$(python3 -c "
import sqlite3, os
db = sqlite3.connect(os.path.expandvars('\$HOME/workspace/freellmapi/server/data/freeapi.db'))
row = db.execute(\"SELECT value FROM settings WHERE key='unified_api_key'\").fetchone()
print(row[0] if row else '')
")"
export FREELLMAPI_API_KEY
[ -n "$FREELLMAPI_API_KEY" ] || { echo "route.sh: FATAL: no API key resolved" >&2; exit 1; }

export SWARM_CACHE="${SWARM_CACHE:-1}"
# Clean per-attempt attribution: disable the script's internal redelegation
# and fallback-rescue so each attempt is genuinely one model. route.sh does
# its own fallback across the ranked list.
export SWARM_REDELEGATE=0
export SWARM_FALLBACK=""
export SWARM_TIMEOUT="${SWARM_TIMEOUT:-120}"

CATEGORY="$(python3 -c "
import json
m = json.load(open('$MAP'))
print(m['task_to_category']['$TASK_ID'])
")"
[ -n "$CATEGORY" ] || { echo "route.sh: unknown task id '$TASK_ID'" >&2; exit 2; }

mapfile -t MODELS < <(python3 -c "
import json
m = json.load(open('$MAP'))
for x in m['categories']['$CATEGORY']['ranked_models']:
    print(x)
")
[ "${#MODELS[@]}" -gt 0 ] || { echo "route.sh: no models for category '$CATEGORY'" >&2; exit 2; }

PROMPT_FILE="$(mktemp /tmp/route-prompt-XXXXXX.txt)"
python3 -c "
import json, sys
d = json.load(open('$TASKS_JSON'))
t = next(x for x in d['tasks'] if x['id'] == '$TASK_ID')
sys.stdout.write(t['prompt'])
" > "$PROMPT_FILE"

MAX_ATTEMPTS=3
attempt=0
for model in "${MODELS[@]}"; do
  attempt=$((attempt + 1))
  [ "$attempt" -le "$MAX_ATTEMPTS" ] || break
  echo "route.sh: attempt $attempt/$MAX_ATTEMPTS task=$TASK_ID category=$CATEGORY model=$model" >&2
  outdir="$(mktemp -d /tmp/route-out-XXXXXX)"
  SWARM_MODELS="$model" "$SWARM_CALL" -f "$PROMPT_FILE" "$outdir" >/dev/null 2>&1
  outfile=""
  for f in "$outdir"/*.txt; do
    [ -f "$f" ] || continue
    [ "$(basename "$f")" = "prompt.txt" ] && continue
    [ -s "$f" ] && outfile="$f"
  done
  if [ -n "$outfile" ]; then
    echo "SELECTED_MODEL=$model"
    cat "$outfile"
    rm -f "$PROMPT_FILE"
    rm -rf "$outdir"
    exit 0
  fi
  echo "route.sh: attempt $attempt produced no output from $model; falling back" >&2
  rm -rf "$outdir"
done

rm -f "$PROMPT_FILE"
echo "route.sh: all $MAX_ATTEMPTS attempts failed for task $TASK_ID" >&2
exit 1
