#!/usr/bin/env bash
# cynic-audit.sh — run any proposal through the permanent Cynic.
# Usage: ./cynic-audit.sh <proposal-file> [outdir]
# Model: nvidia/nemotron-3.5-lightning:free — chosen 2026-10-16 because the
# benchmark showed it had the strongest calibration behavior of any model
# tested: it corrected the fabricated premise directly ("there was no such
# study") where gpt-oss-120b evaded and lfm-2.5-2.6b confabulated a redirect.
# Least sycophantic model on record. Different provider (OpenRouter) from the
# Groq generators, so its verdicts are independent.
set -euo pipefail
cd "$(dirname "$0")"

[ $# -ge 1 ] || { echo "usage: $0 <proposal-file> [outdir]" >&2; exit 1; }
PROPOSAL="$1"
OUTDIR="${2:-/tmp/cynic-audit-$(date +%s)}"
mkdir -p "$OUTDIR"

PROMPT_FILE="$OUTDIR/cynic-prompt.txt"
cat cynic-prompt.md > "$PROMPT_FILE"
printf '\n\n---\n\nPROPOSAL UNDER AUDIT:\n\n' >> "$PROMPT_FILE"
cat "$PROPOSAL" >> "$PROMPT_FILE"

export no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"
if [ -z "${FREELLMAPI_API_KEY:-}" ]; then
  export FREELLMAPI_API_KEY=$(sqlite3 server/data/freeapi.db "SELECT value FROM settings WHERE key='unified_api_key';")
fi

SWARM_MODELS="nvidia/nemotron-3.5-lightning:free" \
SWARM_SKIP_UNHEALTHY=1 \
  ./swarm-call.sh -f "$PROMPT_FILE" "$OUTDIR" 2>&1 | tail -3

echo "--- verdict:"
cat "$OUTDIR"/nvidia_nemotron-3.5-lightning_free.txt 2>/dev/null | tail -6
