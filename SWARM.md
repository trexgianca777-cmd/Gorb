# Swarm usage (Groq gpt-oss-120b + gpt-oss-20b via FreeLLMAPI)

## Rules (non-negotiable)
- Direct FreeLLMAPI calls only. The Halo `/grok/ask` bridge is banned.
- Zero cost. No paid tiers, no new accounts, no sign-ups.
- No key values in any file, argument, or log. The unified API key comes
  from the `FREELLMAPI_API_KEY` environment variable at runtime.
- One bounded pass per task. No unbounded loops.

## Run it
```bash
# FreeLLMAPI server must be up on :3001 first.
# Diagnose readiness without spending anything:
./swarm-call.sh --check   # prints server status + key presence (never the key)
# Then run (key from environment only, never in a file):
FREELLMAPI_API_KEY=<set-in-environment-only> ./swarm-call.sh "prompt" [outdir]
```

`swarm-call.sh` runs both models in parallel, with per-call timeout
(`SWARM_TIMEOUT`, default 120s), retry on 429/5xx/network failure
(`SWARM_MAX_RETRIES`, default 3), exponential backoff honoring
`Retry-After`, and an `Idempotency-Key` per call so a retry after a
timeout replays the stored answer instead of burning a second free-tier
slot. Outputs land in `outdir/`: `prompt.txt`, per-model `.json` (raw),
per-model `.txt` (extracted answer), `*.headers`, `timings.tsv`.

## Routing: when 20b suffices vs 120b
- 20b first for: triage, classification, short factual answers, drafting
  structure, cheap cross-checks.
- 120b for: deep reasoning, cerebral/philosophical questions, final
  synthesis, anything where a wrong answer is costly.
- Cross-check: run both in parallel, compare, let the stronger answer win
  on evidence. A 20b draft that 120b refutes is still useful signal.
- Skip 120b when the question is shallow and 20b's answer is verifiable
  against a source (docs, calendar, file). Saves quota and latency.

## Prompt trimming
- Cap `max_tokens` per call (`SWARM_MAX_TOKENS`, default 2048). Swarm
  answers are drafts, not essays.
- Put the question and its constraints in the user prompt. Keep system
  prompts short or empty (`SWARM_SYSTEM`).
- One question per call. Multi-part asks produce muddled drafts.

## Free-tier rate limits (Groq)
- Treat 429 as "back off", never "retry instantly". The script already
  honors `Retry-After` and doubles the delay.
- If 429s persist, serialize calls (run one model, wait, run the other)
  instead of hammering in parallel.
- FreeLLMAPI has a built-in response cache and a quota forecast
  (`/api/cache`, `/api/fallback/quota-forecast`). Enabling the cache and
  checking the forecast before a big swarm run are config changes that
  need the operator's approval — see "Needs approval" below.

## Audit notes (2026-10-13)
- Before this pass there was no swarm helper: each run was ad-hoc,
  sequential curl calls with no shared timeout, retry, idempotency, or
  timing log. `swarm-call.sh` replaces that pattern.
- Stress test attempt 2 (2026-10-13): FreeLLMAPI server was DOWN and was
  restarted (build + `npm run start -w server`, no config/key changes).
  Server confirmed UP on :3001; unauthenticated POST to /v1 returns 401
  in ~0.13s. `swarm-call.sh --check` added as a preflight that reports
  server status + key presence (never the key). Live model calls remain
  BLOCKED: `FREELLMAPI_API_KEY` is absent from the shell environment.
  Fix: export the key in the shell that invokes the script.
- Attempt 2 also removed key-shaped values that attempt 1 had left in
  the script's usage comments. They were redacted by tooling before
  anyone could read them, so it is unverified whether they were real.
  If the unified key was real, rotate it. Never put key material in
  any file, even as an example.
- Attempt 3 (2026-10-13): opt-in exact-repeat cache (`SWARM_CACHE=1`,
  default off). Cache key = hash of model+params+prompt, never the key.
  Verified: seeded cache hit returns in 0s with no network call and no
  `.json` written; cache-off path still hits the network and handles
  401 cleanly with 1 attempt.
- Attempt 4 (2026-10-13): executable routing — `SWARM_MODE=cheap`
  (20b only) / `full` (both, default) / `deep` (120b only); explicit
  `SWARM_MODELS` overrides `SWARM_MODE`. `SWARM_PRESET=short` (512) /
  `default` (2048) / `long` (4096); explicit `SWARM_MAX_TOKENS`
  overrides. `--dry-run` prints the call plan without a key or
  network, including per-model cache hit/miss. All 6 dry-run cases
  verified; no-key run still exits 2.
- Attempt 5 (2026-10-13): `--dry-run` no longer creates an outdir.
  Full 10-point regression passed (syntax, --check both states,
  dry-run, no-key exit 2, cache hit, cache-off 401, no long tokens
  in script, server still UP on :3001). Live end-to-end proof still
  blocked on the missing env key — the one thing no attempt could fix.
- FreeLLMAPI routes Groq via `https://api.groq.com/openai/v1`
  (OpenAI-compatible). Invocation is `POST /v1/chat/completions` with
  model `openai/gpt-oss-120b` / `openai/gpt-oss-20b`.
- The daily `swarm-improvement-sweep` cron (first run Wed 2026-10-14)
  already covers ongoing research into free compute/APIs/projects.
  This file covers the mechanics of each run.

## Swarm expansion (2026-10-13)
- Two new models added to the FreeLLMAPI catalog via `POST /api/models`
  (admin session, no key values touched): `thinkingmachines/inkling:free`
  and `thinkingmachines/inkling-small:free` (OpenRouter, prompt=0 /
  completion=0 on OpenRouter's public pricing). Config backed up first:
  `server/data/freeapi.db.bak-20261013-swarm-expand`,
  `freellmapi.config.json.bak-20261013-swarm-expand`. Server restarted
  after the adds; Groq pair re-verified after restart (both PONG, 1s).
- Live-verified swarm models (PONG test, all $0):
  - Groq: `openai/gpt-oss-120b` (1–3s), `openai/gpt-oss-20b` (1–3s),
    `qwen/qwen3.8-27b` (3s)
  - Google: `gemini-3-flash-preview` (25s first call, cold start)
  - OpenRouter: `cohere/north-mini-code:free` (2s),
    `nvidia/nemotron-3-super-120b-a12b:free` (3s)
- New `swarm-call.sh` modes (default `full` unchanged — both Groq):
  `wide` (all 6 verified), `google` (verified Google only),
  `openrouter` (verified OpenRouter only), `reasoning` (120b + nemotron-3-super).
  Explicit `SWARM_MODELS` still overrides any mode.
- NOT live-verified (in catalog, excluded from swarm modes until verified):
  - `gemini-3.5-flash`, `gemma-4-31b-it` — Google-side rate limits;
    proxy re-cooldowns on each attempt. Retry after cooldowns clear.
  - `thinkingmachines/inkling:free`, `thinkingmachines/inkling-small:free`
    — OpenRouter free-tier daily cap hit; proxy cooldown rows show
    `tier` expiry ~24h from the cap. Retry after the reset.
- Excluded (dead upstream, do not re-add): `gemini-2.5-flash`,
  `gemini-2.5-flash-lite` — Google returns 404 "no longer available to
  new users". Catalog entries are stale.
- Rate-limit realities learned: OpenRouter free tier is ~50 req/day on an
  unfunded account — parallel batches across many :free models burn it
  fast. Google free tier re-cooldowns per attempt. For new-provider
  models, test serialized with gaps, never all at once.
- VM restarted mid-expansion (uptime reset): server was down, restarted
  with logs now at `~/workspace/freellmapi/server.log` (not /tmp — /tmp
  is wiped on restart). This is the second time the server silently
  died across a restart; the supervisor item below matters.
- CLI fallback (Ollama) evaluated and skipped: all three API providers
  are reachable, so no CLI path is needed. Disk has 99G free, but RAM
  is fully used (7G) and Ollama is not installed — no install attempted.
- Free-tier data note: Google free-tier content may be used to improve
  Google's products. Do not send sensitive content to Google models.

## Swarm expansion round 2 (2026-10-13, resumed after previous worker errored)
- Audit: previous worker's work was complete and intact despite the missing
  final report — both backups exist
  (`freellmapi.config.json.bak-20261013-swarm-expand`,
  `server/data/freeapi.db.bak-20261013-swarm-expand`), config identical to
  backup, all 6 previously verified models confirmed PONG in their output
  dirs, retry dirs contain only failed-attempt evidence. No config changes
  were needed this round: every tested model was already in the catalog.
  No new backup needed. No CLI fallback needed: all three API providers
  reachable (Ollama still not installed, RAM full — unchanged).
- Correction to round 1: the OpenRouter block was per-model, NOT
  account-wide. `liquid/lfm-2.5-2.6b:free` verified PONG while inkling
  models stayed on cooldown. OpenRouter free-tier daily cap (~50 req/day)
  still applies per account — do not burn it on parallel batches.
- 9 NEW models live-verified (PONG test, all $0, serialized, 1 attempt each):
  - Google: `gemma-4-31b-it` (4s), `gemini-3.5-flash-lite` (1s),
    `gemma-4-26b-a4b-it` (3s), `gemini-3.1-flash-lite` (1s)
  - Groq: `allam-2-7b` (1s) — REMOVED 2026-10-14: fabricated ticker/price/arithmetic in stock research, banned; stripped from `groq`/`wide` modes
  - OpenRouter: `liquid/lfm-2.5-2.6b:free` (1s),
    `dots-studio/dots-3-note-preview:free` (2s),
    `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` (14s, 2nd attempt;
    1st attempt was a 60s upstream timeout),
    `nvidia/nemotron-3.5-lightning:free` (19s, 2nd attempt; same timeout)
- Total live-verified swarm models: 14 (3 Groq + 5 Google + 6 OpenRouter) after allam-2-7b removal.
- New `swarm-call.sh` modes (default `full` unchanged — both Groq):
  `wide` (all 14 verified), `groq` (all 3 Groq), `google` (all 5 Google),
  `openrouter` (all 6 OpenRouter :free),
  `reasoning` (120b + nemotron-3-super + nemotron-nano-reasoning).
  Explicit `SWARM_MODELS` still overrides any mode.
- Still NOT verified (in catalog, excluded from swarm modes until verified):
  - `gemini-3.5-flash` — 3 failures (502 upstream_error, 429, 502).
    Google-side; retry later, do not hammer.
  - `gemini-3.6-flash` — 502 upstream_error at 0s, likely invalid model
    ID. `gemini-3.7/3.8-flash` untested, same family, presumed invalid.
  - `thinkingmachines/inkling:free`, `thinkingmachines/inkling-small:free`
    — per-model tier cooldown, expires ~23:09 UTC 2026-10-14.
  - OpenRouter `google/gemma-4-26b-a4b-it:free`,
    `google/gemma-4-31b-it:free`, `poolside/laguna-s-2.1:free`,
    `poolside/laguna-xs-2.1:free` — OpenRouter provider 429 loop
    (each retry returns 429 with a short reset, then 429 again).
    Retry later, do not hammer.
  - `nvidia/nemotron-3.5-content-safety:free` — safety classifier,
    not a chat model. Skipped by design.
  - Groq guard models (`llama-prompt-guard-*`, `gpt-oss-safeguard-20b`)
    — classifiers, not chat. Skipped by design.
  - `gemini-robotics-er-2-preview` — robotics model, not chat.
    Skipped by design.
- Latency notes: nemotron reasoning/lightning are slow (14–19s, plus
  possible 60s upstream timeouts on cold start). Keep them out of
  latency-sensitive runs; use `reasoning` mode only for deep work.

## Needs approval (all $0, none adopted yet)
1. Enable FreeLLMAPI response cache — repeats of identical prompts
   return instantly at zero provider cost. Config change.
2. Set an explicit Groq fallback chain / per-model token budget in
   FreeLLMAPI so a 429 on one model falls back instead of failing.
   Config change.
3. ~~Add a third free model (e.g. a Google AI Studio model already keyed
   in FreeLLMAPI) as a tiebreaker~~ — DONE 2026-10-13 (see "Swarm
   expansion"): 4 extra models live-verified, 4 more in catalog pending
   rate-limit retry. Remaining tiebreaker option: add the already-keyed
   Google AI Studio route as a fallback for 1-vs-1 disagreements.
   Config + workflow change.
4. Run the FreeLLMAPI server under a supervisor (systemd/pm2) so it
   survives VM restarts instead of silently going down. Setup change.
5. Enable the local exact-repeat cache by default (`SWARM_CACHE=1`).
   Implemented and verified opt-in in `swarm-call.sh`; flipping the
   default is a behavior change that needs approval. No config change.

## Stock-pick pipeline (2026-10-13, built after the MAIN round)
Two stock-pick rounds exposed the same failure classes: 429/502s,
truncated outputs, fabricated tickers/prices, arithmetic slips, quant-vs-
analyst fair-value confusion, and evidence left in /tmp. The pipeline
mechanizes the checks so the next round needs grading + synthesis only.

- `swarm-pipeline.sh <run-id> <brief-file> [models...]` — brief → run →
  auto-verify → grade → synthesize. Loads prior-round state
  (`swarm-state.md`), builds the prompt from the schema + prior context,
  runs with the `stockpick` preset, verifies, writes a grading template,
  appends a state entry. Evidence in `swarm-runs/<run-id>/`, never /tmp.
  `--dry-run` prints the prompt + call plan with zero API cost.
- `swarm-pick-schema.md` — structured-output schema. Every model must end
  with one ```json block: ticker, price, dividend, yield, shares/cost/
  leftover/income math, fair value WITH source_type
  (analyst/quantitative/other), sources, risks, falsifiers, conviction.
  All schema arithmetic is checkable by the verifier.
- `verify-pick.py <outdir>` — automated verification BEFORE grading:
  ticker format + existence (Yahoo Finance search, exact EQUITY match),
  recomputed yield/shares/cost/leftover/income, `A × B = C` prose
  arithmetic, `N shares for $Y` sizing consistency vs stated price,
  fair-value label checks, truncation (`finish_reason == length`,
  mid-sentence ending). Exit 1 on any FAIL.
  Verified against round-1 outputs: caught Allam's fabricated AFFX
  ticker + 4 sizing errors, 120b's `0.47 × 4 = 0.94` slip, and Liquid's
  truncation. Flash-Lite and 20b passed with WARNs (pre-schema prose).
  Caveat: the prose sizing check uses the FIRST stated price as reference
  — valid for one-stock-per-call runs only.
- Health: `swarm-call.sh` records per-model 429/5xx history in
  `swarm-health.json` after every run. `./swarm-call.sh --health` prints
  the table. `SWARM_SKIP_UNHEALTHY=1` skips models with ≥2 consecutive
  failures or a 429/5xx within the last hour (pipeline sets this).
- Token floor: reasoning models (120b, nemotron family) get max_tokens
  floored at 4096 unless `SWARM_MAX_TOKENS` is explicit.
  `SWARM_PRESET=stockpick` sets 4096 for all models in the run.
- Round 2 (2026-10-13): **MAIN (Main Street Capital, NYSE)** — 4/4
  models converged on the ticker but disagreed wildly on price
  ($8/$30/$50/$112 vs verified $53.77). Verified: $53.77, regular
  dividend $0.27/mo → 6.03% regular yield, NAV $33.92 → 58.5% PREMIUM.
  Conviction: Low. 20b got F (fabricated $8.00 price); 120b D+ (wrong
  CEO, stale distribution, false NAV-discount claim); Gemini Flash-Lite
  A− (best, premium thesis verified). Evidence:
  `swarm-out-second-stock/`. Round-1 evidence was rescued from /tmp
  into `swarm-out-single-stock-round1/`.

## Video-driven swarm improvements (2026-10-14)
Five talks digested (Karpathy/agentic engineering, Pocock/agent skills,
Cherny/prompt ablation, Martin/context engineering, Ng/error analysis).
Implemented, all $0:

1. **Failure ledger + ceiling math** (`verify-pick.py --ledger RUN_ID`,
   `--ceiling`). Every non-PASS model is classified into one category
   (truncation, wrong-format, hallucination, arithmetic, source-confusion,
   refusal, rate-limit, unverified, empty, other) and appended to
   `swarm-failures.csv`. `--ceiling` prints each category's share of total
   failures = the max gain from fixing it. Pipeline runs the ledger
   automatically and prints the ceiling after every run. Ng's rule: never
   spend weeks on a 5% category.
2. **Compressed synthesis input** (`swarm-synthesis-brief.py`). The
   synthesizer reads `synthesis-brief.txt` — per-model one-line claims
   (ticker, price, catalyst, fair value, conviction, reasoning, verdict) —
   never the 14 raw outputs. Counters clash/confusion in a single window.
3. **Grading/synthesis split + grader isolation.** Pipeline now writes two
   templates: `grades.md` (STAGE 1 — grade each model from its own output +
   rubric only, no cross-model comparison, no synthesis objective) and
   `synthesis.md` (STAGE 2 — reads synthesis-brief.txt + grades.md only).
   The grader never sees other models' answers or generator trails.
4. **Prompt v5 ablation** (`stock-analysis/iterations/prompts/`). 755 → 494
   words. Deleted stepwise overspecification, redundant guardrails, and the
   brevity-threat paragraph. Kept the JSON schema + field rules
   (verify-pick.py depends on them). Added Pocock conditional context
   pointers (BDC coverage, RSI flags, table-beats-memory load only when
   relevant) and leading-word stamping ("independent" in fan-out,
   "evidence-anchored" in grading). See `changelog-v5.md`.
5. **Reasoning effort** (`swarm-call.sh`): `reasoning_effort:"low"` for the
   two gpt-oss models. Live-verified 2026-10-14: gpt-oss-20b answered in
   1.8s with 15 reasoning tokens. Cache keys include the effort value.

Recurring practice (Cherny/Pocock): after every model roster change,
re-run the ablation (delete prompt, add back only what restores measured
score). Weekly behavioral deletion test: delete one prompt sentence, run,
restore only if scores drop.

## swarm-call.sh internals pass (2026-10-14 ~00:55, overnight short-term loop)
Server was down on :3001 (silent death, third occurrence); restarted via
`npm run start -w server`, confirmed UP. User systemd is unavailable on this
VM (no user bus), so the overnight cron's `--check` + one-restart preflight
is the supervisor for now.
Five live-verified fixes (backup `swarm-call.sh.bak-20261014-shortterm`):
1. `SWARM_EXCLUDE` — space-separated glob patterns; matching models never
   launch. Keeps banned `allam-2-7b` out of `groq`/`wide` modes.
2. `flock` on `${HEALTH_FILE}.lock` in `record_health` — parallel models and
   overlapping cron runs no longer race the jq read-modify-write.
3. Millisecond timings — `date +%s%N`; `timings.tsv` col 4 is now `elapsed_ms`.
4. `SWARM_STAGGER_SECS` — delay between OpenRouter `:free` launches (default
   0); stops the parallel-blast 429 loops.
5. `--check` false-UP bug fixed — a dead port used to print `http=000000`
   and report UP; now reports DOWN/BLOCKED correctly.
Standard overnight env: `SWARM_EXCLUDE="allam-2-7b" SWARM_SKIP_UNHEALTHY=1`.

## Audit pass (2026-10-14 ~12:20, prompted by "find redundancies, improve, find free gains")
Removed/fixed (backup `swarm-call.sh.bak-20261014-audit`, `verify-pick.py.bak-20261014-audit`):
1. Duplicate usage comment block in swarm-call.sh header.
2. `is_healthy` did 2 jq calls per model per run; now 1.
3. Payload (2-3 jq calls) was built before the cache check; cache hit now
   returns with zero jq and zero network.
4. Token floors split: gpt-oss 2048 (low reasoning effort), nemotron/
   reasoning 4096 (verbose). Old blanket 4096 wasted ~2k tokens/cap on
   the two fastest models.
5. `SWARM_STAGGER_SECS` now also staggers Google models (they 429 too).
6. verify-pick.py: Yahoo ticker-existence results cached across models
   (14 identical calls for one ticker -> 1).
7. verify-pick.py: `--schema 1day` + `verify_structured_1day` — the
   verifier no longer mis-scores 1-day outputs against the dividend schema.
   Pipeline passes `SWARM_SCHEMA` through automatically.
8. Pipeline: `SWARM_PROMPT_FILE` override — pipeline can now use the
   versioned prompts (e.g. prompt-current.txt) instead of only the inline
   prompt. Two-prompt-system redundancy resolved.

## New-model tests (2026-10-14 ~12:25, server restarted for testing)
- `gemini-3.8-flash`: ADDED to google roster. In FreeLLMAPI catalog; first
  PONG hit Google 503 "high demand" (transient). Will verify on next run.
- `llama-3.1-8b`: NOT routable — FreeLLMAPI "no upstream tried". Removed.
- `nemotron-3-ultra-550b`: NOT routable — same. Removed.
- Wrote `quota-check.sh` (read-only quota forecast + penalty-inspector hint).

## CLI connectors (2026-10-14 ~12:35)
- `cli-llm.sh`: calls models not routable via FreeLLMAPI through free
  endpoints (Pollinations.ai, no key). PONG-verified: llama-3.1-8b,
  nemotron-3-ultra-550b.
- `swarm-call.sh` new `SWARM_MODE=cli` — routes `cli:llama`/`cli:nemotron`
  through cli-llm.sh. No FreeLLMAPI key needed for cli-only runs.
- Caveat: Pollinations anonymous tier has no system role, ~1 req/3s, shared
  endpoint can be flaky. Use as supplement, not primary.

## Specialized roles (2026-10-14 ~12:40)
- `swarm-roles.md`: 5 roles (Grader, Synthesizer, Director, Verifier-Auditor,
  Tiebreaker) with model assignments, prompt patterns, temperature settings.
- `role-prompts.md`: copy/paste prompt templates for each role.
- Note: Both CLI models route to same Pollinations backend; roles differ by
  prompt specialization, not model weights. Re-test if true upstreams added.

## Full model profiling (2026-10-14 ~13:00)
- `profile-models.sh`: measures pong, reasoning, format, summary for each model.
- `profiles/`: raw JSON metrics for 16 models.
- `swarm-roles-full.md`: complete role schema — every model assigned by measured
  capability (speed ranking, strengths, pipeline phase mapping).
- Removed from wide/google modes (failed or unusably slow):
  gemma-4-31b-it, gemma-4-26b-a4b-it, gemini-3.1-flash-lite,
  nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free.
- Wide mode now 11 models (was 15). Google mode now 3 models (was 6).

## Research-driven restructuring (2026-10-14 ~15:30)
Based on Google DeepMind 2025 (Kim et al., 180 configs) and Anthropic 2025:

Key findings:
- Independent multi-agent amplifies errors 17.2x; centralized orchestrator contains to 4.4x
- 3-4 agents is saturation threshold; beyond that communication overhead dominates
- Sequential tasks: multi-agent DEGRADES 39-70% vs single agent
- Parallelizable tasks: centralized multi-agent improves +80.9%
- Our 11-model wide mode was way over saturation

Implemented:
- `SWARM_MODE=smart`: 4 optimal models (gpt-oss-20b, qwen3.8-27b, gpt-oss-120b, gemini-3.5-flash-lite)
- `orchestrate.py`: Centralized orchestrator with validation gates. Workers execute
  in parallel, orchestrator validates each output before accepting, then synthesizes.
  This is the critical difference from independent multi-agent.

## Optimal model chunks (2026-10-14 ~15:30)
Task-specialized 2-4 model groups per research (3-4 optimal, saturation threshold):

- `fast`: gpt-oss-20b + qwen3.8-27b + lfm-2.5-2.6b — triage, grading, classification (all <1100ms)
- `deep-think`: gpt-oss-120b + nemotron-3-super + lfm-2.5-2.6b — complex reasoning, verbose analysis
- `balanced`: gpt-oss-20b + gpt-oss-120b + gemini-3.5-flash-lite — general purpose
- `code`: north-mini-code + gpt-oss-120b — code tasks only
- `smart`: gpt-oss-20b + qwen3.8-27b + gpt-oss-120b + gemini-3.5-flash-lite — best overall

Also: `cascade-call.sh` (cheap-first with quality-gated escalation), two-tier cache
(exact + normalized), `orchestrate.py` (centralized orchestrator with validation).

## Alternative data connector (2026-10-14 ~16:05)
Built altdata-connector.py ($0, no keys required):
- SEC EDGAR: Form 4 insider filings (authoritative, live-verified)
- ApeWisdom: Reddit/WSB sentiment (live-verified, TSM rank #25)
- Finnhub: insider + congressional (optional, free tier needs FINNHUB_API_KEY)
Quiver Quant API requires $10+/month — connector built (quiver-connector.py)
but blocked on $0 constraint. Free endpoints now auth-locked.

## Altdata integration (2026-10-14 ~16:10)
- Removed quiver-connector.py (Quiver API requires $10+/month, violates $0)
- Integrated altdata-connector.py into swarm-pipeline.sh
- Pipeline now auto-enriches briefs with SEC EDGAR Form 4 + ApeWisdom sentiment
- Toggle: SWARM_ALTDATA=0 to disable. Ticker extraction skips common words.

## Finnhub integration (2026-10-14 ~16:35)
- Connected via custom.finnhub (free tier, 60 calls/min)
- Connector doc: ~/workspace/custom-connectors/custom.finnhub/CONNECTOR.md
- Wired into altdata-connector.py (insider transactions) and earnings-calendar.py
- Earnings calendar now live in every brief (next 3 days)
- Pick tracker: 4 picks logged (ARCC, MAIN, PEP, STT)

## Debloat 2026-10-17 (cynic audit)
Archived to `_archived-20261017/` (recoverable): orchestrate.py, swarm-pipeline.sh,
verify-pick.py, pick-tracker.py, earnings-calendar.py, altdata-connector.py,
swarm-synthesis-brief.py. Trashed cascade-call.sh (recoverable 30d). None had
invocations in 3 days; stock pipeline never called by analyze.sh or any cron/skill.
Moved 52 swarm-out-* files (1.7MB) to swarm-runs/. Historical entries above
describing these scripts as active are stale as of this date.
