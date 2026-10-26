#!/usr/bin/env bash
# cli-llm.sh — CLI connector for models not routable via FreeLLMAPI.
# Calls free endpoints directly via curl. $0 spend, no keys.
#
# Usage:
#   ./cli-llm.sh llama "prompt" [outdir]     # llama-3.1-8b via Pollinations
#   ./cli-llm.sh nemotron "prompt" [outdir]  # nemotron-3-ultra via Pollinations
#
# Output: writes response to <outdir>/<model>.txt (swarm-call.sh compatible)

set -euo pipefail

MODEL_ALIAS="${1:?usage: cli-llm.sh <llama|nemotron> \"prompt\" [outdir]}"
PROMPT="${2:?usage: cli-llm.sh <llama|nemotron> \"prompt\" [outdir]}"
OUTDIR="${3:-/tmp/cli-llm-out}"
mkdir -p "$OUTDIR"

case "$MODEL_ALIAS" in
  llama)
    MODEL_ID="llama-3.1-8b"
    # Pollinations OpenAI-compatible endpoint, no key needed
    ENDPOINT="https://text.pollinations.ai/openai"
    ;;
  nemotron)
    MODEL_ID="nemotron-3-ultra-550b"
    ENDPOINT="https://text.pollinations.ai/openai"
    ;;
  *)
    echo "unknown model alias: $MODEL_ALIAS (use: llama, nemotron)" >&2
    exit 1
    ;;
esac

SAFE="$(echo "$MODEL_ID" | tr '/:' '_')"
OUTFILE="$OUTDIR/$SAFE.txt"

# Build request (no system role on anonymous tier — prepend to user message)
PAYLOAD="$(python3 -c "
import json,sys
print(json.dumps({
    'model': 'openai',
    'messages': [{'role': 'user', 'content': sys.argv[1]}],
    'max_tokens': 2048,
    'temperature': 0.7
}))
" "$PROMPT")"

echo "[$MODEL_ID] calling $ENDPOINT..."
HTTP_CODE="$(curl -sS -o "$OUTFILE.json" -w "%{http_code}" --max-time 120 \
  -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" 2>/dev/null || echo "000")"

if [ "$HTTP_CODE" = "200" ]; then
  python3 -c "
import json
d=json.load(open('$OUTFILE.json'))
text=(d.get('choices') or [{}])[0].get('message',{}).get('content','')
open('$OUTFILE','w').write(text)
print(f'[$MODEL_ID] OK, {len(text)} chars -> $OUTFILE')
"
else
  echo "[$MODEL_ID] FAILED http=$HTTP_CODE" >&2
  exit 1
fi
