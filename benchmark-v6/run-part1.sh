#!/usr/bin/env bash
# run-part1.sh — Part 1: baseline + 5 candidates on the 12 kept hard tasks.
# One time window for paired comparison. Idempotent per cell (skips done).
set -u
V6="$(cd "$(dirname "$0")" && pwd)"
cd "$V6" || exit 1
export MECH_KEPT_JSON=tasks-v5-kept2.json
. "$HOME/workspace/freellmapi/vault/vault.sh" || exit 1
swarm_vault_load || exit 1
export FREELLMAPI_API_KEY no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"

TASKS="c1-expr-eval-3 c10-sexpr l1-knights-6 p3-unicode-json p8-bizdays p9-sexpr-let q3-zebra-5 q8-mastermind r5-fifty-words r8-no-e w2-word-count w5-lines-words"
MECHS="baseline ce mh kb ad sv"

for mech in $MECHS; do
  for t in $TASKS; do
    out="results/part1/$mech/$t/rep1"
    if [ -f "$out/meta.json" ]; then echo "SKIP $mech $t"; continue; fi
    echo "RUN $mech $t $(date +%H:%M:%S)"
    python3 mech-v6.py --mech "$mech" --task "$t" --rep 1 --outdir "$out"
  done
done
echo "PART1 DONE $(date)"
