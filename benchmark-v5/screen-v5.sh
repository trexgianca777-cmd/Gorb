#!/usr/bin/env bash
# screen-v5.sh — cycle-1 screening: 3 fresh reps per candidate task per model.
# Idempotent per cell: skips cells whose output file already exists.
#
# Usage: ./screen-v5.sh <model>   (e.g. openai/gpt-oss-120b)
# Optional env: TASKS_JSON (default tasks-v5-candidates.json),
#               OUTSUB (default "screen"), REPS (default 3)
#
# Honest attribution: SWARM_REDELEGATE=0, SWARM_FALLBACK="", SWARM_CACHE=0,
# SWARM_SKIP_UNHEALTHY=0. Layout:
#   results/<OUTSUB>/<task>/rep<1..N>/<safe_model>.txt
set -u
V5_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$V5_DIR" || exit 1

MODEL="${1:?usage: screen-v5.sh <model>}"
TASKS_JSON="${TASKS_JSON:-tasks-v5-candidates.json}"
OUTSUB="${OUTSUB:-screen}"
REPS="${REPS:-3}"

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
export SWARM_REDELEGATE=0
export SWARM_FALLBACK=""
export SWARM_CACHE=0
export SWARM_SKIP_UNHEALTHY=0
export SWARM_STAGGER_SECS=3
export SWARM_TIMEOUT=180
export SWARM_EXCLUDE="allam-2-7b"

# Key: vault loader if present, else DB lookup (in-memory only, never printed).
if [ -f "$HOME/workspace/freellmapi/vault/vault.sh" ]; then
  # shellcheck disable=SC1090
  . "$HOME/workspace/freellmapi/vault/vault.sh"
  swarm_vault_load || { echo "FATAL: vault load failed" >&2; exit 1; }
else
  FREELLMAPI_API_KEY="$(python3 -c "
import sqlite3
db = sqlite3.connect('$HOME/workspace/freellmapi/server/data/freeapi.db')
row = db.execute(\"SELECT value FROM settings WHERE key='unified_api_key'\").fetchone()
print(row[0] if row else '')
")"
  export FREELLMAPI_API_KEY
  [ -n "$FREELLMAPI_API_KEY" ] || { echo "FATAL: no API key resolved" >&2; exit 1; }
fi

# Server must be listening; try a restart if it is not.
if ! curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    http://localhost:3001/api/models | grep -q "401"; then
  echo "server not listening; attempting restart" >&2
  (cd "$HOME/workspace/freellmapi" && nohup node dist/index.js \
    >server.log 2>&1 &) 
  sleep 8
  curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    http://localhost:3001/api/models | grep -q "401" \
    || { echo "FATAL: server still down" >&2; exit 1; }
fi

mapfile -t TIDS < <(python3 -c "
import json
d = json.load(open('$TASKS_JSON'))
print('\n'.join(t['id'] for t in d['tasks']))")

SAFE="$(printf '%s' "$MODEL" | tr '/:' '__')"
LOG="results/screen-$SAFE-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "results/$OUTSUB"

done_n=0
skip_n=0
for tid in "${TIDS[@]}"; do
  prompt="$(python3 -c "
import json,sys
d = json.load(open('$TASKS_JSON'))
t = next(x for x in d['tasks'] if x['id'] == '$tid')
sys.stdout.write(t['prompt'])")"
  pf="$(mktemp /tmp/v5-prompt-XXXXXX.txt)"
  printf '%s' "$prompt" > "$pf"
  for rep in $(seq 1 "$REPS"); do
    repdir="results/$OUTSUB/$tid/rep$rep"
    mkdir -p "$repdir"
    target="$repdir/$SAFE.txt"
    if [ -f "$target" ]; then
      skip_n=$((skip_n + 1)); continue
    fi
    outdir="$(mktemp -d /tmp/v5-out-XXXXXX)"
    echo "--- $OUTSUB $tid rep$rep / $MODEL" | tee -a "$LOG"
    run_out="$(SWARM_MODELS="$MODEL" ~/workspace/freellmapi/swarm-call.sh \
      -f "$pf" "$outdir" 2>&1)"
    echo "$run_out" | tail -3 | tee -a "$LOG"
    if [ -f "$outdir/$SAFE.txt" ]; then
      cp "$outdir/$SAFE.txt" "$target"
    else
      echo "NO-OUTPUT $OUTSUB $tid rep$rep $MODEL" | tee -a "$LOG"
      printf 'NO-OUTPUT\n' > "$target"
    fi
    rm -rf "$outdir"
    done_n=$((done_n + 1))
    sleep 3
  done
  rm -f "$pf"
done
echo "done: $done_n new cells, $skip_n skipped." | tee -a "$LOG"
