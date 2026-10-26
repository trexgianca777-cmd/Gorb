#!/usr/bin/env bash
# run-v4.sh — benchmark v4 measurement runs. Idempotent per cell: skips cells
# whose output file already exists, so interrupted runs resume cleanly.
#
# Usage: ./run-v4.sh [plain|route|revise]
#   plain  — openai/gpt-oss-120b, 3 fresh reps per task (baseline)
#   route  — per-task routed model (pre-registered map, see ROUTER.md), 3 reps
#   revise — revise-v4.py: 120b generator + mechanical verifier, <=2 revisions, 3 reps
#
# Honest attribution: SWARM_REDELEGATE=0, SWARM_FALLBACK="" (no silent
# substitution), SWARM_SKIP_UNHEALTHY=0 (every cell gets a real attempt),
# SWARM_CACHE=0 (fresh calls). Layout:
#   results/raw/<mechanism>/<task>/rep<1..3>/<safe_model>.txt
set -u
V4_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$V4_DIR" || exit 1

MECH="${1:?usage: run-v4.sh [plain|route|revise]}"
case "$MECH" in plain|route|revise) ;; *) echo "bad mechanism: $MECH" >&2; exit 1;; esac

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
export SWARM_REDELEGATE=0
export SWARM_FALLBACK=""
export SWARM_CACHE=0
export SWARM_SKIP_UNHEALTHY=0
export SWARM_STAGGER_SECS=3
export SWARM_TIMEOUT=180
export SWARM_EXCLUDE="allam-2-7b"

# Unified API key resolved in-memory from the server DB (never printed).
FREELLMAPI_API_KEY="$(python3 -c "
import sqlite3
db = sqlite3.connect('$HOME/workspace/freellmapi/server/data/freeapi.db')
row = db.execute(\"SELECT value FROM settings WHERE key='unified_api_key'\").fetchone()
print(row[0] if row else '')
")"
export FREELLMAPI_API_KEY
[ -n "$FREELLMAPI_API_KEY" ] || { echo "FATAL: no API key resolved" >&2; exit 1; }

BASE_MODEL="openai/gpt-oss-120b"
CODE_MODEL="openai/gpt-oss-20b"

# Pre-registered routing rule (ROUTER.md): code tasks -> the model that went
# 8/8 on v3 and was best on v3's code tasks; everything else -> 120b (v3 best
# overall at 7/8). Chosen a priori from v3 evidence, not from v4 results.
route_model() {
  case "$1" in
    01-code-evaluator-2|02-code-sjson|03-code-wildcard|04-code-base-convert|15-code-caesar|16-code-roman)
      printf '%s' "$CODE_MODEL" ;;
    *)
      printf '%s' "$BASE_MODEL" ;;
  esac
}

mapfile -t TASKS < <(python3 -c "
import json
d = json.load(open('tasks-v4.json'))
for t in d['tasks']: print(t['id'])")

LOG="results/run-v4-$MECH-$(date +%Y%m%d-%H%M%S).log"
mkdir -p results/raw

done_n=0
skip_n=0
for tid in "${TASKS[@]}"; do
  echo "=== $tid ===" | tee -a "$LOG"
  prompt="$(python3 -c "
import json,sys
d = json.load(open('tasks-v4.json'))
t = next(x for x in d['tasks'] if x['id'] == '$tid')
sys.stdout.write(t['prompt'])")"
  pf="$(mktemp /tmp/v4-prompt-XXXXXX.txt)"
  printf '%s' "$prompt" > "$pf"
  for rep in 1 2 3; do
    repdir="results/raw/$MECH/$tid/rep$rep"
    mkdir -p "$repdir"
    if [ "$MECH" = "revise" ]; then
      target="$repdir/openai_gpt-oss-120b.txt"
      if [ -f "$target" ]; then
        echo "SKIP (have output) $MECH $tid rep$rep" | tee -a "$LOG"
        skip_n=$((skip_n + 1)); continue
      fi
      echo "--- $MECH $tid rep$rep (revise loop)" | tee -a "$LOG"
      python3 revise-v4.py --task "$tid" --rep "$rep" \
        --generator "$BASE_MODEL" --max-revisions 2 \
        --outdir "$repdir" >>"$LOG" 2>&1
      done_n=$((done_n + 1))
    else
      if [ "$MECH" = "route" ]; then
        model="$(route_model "$tid")"
      else
        model="$BASE_MODEL"
      fi
      safe="$(printf '%s' "$model" | tr '/:' '__')"
      target="$repdir/$safe.txt"
      if [ -f "$target" ]; then
        echo "SKIP (have output) $MECH $tid rep$rep $model" | tee -a "$LOG"
        skip_n=$((skip_n + 1)); continue
      fi
      outdir="$(mktemp -d /tmp/v4-out-XXXXXX)"
      echo "--- $MECH $tid rep$rep / $model" | tee -a "$LOG"
      run_out="$(SWARM_MODELS="$model" ~/workspace/freellmapi/swarm-call.sh -f "$pf" "$outdir" 2>&1)"
      echo "$run_out" | tee -a "$LOG"
      if [ -f "$outdir/$safe.txt" ]; then
        cp "$outdir/$safe.txt" "$target"
        echo "SAVED $target" | tee -a "$LOG"
      else
        echo "NO-OUTPUT $MECH $tid rep$rep $model" | tee -a "$LOG"
      fi
      [ -f "$repdir/model.txt" ] || printf '%s\n' "$model" > "$repdir/model.txt"
      [ -f "$outdir/timings.tsv" ] && cat "$outdir/timings.tsv" >> "$repdir/timings.tsv"
      rm -rf "$outdir"
      done_n=$((done_n + 1))
    fi
    sleep 3
  done
  rm -f "$pf"
done
echo "done: $done_n new cells, $skip_n skipped (already had output)." | tee -a "$LOG"
