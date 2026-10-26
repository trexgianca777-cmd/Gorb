#!/usr/bin/env bash
# run-v5.sh — cycle-1 mechanism runs on the kept task set.
# Idempotent per cell.
#
# Usage: ./run-v5.sh [plain|bestof5|revise|selfcon|route]
#   plain    120b, 5 fresh reps (tighter baseline)
#   bestof5  mech-v5.py bestof5, 3 reps
#   revise   mech-v5.py revise (thrash-guard), 3 reps
#   selfcon  mech-v5.py selfcon (single-answer tasks only), 3 reps
#   route    per-task model from router-v5.json (built from same-distribution
#            20b screening), 3 reps
#
# Layout: results/raw/<mech>/<task>/rep<N>/openai_gpt-oss-120b.txt
# (+ meta.json for mech-driven runs; model.txt for route runs)
set -u
V5_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$V5_DIR" || exit 1

MECH="${1:?usage: run-v5.sh [plain|bestof5|revise|selfcon|route]}"
case "$MECH" in plain|bestof5|revise|selfcon|route) ;; *)
  echo "bad mechanism: $MECH" >&2; exit 1;; esac

KEPT_JSON="${V5_KEPT_JSON:-tasks-v5-kept.json}"
RAW_SUB="${V5_RAW_SUB:-raw}"
[ -f "$KEPT_JSON" ] || { echo "FATAL: run select-v5.py first ($KEPT_JSON missing)" >&2; exit 1; }
ROUTER_JSON="${V5_ROUTER_JSON:-router-v5.json}"
if [ "$MECH" = "route" ] && [ ! -f "$ROUTER_JSON" ]; then
  echo "FATAL: $ROUTER_JSON missing (build from 20b screening)" >&2; exit 1
fi

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
export SWARM_REDELEGATE=0
export SWARM_FALLBACK=""
export SWARM_CACHE=0
export SWARM_SKIP_UNHEALTHY=0
export SWARM_STAGGER_SECS=3
export SWARM_TIMEOUT=180
export SWARM_EXCLUDE="allam-2-7b"

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
import json,os
d = json.load(open(os.environ.get('V5_KEPT_JSON','tasks-v5-kept.json')))
print('\n'.join(d['kept_ids']))")

SAFE120="openai_gpt-oss-120b"
REPS=5
[ "$MECH" = "plain" ] || REPS=3

LOG="results/run-v5-$MECH-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "results/$RAW_SUB"

route_model() {
  python3 -c "
import json,os
m = json.load(open(os.environ.get('V5_ROUTER_JSON','router-v5.json')))
print(m.get('$1', 'openai/gpt-oss-120b'))"
}

done_n=0
skip_n=0
for tid in "${TIDS[@]}"; do
  for rep in $(seq 1 "$REPS"); do
    repdir="results/$RAW_SUB/$MECH/$tid/rep$rep"
    mkdir -p "$repdir"
    target="$repdir/$SAFE120.txt"
    if [ -f "$target" ]; then
      skip_n=$((skip_n + 1)); continue
    fi
    echo "--- $MECH $tid rep$rep" | tee -a "$LOG"
    if [ "$MECH" = "plain" ] || [ "$MECH" = "route" ]; then
      if [ "$MECH" = "route" ]; then
        model="$(route_model "$tid")"
      else
        model="openai/gpt-oss-120b"
      fi
      safe="$(printf '%s' "$model" | tr '/:' '__')"
      prompt="$(python3 -c "
import json,sys,os
d = json.load(open(os.environ.get('V5_KEPT_JSON','tasks-v5-kept.json')))
t = next(x for x in d['tasks'] if x['id'] == '$tid')
sys.stdout.write(t['prompt'])")"
      pf="$(mktemp /tmp/v5-prompt-XXXXXX.txt)"
      printf '%s' "$prompt" > "$pf"
      outdir="$(mktemp -d /tmp/v5-out-XXXXXX)"
      run_out="$(SWARM_MODELS="$model" ~/workspace/freellmapi/swarm-call.sh \
        -f "$pf" "$outdir" 2>&1)"
      echo "$run_out" | tail -2 | tee -a "$LOG"
      if [ -f "$outdir/$safe.txt" ]; then
        cp "$outdir/$safe.txt" "$target"
      else
        echo "NO-OUTPUT $MECH $tid rep$rep $model" | tee -a "$LOG"
        printf 'NO-OUTPUT\n' > "$target"
      fi
      printf '%s\n' "$model" > "$repdir/model.txt"
      rm -rf "$outdir" "$pf"
    else
      python3 mech-v5.py --mech "$MECH" --task "$tid" --rep "$rep" \
        --outdir "$repdir" 2>&1 | tee -a "$LOG"
    fi
    done_n=$((done_n + 1))
    sleep 3
  done
done
echo "done: $done_n new cells, $skip_n skipped." | tee -a "$LOG"
