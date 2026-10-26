#!/usr/bin/env bash
# run-styles.sh — Part 2: 4 feedback styles x 6 fixable tasks. Idempotent.
set -u
V6="$(cd "$(dirname "$0")" && pwd)"
cd "$V6" || exit 1
export MECH_KEPT_JSON=tasks-v5-kept2.json
. "$HOME/workspace/freellmapi/vault/vault.sh" || exit 1
swarm_vault_load || exit 1
export FREELLMAPI_API_KEY no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"

TASKS="c1-expr-eval-3 c10-sexpr p3-unicode-json p9-sexpr-let q3-zebra-5 w5-lines-words"
STYLES="style_terse style_ce style_socratic style_diverge"

for style in $STYLES; do
  for t in $TASKS; do
    out="results/part2/$style/$t/rep1"
    if [ -f "$out/meta.json" ]; then echo "SKIP $style $t"; continue; fi
    echo "RUN $style $t $(date +%H:%M:%S)"
    python3 mech-v6.py --mech "$style" --task "$t" --rep 1 --outdir "$out"
  done
done
echo "STYLES DONE $(date)"
