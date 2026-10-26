#!/usr/bin/env bash
# swarm-call.sh — parallel FreeLLMAPI swarm calls (multi-provider: Groq, Google, OpenRouter)
#
# Usage:
#   export FREELLMAPI_API_KEY   # set in environment only, never in a file
#   ./swarm-call.sh --check             # preflight: server up? key present? (key never printed)
#   ./swarm-call.sh --dry-run "prompt"  # show what would be called, no key/network needed
#   ./swarm-call.sh "prompt" [outdir]
#
# Verified models (live PONG-tested 2026-10-13/14, all $0):
#   Groq:      openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b
#   Google:    gemini-3-flash-preview, gemma-4-31b-it, gemini-3.5-flash-lite,
#              gemma-4-26b-a4b-it, gemini-3.1-flash-lite,
#              gemini-3.8-flash (added 2026-10-14, in catalog; Google 503/high-demand on first test)
#   OpenRouter: cohere/north-mini-code:free, nvidia/nemotron-3-super-120b-a12b:free,
#              liquid/lfm-2.5-2.6b:free, dots-studio/dots-3-note-preview:free,
#              nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,
#              nvidia/nemotron-3.5-lightning:free
# Tested 2026-10-14, NOT routable via FreeLLMAPI (no upstream provider):
#   llama-3.1-8b, nemotron-3-ultra-550b — available via CLI connectors
#   (cli-llm.sh -> Pollinations.ai, no key). Use SWARM_MODE=cli.
#   Both PONG-verified 2026-10-14 via CLI.
# Removed: allam-2-7b (fabricated ticker/price/arithmetic — banned from stock
# research 2026-10-13); gemini-2.5-flash / 2.5-flash-lite (Google retired them,
# 404); gemini-3.5/3.6-flash (invalid IDs / upstream errors at test time).
# Skipped by design: Groq guard models, gemini-robotics-er-2-preview,
# nvidia/nemotron-3.5-content-safety (classifiers, not chat).
#
# Rules:
# - The unified API key comes ONLY from the environment. Never put a key in
#   this file, in an argument, or in any output file.
# - Calls go to the local FreeLLMAPI server (default http://localhost:3001),
#   which routes to Groq. The Halo /grok/ask bridge is NEVER used.
# - Both models run in parallel. Each call carries an Idempotency-Key so a
#   retry after a timeout replays the stored answer at zero provider cost
#   instead of burning a second free-tier slot.
# - Retries apply to 429 / 5xx / network failures only, with exponential
#   backoff, honoring the server's Retry-After header when present.
# - Exact-repeat cache (SWARM_CACHE=1, default ON since 2026-10-14 per
#   efficiency studies: exact-match hits avoid full rate-limit slots.
#   SWARM_CACHE=0 disables). Cache key is a hash of model+params+prompt only — never the
#   API key. Cache lives in SWARM_CACHE_DIR (default ~/.cache/swarm-call).
#
# Env overrides:
#   FREELLMAPI_BASE_URL   default http://localhost:3001
#   SWARM_MODELS          explicit model list (overrides SWARM_MODE)
#   SWARM_MODE            cheap (20b only) | full (both Groq, default) | deep (120b only)
#                         | smart (4 optimal models per DeepMind 2025) | cli (CLI connectors)
#                         | wide (all 15 verified) | groq (all 4 Groq) | google (all 5 Google)
#                         | openrouter (all 6 OpenRouter :free) | reasoning (large reasoners)
#   SWARM_TIMEOUT         per-call seconds, default 120
#   SWARM_MAX_RETRIES    default 3 (1 initial + 2 retries)
#   SWARM_FALLBACK        model used for one rescue attempt when a model fails
#                         all retries (default openai/gpt-oss-20b; empty
#                         disables). Rescue output fills the failed model's
#                         slot and is tagged FB in timings.tsv. Rescue answers
#                         are cached under the FALLBACK model's key only —
#                         never under the failed model's key.
#   SWARM_MAX_TOKENS      explicit token cap (overrides SWARM_PRESET)
#   SWARM_PRESET          short (512) | default (2048) | long (4096)
#                         | stockpick (4096, for stock-pick runs)
#   SWARM_TEMPERATURE     default 0.7
#   SWARM_SYSTEM          optional system prompt
#   SWARM_CACHE           1 = exact-repeat cache (default 1 = ON; 0 disables)
#   SWARM_CACHE_DIR       default ~/.cache/swarm-call
#   SWARM_HEALTH_FILE     default <script-dir>/swarm-health.json — per-model
#                         429/5xx history, updated after every run
#   SWARM_SKIP_UNHEALTHY  1 = skip models with >=2 consecutive failures or a
#                         429/5xx/cooldown in effect (default 0)
#   SWARM_REDELEGATE      1 (default) = an unhealthy model's slot is reassigned
#                         to the healthiest substitute in the roster (fewest
#                         failures, then lowest 1h call load) instead of being
#                         dropped. 0 = old skip behavior. Only applies with
#                         SWARM_SKIP_UNHEALTHY=1.
#   SWARM_SUBSTITUTE_POOL space-separated models eligible as redelegation
#                         substitutes; defaults to the run's MODELS roster.
#                         Lets single-model callers (e.g. per-role engine runs)
#                         redelegate into a wider pool.
#   SWARM_EXCLUDE         space-separated glob patterns; matching models never
#                         launch (e.g. "allam-2-7b")
#   SWARM_STAGGER_SECS    delay between rate-limited model launches
#                         (OpenRouter :free, Google; default 0)
# timings.tsv columns: model, http_code, attempts, elapsed_ms
# Token floors unless SWARM_MAX_TOKENS explicit: gpt-oss 2048 (low reasoning
# effort), nemotron/reasoning family 4096 (verbose reasoners; liquid truncated
# at 2048 in round 1).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_FILE="${SWARM_HEALTH_FILE:-$SCRIPT_DIR/swarm-health.json}"

BASE_URL="${FREELLMAPI_BASE_URL:-http://localhost:3001}"
# Routing mode: cheap (20b only), full (both Groq, default), deep (120b only),
# wide (all live-verified models), groq (all Groq), google (verified Google only),
# openrouter (verified OpenRouter :free only), reasoning (large reasoners).
# Applies only when SWARM_MODELS is not explicitly set.
if [ -n "${SWARM_MODELS:-}" ]; then
  MODELS="$SWARM_MODELS"
else
  case "${SWARM_MODE:-full}" in
    cheap) MODELS="openai/gpt-oss-20b" ;;
    deep)  MODELS="openai/gpt-oss-120b" ;;
    wide)  MODELS="openai/gpt-oss-120b openai/gpt-oss-20b qwen/qwen3.8-27b gemini-3-flash-preview gemini-3.5-flash-lite gemini-3.8-flash cohere/north-mini-code:free nvidia/nemotron-3-super-120b-a12b:free liquid/lfm-2.5-2.6b:free dots-studio/dots-3-note-preview:free nvidia/nemotron-3.5-lightning:free" ;;
    groq) MODELS="openai/gpt-oss-120b openai/gpt-oss-20b qwen/qwen3.8-27b" ;;
    google) MODELS="gemini-3-flash-preview gemini-3.5-flash-lite gemini-3.8-flash" ;;
    openrouter) MODELS="cohere/north-mini-code:free nvidia/nemotron-3-super-120b-a12b:free liquid/lfm-2.5-2.6b:free dots-studio/dots-3-note-preview:free nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free nvidia/nemotron-3.5-lightning:free" ;;
    reasoning) MODELS="openai/gpt-oss-120b nvidia/nemotron-3-super-120b-a12b:free nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free" ;;
    cli) MODELS="cli:llama cli:nemotron" ;;
    # Smart mode (2026-10-14, re-tuned 2026-10-16 from benchmark data):
    # 4 models optimal per Google DeepMind 2025 (saturation at 3-4 agents).
    # Roster = measured 10/10 or 9/9-with-zero-capability-failures, three
    # providers: fastest (20b, flash-preview) + best reasoning (120b,
    # nemotron-3.5-lightning) + diversity (Groq/OpenRouter/Google).
    # gemini-3.5-flash-lite removed 2026-10-16: silent arithmetic failure
    # (capability, not transport) + 10h rate-limit in benchmark wave 3.
    smart) MODELS="openai/gpt-oss-20b openai/gpt-oss-120b nvidia/nemotron-3.5-lightning:free gemini-3-flash-preview" ;;
    # Optimal chunks (2026-10-14): 3-4 models each, task-specialized per research
    # Fast chunk: triage, grading, classification (all <1100ms pong)
    fast) MODELS="openai/gpt-oss-20b qwen/qwen3.8-27b liquid/lfm-2.5-2.6b:free" ;;
    # Deep chunk: complex reasoning, analysis (verbose, thorough)
    deep-think) MODELS="openai/gpt-oss-120b nvidia/nemotron-3-super-120b-a12b:free liquid/lfm-2.5-2.6b:free" ;;
    # Balanced chunk: general purpose, speed + quality
    balanced) MODELS="openai/gpt-oss-20b openai/gpt-oss-120b gemini-3.5-flash-lite" ;;
    # Code chunk: code tasks only
    code) MODELS="cohere/north-mini-code:free openai/gpt-oss-120b" ;;
    *)     MODELS="openai/gpt-oss-120b openai/gpt-oss-20b" ;;
  esac
fi
# Exclusions: space-separated glob patterns; matching models never launch.
# (e.g. SWARM_EXCLUDE="allam-2-7b" keeps a banned model out of groq/wide modes.)
if [ -n "${SWARM_EXCLUDE:-}" ]; then
  filtered=""
  for m in $MODELS; do
    skip=0
    for pat in $SWARM_EXCLUDE; do
      case "$m" in $pat) skip=1; break ;; esac
    done
    [ "$skip" = "0" ] && filtered="$filtered $m"
  done
  MODELS="${filtered# }"
fi
TIMEOUT="${SWARM_TIMEOUT:-120}"
MAX_RETRIES="${SWARM_MAX_RETRIES:-3}"
MAX_TOKENS="${SWARM_MAX_TOKENS:-2048}"
TOKENS_EXPLICIT=0
[ -n "${SWARM_MAX_TOKENS:-}" ] && TOKENS_EXPLICIT=1
# Token preset applies only when SWARM_MAX_TOKENS is not explicitly set.
if [ "$TOKENS_EXPLICIT" = "0" ]; then
  case "${SWARM_PRESET:-default}" in
    short) MAX_TOKENS=512 ;;
    long)  MAX_TOKENS=4096 ;;
    stockpick) MAX_TOKENS=4096 ;;
  esac
fi
TEMPERATURE="${SWARM_TEMPERATURE:-0.7}"
SYSTEM="${SWARM_SYSTEM:-}"

# --- Model health tracking (swarm-health.json) ---
# Updated after every run: last HTTP code, last-seen epoch, consecutive
# failures, last 429/5xx epoch, cooldown_until (epoch; no calls before then),
# and calls[] (epochs of calls in the last hour, for load-aware redelegation).
# Read by --health, SWARM_SKIP_UNHEALTHY, is_healthy, and resolve_model.
record_health() {
  local model="$1" http="$2" retry_after="${3:-0}"
  local now cutoff cd_secs
  now="$(date +%s)"; cutoff=$((now - 3600))
  # Cooldown: honor the server's Retry-After (capped at 1h so one bad header
  # can't park a model all day); default 300s on 429 without a header, 300s
  # on 5xx/connection failure. Success clears the cooldown (recovery).
  cd_secs=0
  case "$http" in
    429)
      cd_secs="$retry_after"
      { [ "$cd_secs" -gt 0 ] 2>/dev/null; } || cd_secs=300
      [ "$cd_secs" -gt 3600 ] && cd_secs=3600 ;;
    500|502|503|504|000) cd_secs=300 ;;
  esac
  # Serialize updates: parallel background models (and overlapping runs) would
  # otherwise race the jq read-modify-write and lose/corrupt health entries.
  exec 200>"${HEALTH_FILE}.lock"
  flock -x 200
  local tmp
  tmp="$(mktemp)"
  if [ -f "$HEALTH_FILE" ]; then
    jq --arg m "$model" --argjson h "$http" --argjson n "$now" \
      --argjson cd "$cd_secs" --argjson cut "$cutoff" \
      '($m) as $k | (.[$k] // {}) as $e |
       (if $h == 200 then 0 else (($e.consecutive_failures // 0) + 1) end) as $nf |
       (if $h == 200 then 0
        elif $cd > 0 then $n + $cd
        else ($e.cooldown_until // 0) end) as $ncd |
       (if ([429,500,502,503,504,0] | index($h)) then $n else ($e.last_429_5xx // 0) end) as $nerr |
       (((($e.calls // []) + [$n]) | map(select(. > $cut))) as $nc |
       .[$k] = {last_http: $h, last_seen: $n, consecutive_failures: $nf,
                last_429_5xx: $nerr, cooldown_until: $ncd, calls: $nc})' \
      "$HEALTH_FILE" > "$tmp" 2>/dev/null && mv "$tmp" "$HEALTH_FILE" || rm -f "$tmp"
  else
    jq -n --arg m "$model" --argjson h "$http" --argjson n "$now" \
      --argjson cd "$cd_secs" --argjson cut "$cutoff" \
      '{($m): {last_http: $h, last_seen: $n,
               consecutive_failures: (if $h == 200 then 0 else 1 end),
               last_429_5xx: (if ([429,500,502,503,504,0] | index($h)) then $n else 0 end),
               cooldown_until: (if $cd > 0 then $n + $cd else 0 end),
               calls: [$n]}}' \
      > "$HEALTH_FILE" 2>/dev/null || true
    rm -f "$tmp"
  fi
  flock -u 200
  exec 200>&-
}

is_healthy() {
  local model="$1"
  [ -f "$HEALTH_FILE" ] || return 0
  local now fails last_err cd rest vals
  now="$(date +%s)"
  # Single jq call for all fields (was two).
  vals="$(jq -r --arg m "$model" '[.[$m].consecutive_failures // 0, .[$m].last_429_5xx // 0, .[$m].cooldown_until // 0] | @tsv' "$HEALTH_FILE" 2>/dev/null || printf '0\t0\t0')"
  fails="${vals%%$'\t'*}"; rest="${vals#*$'\t'}"
  last_err="${rest%%$'\t'*}"; cd="${rest#*$'\t'}"
  [ "$fails" -ge 2 ] && return 1
  [ "$last_err" != "0" ] && [ "$last_err" != "null" ] && [ $((now - last_err)) -lt 3600 ] && return 1
  { [ "$cd" -gt "$now" ] 2>/dev/null; } && return 1
  return 0
}

# resolve_model <preferred> <roster...>
# Weight-redelegation core: print the model to actually call. Preferred model
# when healthy; otherwise the healthiest substitute in the roster — fewest
# consecutive failures, then lowest 1h call load (spreads redelegated weight
# instead of piling it all on one fallback). Prints nothing if no healthy
# substitute exists.
resolve_model() {
  local pref="$1"; shift
  if is_healthy "$pref"; then echo "$pref"; return 0; fi
  local best="" best_f=999999 best_load=999999999 c f load vals
  for c in "$@"; do
    [ "$c" = "$pref" ] && continue
    is_healthy "$c" || continue
    vals="$(jq -r --arg m "$c" '[.[$m].consecutive_failures // 0, ((.[$m].calls // []) | length)] | @tsv' "$HEALTH_FILE" 2>/dev/null || printf '0\t0')"
    f="${vals%%$'\t'*}"; load="${vals#*$'\t'}"
    { [ "$f" -lt "$best_f" ] || { [ "$f" -eq "$best_f" ] && [ "$load" -lt "$best_load" ]; }; } 2>/dev/null \
      && { best="$c"; best_f="$f"; best_load="$load"; }
  done
  [ -n "$best" ] && echo "$best"
  return 0  # never fail: callers test for empty output; a nonzero return
            # would trip errexit inside $(...) command substitutions.
}

# --health: print the per-model health table, no network needed.
if [ "${1:-}" = "--health" ]; then
  if [ ! -f "$HEALTH_FILE" ]; then echo "no health data yet (no runs recorded)"; exit 0; fi
  printf '%-50s %-8s %-8s %-10s %-10s %-6s %s\n' "MODEL" "LAST_HTTP" "FAILS" "LAST_ERR_AGO" "COOLDOWN" "LOAD_1H" "LAST_SEEN"
  jq -r 'to_entries[] | [.key, (.value.last_http // "n/a"), (.value.consecutive_failures // 0), (.value.last_429_5xx // 0), (.value.cooldown_until // 0), ((.value.calls // []) | length), (.value.last_seen // 0)] | @tsv' "$HEALTH_FILE" | while IFS=$'\t' read -r m h f e cd load s; do
    now="$(date +%s)"
    ago="never"; [ "$e" != "0" ] && [ "$e" != "null" ] && ago="$(( (now - e) / 60 ))m ago"
    cdn="-"; [ "$cd" -gt "$now" ] 2>/dev/null && cdn="$(( (cd - now) / 60 ))m left"
    seen="$(date -d "@$s" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "?")"
    printf '%-50s %-8s %-8s %-10s %-10s %-6s %s\n' "$m" "$h" "$f" "$ago" "$cdn" "$load" "$seen"
  done
  exit 0
fi

# Preflight: server reachable? key present (presence only, never printed)?
# Uses an unauthenticated probe that the server answers 401 — zero provider cost.
if [ "${1:-}" = "--check" ]; then
  ok=1
  probe="$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 -X POST "$BASE_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"openai/gpt-oss-20b","messages":[{"role":"user","content":"ping"}],"max_tokens":1}' 2>/dev/null || true)"
  # curl -w prints 000 on connection failure; only fall back when it printed nothing.
  [ -z "$probe" ] && probe="000"
  case "$probe" in
    401) echo "server: UP ($BASE_URL, auth enforced)" ;;
    000) echo "server: DOWN ($BASE_URL unreachable)"; ok=0 ;;
    *)   echo "server: UP ($BASE_URL, unexpected http=$probe)" ;;
  esac
  if [ -n "${FREELLMAPI_API_KEY:-}" ]; then
    echo "api key: PRESENT in environment"
  else
    echo "api key: ABSENT from environment — export FREELLMAPI_API_KEY before running"
    ok=0
  fi
  if [ "$ok" = "1" ]; then echo "READY"; else echo "BLOCKED"; fi
  exit $((1 - ok))
fi

# Dry-run: show what would be called without needing a key or network.
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

if [ "${1:-}" = "-f" ]; then
  [ -n "${2:-}" ] || { echo "usage: swarm-call.sh -f prompt.txt [outdir]" >&2; exit 2; }
  PROMPT="$(cat "$2")"
  OUTDIR="${3:-./swarm-out-$(date +%Y%m%d-%H%M%S)}"
else
  [ -n "${1:-}" ] || { echo "usage: swarm-call.sh \"prompt\" [outdir]" >&2; exit 2; }
  PROMPT="$1"
  OUTDIR="${2:-./swarm-out-$(date +%Y%m%d-%H%M%S)}"
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "models: $MODELS"
  echo "max_tokens: $MAX_TOKENS (gpt-oss floor 2048, nemotron/reasoning floor 4096 unless explicit)  temperature: $TEMPERATURE  timeout: ${TIMEOUT}s"
  echo "cache: ${SWARM_CACHE:-1} (dir: ${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call})"
  for m in $MODELS; do
    local_toks="$MAX_TOKENS"
    case "$m" in
      *gpt-oss-120b*|*gpt-oss-20b*)
        if [ "$TOKENS_EXPLICIT" = "0" ] && [ "$local_toks" -lt 2048 ]; then local_toks=2048; fi ;;
      *nemotron*|*reasoning*)
        if [ "$TOKENS_EXPLICIT" = "0" ] && [ "$local_toks" -lt 4096 ]; then local_toks=4096; fi ;;
    esac
    effort=""
    case "$m" in
      *gpt-oss-120b*|*gpt-oss-20b*) effort="low" ;;
    esac
    if [ "${SWARM_SKIP_UNHEALTHY:-0}" = "1" ] && ! is_healthy "$m"; then
      # shellcheck disable=SC2086
      sub="$(resolve_model "$m" ${SWARM_SUBSTITUTE_POOL:-$MODELS})"
      if [ "${SWARM_REDELEGATE:-1}" = "1" ] && [ -n "$sub" ]; then
        echo "[$m] would REDELEGATE -> $sub"
      else
        echo "[$m] would SKIP (unhealthy)"
      fi
      continue
    fi
    if [ "${SWARM_CACHE:-1}" = "1" ]; then
      hk="$(printf '%s|%s|%s|%s|%s|%s' "$m" "$local_toks" "$TEMPERATURE" "$SYSTEM" "$PROMPT" "$effort" | sha256sum | awk '{print $1}')"
      if [ -f "${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call}/$hk.txt" ]; then
        echo "[$m] would return CACHE HIT (tokens=$local_toks)"
      else
        echo "[$m] would call network (cache miss, tokens=$local_toks)"
      fi
    else
      echo "[$m] would call network (tokens=$local_toks)"
    fi
  done
  exit 0
fi

mkdir -p "$OUTDIR"
printf '%s\n' "$PROMPT" > "$OUTDIR/prompt.txt"
: > "$OUTDIR/timings.tsv"

KEY="${FREELLMAPI_API_KEY:-}"
# CLI-only mode doesn't need the FreeLLMAPI key (uses cli-llm.sh directly).
if [ -z "$KEY" ] && [ "${SWARM_MODE:-}" != "cli" ] && [[ "${SWARM_MODELS:-}" != cli:* ]]; then
  echo "error: FREELLMAPI_API_KEY is not set in the environment" >&2
  exit 2
fi

call_model() {
  local model="$1"
  # Slot: the requested roster entry (for filenames). When redelegation maps
  # two slots onto one model, files stay distinct; health/timings still record
  # the actual model that ran.
  local slot="${2:-$1}"
  local safe="${slot//\//_}"
  safe="${safe//:/_}"
  local idem
  idem="$(cat /proc/sys/kernel/random/uuid)"
  local attempt=0 delay=2
  local start end http_code="000" retry_after=""

  # CLI connector models (cli:llama, cli:nemotron): route via cli-llm.sh
  # instead of the FreeLLMAPI server. These use free endpoints directly.
  case "$model" in
    cli:*)
      local cli_alias="${model#cli:}"
      start="$(date +%s%N)"
      if "$SCRIPT_DIR/cli-llm.sh" "$cli_alias" "$PROMPT" "$OUTDIR" 2>/dev/null; then
        end="$(date +%s%N)"
        local elapsed_ms=$(( (end - start) / 1000000 ))
        printf '%s\t%s\t%s\t%s\n' "$model" "CLI" "1" "$elapsed_ms" >> "$OUTDIR/timings.tsv"
        echo "[$model] CLI OK (${elapsed_ms}ms)"
        return 0
      else
        end="$(date +%s%N)"
        local elapsed_ms=$(( (end - start) / 1000000 ))
        printf '%s\t%s\t%s\t%s\n' "$model" "CLI_FAIL" "1" "$elapsed_ms" >> "$OUTDIR/timings.tsv"
        echo "[$model] CLI FAILED" >&2
        return 1
      fi
      ;;
  esac

  # Token floor: reasoning models need headroom unless SWARM_MAX_TOKENS explicit.
  # gpt-oss runs at reasoning_effort=low (few reasoning tokens) so 2048
  # suffices; nemotron/reasoning models are verbose — keep 4096.
  local tokens="$MAX_TOKENS"
  case "$model" in
    *gpt-oss-120b*|*gpt-oss-20b*)
      if [ "$TOKENS_EXPLICIT" = "0" ] && [ "$tokens" -lt 2048 ]; then tokens=2048; fi ;;
    *nemotron*|*reasoning*)
      if [ "$TOKENS_EXPLICIT" = "0" ] && [ "$tokens" -lt 4096 ]; then tokens=4096; fi ;;
  esac

  # Reasoning effort: Groq gpt-oss models accept reasoning_effort (low/medium/
  # high, default medium). Low cuts reasoning tokens — which count against
  # max_tokens and TPM — and latency (2026-10-14). Verified for the two
  # gpt-oss models only; other models omit the field.
  local effort=""
  case "$model" in
    *gpt-oss-120b*|*gpt-oss-20b*) effort="low" ;;
  esac

  start="$(date +%s%N)"
  # Exact-repeat cache FIRST: hit returns the stored answer with zero jq
  # payload construction and zero network. (Payload is built lazily below,
  # only on cache miss.)
  # Two-tier cache: tier 1 exact match, tier 2 normalized (whitespace/
  # punctuation stripped, lowercased). Catches trivially-different prompts.
  local cache_file=""
  if [ "${SWARM_CACHE:-1}" = "1" ]; then
    local cache_key norm_key
    cache_key="$(printf '%s|%s|%s|%s|%s|%s' "$model" "$tokens" "$TEMPERATURE" "$SYSTEM" "$PROMPT" "$effort" | sha256sum | awk '{print $1}')"
    cache_file="${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call}/$cache_key.txt"
    if [ -f "$cache_file" ]; then
      cp "$cache_file" "$OUTDIR/$safe.txt"
      printf '%s\t%s\t%s\t%s\n' "$model" "CACHE" "0" "0" >> "$OUTDIR/timings.tsv"
      echo "[$model] CACHE HIT (exact, 0s)"
      return 0
    fi
    # Tier 2: normalized match
    norm_key="$(printf '%s|%s|%s|%s|%s|%s' "$model" "$tokens" "$TEMPERATURE" "$SYSTEM" "$PROMPT" "$effort" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:][:punct:]' | sha256sum | awk '{print $1}')"
    local norm_file="${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call}/norm-$norm_key.txt"
    if [ -f "$norm_file" ]; then
      cp "$norm_file" "$OUTDIR/$safe.txt"
      printf '%s\t%s\t%s\t%s\n' "$model" "CACHE_NORM" "0" "0" >> "$OUTDIR/timings.tsv"
      echo "[$model] CACHE HIT (normalized, 0s)"
      return 0
    fi
  fi

  # Build the request body once with jq (safe escaping of the prompt).
  local payload
  if [ -n "$SYSTEM" ]; then
    payload="$(jq -n --arg m "$model" --arg s "$SYSTEM" --arg p "$PROMPT" \
      --argjson t "$tokens" --argjson temp "$TEMPERATURE" \
      '{model:$m, messages:[{role:"system",content:$s},{role:"user",content:$p}], max_tokens:$t, temperature:$temp, stream:false}')"
  else
    payload="$(jq -n --arg m "$model" --arg p "$PROMPT" \
      --argjson t "$tokens" --argjson temp "$TEMPERATURE" \
      '{model:$m, messages:[{role:"user",content:$p}], max_tokens:$t, temperature:$temp, stream:false}')"
  fi

  # Attach reasoning_effort only for models that support it (gpt-oss).
  if [ -n "$effort" ]; then
    payload="$(printf '%s' "$payload" | jq --arg e "$effort" '. + {reasoning_effort:$e}')"
  fi

  while [ "$attempt" -lt "$MAX_RETRIES" ]; do
    attempt=$((attempt + 1))
    # Capture headers + body separately; -w prints the status code.
    http_code="$(curl -sS -o "$OUTDIR/$safe.json" -D "$OUTDIR/$safe.headers" \
      -w "%{http_code}" --max-time "$TIMEOUT" \
      -X POST "$BASE_URL/v1/chat/completions" \
      -H "Authorization: Bearer $KEY" \
      -H "Content-Type: application/json" \
      -H "Idempotency-Key: $idem" \
      -d "$payload" 2>/dev/null || true)"
    # Normalize: empty or malformed output means the request never completed.
    case "$http_code" in
      ???) : ;;
      *) http_code="000" ;;
    esac
    case "$http_code" in
      200)
        break ;;
      409)
        echo "[$model] 409: idempotency key reused with different content — aborting" >&2
        break ;;
      429|500|502|503|504|000)
        retry_after="$(grep -i '^retry-after:' "$OUTDIR/$safe.headers" 2>/dev/null | tr -d '\r' | awk '{print $2}' || true)"
        if [ "$attempt" -lt "$MAX_RETRIES" ]; then
          # Cap honored Retry-After: a 22h server-supplied wait inside a retry
          # loop freezes unattended runs (seen 2026-10-16: Retry-After 81056).
          # Beyond the cap, treat as ordinary backoff failure so fallback and
          # health-skip can route around the dead route.
          if [ -n "$retry_after" ] && [ "$retry_after" -gt 0 ] 2>/dev/null; then
            [ "$retry_after" -gt 120 ] && retry_after=120
            sleep "$retry_after"
          else
            sleep "$delay"
            delay=$((delay * 2))
          fi
        fi
        ;;
      *)
        break ;;
    esac
  done
  # Fallback rescue: the model failed all retries. If SWARM_FALLBACK names a
  # different model, make one rescue attempt with it so the slot still yields
  # output (benchmark wave 1-3 lost most outputs to transport, not capability).
  # Rescue answers are cached under the FALLBACK model's own key only.
  # orig_code preserves the model's real result for health tracking.
  orig_code="$http_code"
  if [ "$http_code" != "200" ] && [ -n "${SWARM_FALLBACK-openai/gpt-oss-20b}" ] \
     && [ "$model" != "${SWARM_FALLBACK-openai/gpt-oss-20b}" ]; then
    fb_model="${SWARM_FALLBACK-openai/gpt-oss-20b}"
    fb_payload="$(printf '%s' "$payload" | jq --arg m "$fb_model" '.model = $m')"
    case "$fb_model" in *gpt-oss*) : ;; *) fb_payload="$(printf '%s' "$fb_payload" | jq 'del(.reasoning_effort)')"; esac
    fb_code="$(curl -sS -o "$OUTDIR/$safe.json" -D "$OUTDIR/$safe.headers" \
      -w "%{http_code}" --max-time "$TIMEOUT" \
      -X POST "$BASE_URL/v1/chat/completions" \
      -H "Authorization: Bearer $KEY" \
      -H "Content-Type: application/json" \
      -H "Idempotency-Key: $idem-fb" \
      -d "$fb_payload" 2>/dev/null || true)"
    case "$fb_code" in ???) : ;; *) fb_code="000" ;; esac
    if [ "$fb_code" = "200" ]; then
      jq -r '.choices[0].message.content // empty' "$OUTDIR/$safe.json" > "$OUTDIR/$safe.txt" 2>/dev/null || true
      # Cache under the fallback model's key (never the failed model's).
      if [ "${SWARM_CACHE:-1}" = "1" ]; then
        fb_effort=""; case "$fb_model" in *gpt-oss-120b*|*gpt-oss-20b*) fb_effort="low" ;; esac
        fb_toks="$MAX_TOKENS"
        case "$fb_model" in
          *gpt-oss-120b*|*gpt-oss-20b*) [ "$TOKENS_EXPLICIT" = "0" ] && [ "$fb_toks" -lt 2048 ] && fb_toks=2048 ;;
          *nemotron*|*reasoning*) [ "$TOKENS_EXPLICIT" = "0" ] && [ "$fb_toks" -lt 4096 ] && fb_toks=4096 ;;
        esac
        fb_key="$(printf '%s|%s|%s|%s|%s|%s' "$fb_model" "$fb_toks" "$TEMPERATURE" "$SYSTEM" "$PROMPT" "$fb_effort" | sha256sum | awk '{print $1}')"
        mkdir -p "${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call}"
        cp "$OUTDIR/$safe.txt" "${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call}/$fb_key.txt"
      fi
      http_code="FB"
      fb_used=1
      echo "[$model] RESCUED by $fb_model"
    else
      http_code="FB_FAIL"
      echo "[$model] FAILED http=$http_code after $attempt attempt(s); fallback $fb_model also failed ($fb_code)" >&2
    fi
  fi
  end="$(date +%s%N)"
  elapsed_ms="$(( (end - start) / 1000000 ))"
  elapsed_s="$(awk "BEGIN{printf \"%.1f\", $elapsed_ms/1000}")"

  if [ "$http_code" = "200" ]; then
    jq -r '.choices[0].message.content // empty' "$OUTDIR/$safe.json" > "$OUTDIR/$safe.txt" 2>/dev/null || true
    if [ "${SWARM_CACHE:-1}" = "1" ] && [ -n "$cache_file" ]; then
      mkdir -p "$(dirname "$cache_file")"
      cp "$OUTDIR/$safe.txt" "$cache_file"
      # Also write normalized tier
      norm_key="$(printf '%s|%s|%s|%s|%s|%s' "$model" "$tokens" "$TEMPERATURE" "$SYSTEM" "$PROMPT" "$effort" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:][:punct:]' | sha256sum | awk '{print $1}')"
      cp "$OUTDIR/$safe.txt" "${SWARM_CACHE_DIR:-$HOME/.cache/swarm-call}/norm-$norm_key.txt"
    fi
    echo "[$model] OK in ${elapsed_s}s, $attempt attempt(s)"
  elif [ "$http_code" = "FB" ]; then
    echo "[$model] OK via fallback in ${elapsed_s}s"
  else
    echo "[$model] FAILED http=$http_code after $attempt attempt(s), ${elapsed_s}s"
  fi
  printf '%s\t%s\t%s\t%s\n' "$model" "$http_code" "$attempt" "$elapsed_ms" >> "$OUTDIR/timings.tsv"
  record_health "$model" "$orig_code" "$retry_after"
  { [ "$http_code" = "200" ] || [ "$http_code" = "FB" ]; }
}

fail=0
pids=""
# Stagger rate-limited launches: firing all OpenRouter :free or Google models
# at once is a known 429-loop trigger. SWARM_STAGGER_SECS=0 preserves old
# behavior.
STAGGER="${SWARM_STAGGER_SECS:-0}"
for m in $MODELS; do
  # Weight redelegation: an unhealthy model's slot is reassigned to the
  # healthiest substitute instead of being dropped. SWARM_REDELEGATE=0
  # restores the old skip behavior. Substitutes come from
  # SWARM_SUBSTITUTE_POOL when set, else the run's own roster.
  actual="$m"
  if [ "${SWARM_SKIP_UNHEALTHY:-0}" = "1" ] && ! is_healthy "$m"; then
    if [ "${SWARM_REDELEGATE:-1}" = "1" ]; then
      # shellcheck disable=SC2086
      sub="$(resolve_model "$m" ${SWARM_SUBSTITUTE_POOL:-$MODELS})"
      if [ -n "$sub" ]; then
        echo "[$m] REDELEGATED -> $sub"
        actual="$sub"
      else
        echo "[$m] SKIPPED (unhealthy, no healthy substitute)"
        continue
      fi
    else
      echo "[$m] SKIPPED (unhealthy — see --health)"
      continue
    fi
  fi
  case "$actual" in *:free*|gemini-*|gemma-*) [ "$STAGGER" -gt 0 ] 2>/dev/null && sleep "$STAGGER" ;; esac
  call_model "$actual" "$m" & pids="$pids $!"
done
for pid in $pids; do
  wait "$pid" || fail=1
done

echo "output: $OUTDIR"
exit "$fail"
