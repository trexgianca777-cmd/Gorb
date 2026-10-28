#!/bin/bash
# Build swarmzero-bundle.md: the whole project as one file, for upload
# into a fresh Muse session from a phone. Regenerate after any change:
#   ./make-bundle.sh && git add swarmzero-bundle.md && git commit -m "Refresh bundle" && git push
set -e
cd "$(dirname "$0")"

FILES="
BOOTSTRAP.md
README.md
BUDGET.md
LIMITATIONS.md
RESULTS.md
SWARM.md
TOKEN-PROTOCOL.md
researcher-contract.md
role-prompts.md
swarm-roles.md
swarm-roles-full.md
live_demo.py
proxy_server.py
prompt_filter.py
meta_client.py
routing_ledger.py
routing_ledger.csv
swarm-call.sh
contract_check.py
live-runs/run-escalation-test-20261025.json
live-runs/run-escalation-retest-20261026.json
benchmark-v5/REPORT.md
benchmark-v5/score-v5.py
benchmark-v5/verify-v5.py
benchmark-v5/mech-v5.py
benchmark-v5/xrevise.py
benchmark-v5/run-v5.sh
benchmark-v5/tasks-v5-kept.json
benchmark-v4/REPORT.md
benchmark-v4/ROUTER.md
benchmark/results/REPORT.md
"

OUT="swarmzero-bundle.md"
{
  echo "# SwarmZero — single-file bundle"
  echo
  echo "Upload this one file into Muse and it carries the full project:"
  echo "docs, demo loop, cost-guard proxy, swarm caller, and benchmark"
  echo "reports. Source repo: https://github.com/trexgianca777-cmd/Gorb"
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ). Regenerate with ./make-bundle.sh."
  echo
  echo "## Contents"
  for f in $FILES; do echo "- $f"; done
  echo
  for f in $FILES; do
    if [ -f "$f" ]; then
      echo "================================================================"
      echo "FILE: $f"
      echo "================================================================"
      cat "$f"
      echo
    else
      echo "================================================================"
      echo "FILE: $f (MISSING at bundle time)"
      echo "================================================================"
      echo
    fi
  done
} > "$OUT"
echo "Wrote $OUT ($(wc -c < "$OUT") bytes, $(grep -c '^FILE: ' "$OUT") files)"
