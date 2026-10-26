#!/usr/bin/env bash
# screen-model.sh — run one model through benchmark v3 and report its score.
# Usage: ./screen-model.sh <model-id>
# Example: ./screen-model.sh "qwen/qwen3-32b:free"
#
# Compares against the bar: gpt-oss-120b scored 7/8 on the reference run.
# A model worth adding to the roster beats 7/8 or fills a gap (passes a task
# the current roster fails). All calls fresh (SWARM_CACHE=0).
set -u
V3_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL="${1:?usage: screen-model.sh <model-id>}"
SAFE="$(printf '%s' "$MODEL" | tr '/:' '__')"

export no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"
export SWARM_REDELEGATE=0 SWARM_CACHE=0 SWARM_SKIP_UNHEALTHY=0
export SWARM_STAGGER_SECS=5

# API key: environment only, never files (same pattern as run-benchmark.sh).
if [ -z "${FREELLMAPI_API_KEY:-}" ]; then
  FREELLMAPI_API_KEY="$(python3 -c "
import sqlite3, os
db = sqlite3.connect(os.path.expandvars('\$HOME/workspace/freellmapi/server/data/freeapi.db'))
row = db.execute(\"SELECT value FROM settings WHERE key='unified_api_key'\").fetchone()
print(row[0] if row else '')
")"
  export FREELLMAPI_API_KEY
fi
[ -n "$FREELLMAPI_API_KEY" ] || { echo "FATAL: no API key resolved" >&2; exit 1; }

OUTDIR="$(mktemp -d /tmp/screen-model-XXXXXX)"
mapfile -t TASKS < <(python3 -c "
import json
d = json.load(open('$V3_DIR/tasks-v3.json'))
print('\n'.join(t['id'] for t in d['tasks']))")

for tid in "${TASKS[@]}"; do
  prompt="$(python3 -c "
import json
d = json.load(open('$V3_DIR/tasks-v3.json'))
t = next(x for x in d['tasks'] if x['id'] == '$tid')
print(t['prompt'], end='')")"
  pf="$(mktemp /tmp/screen-prompt-XXXXXX.txt)"
  printf '%s' "$prompt" > "$pf"
  SWARM_MODELS="$MODEL" "$HOME/workspace/freellmapi/swarm-call.sh" -f "$pf" "$OUTDIR/$tid" >/dev/null 2>&1
  mkdir -p "$V3_DIR/results/screening/$SAFE"
  f="$OUTDIR/$tid/${SAFE}.txt"
  [ -f "$f" ] && cp "$f" "$V3_DIR/results/screening/$SAFE/$tid.txt"
  rm -f "$pf"
done
rm -rf "$OUTDIR"

echo "=== $MODEL ==="
python3 - "$V3_DIR" "$SAFE" <<'EOF'
import json, sys, importlib.util
v3dir, safe = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("sv3", f"{v3dir}/score-v3.py")
sv3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(sv3)
tasks = json.load(open(f"{v3dir}/tasks-v3.json"))["tasks"]
p = 0
for t in tasks:
    try:
        out = open(f"{v3dir}/results/screening/{safe}/{t['id']}.txt").read()
    except FileNotFoundError:
        print(f"  {t['id']}: NO OUTPUT"); continue
    ok, detail = sv3.SCORERS[t["scorer"]](out, t)
    p += ok
    print(f"  {t['id']}: {'PASS' if ok else 'FAIL'}")
print(f"TOTAL: {p}/{len(tasks)}  (bar: gpt-oss-120b 7/8)")
EOF
