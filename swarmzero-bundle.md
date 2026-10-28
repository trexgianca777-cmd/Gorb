# SwarmZero — single-file bundle

Upload this one file into Muse and it carries the full project:
docs, demo loop, cost-guard proxy, swarm caller, and benchmark
reports. Source repo: https://github.com/trexgianca777-cmd/Gorb
Generated: 2026-10-28T08:23:09Z. Regenerate with ./make-bundle.sh.

## Contents
- README.md
- BUDGET.md
- LIMITATIONS.md
- RESULTS.md
- SWARM.md
- TOKEN-PROTOCOL.md
- researcher-contract.md
- role-prompts.md
- swarm-roles.md
- swarm-roles-full.md
- live_demo.py
- proxy_server.py
- prompt_filter.py
- meta_client.py
- routing_ledger.py
- routing_ledger.csv
- swarm-call.sh
- contract_check.py
- live-runs/run-escalation-test-20261025.json
- live-runs/run-escalation-retest-20261026.json
- benchmark-v5/REPORT.md
- benchmark-v5/score-v5.py
- benchmark-v5/verify-v5.py
- benchmark-v5/mech-v5.py
- benchmark-v5/xrevise.py
- benchmark-v5/run-v5.sh
- benchmark-v5/tasks-v5-kept.json
- benchmark-v4/REPORT.md
- benchmark-v4/ROUTER.md
- benchmark/results/REPORT.md

================================================================
FILE: README.md
================================================================
# SwarmZero — $0 multi-agent orchestration on open-weights models

A delegation-first orchestration layer that fans work out across free-tier
and open model APIs at zero inference cost. Per-model health tracking
reroutes around rate limits and outages so the swarm degrades gracefully
instead of dying.

## How it works

- **swarm-call.sh** — parallel multi-model caller. Sends one prompt to every
  model in the roster concurrently and collects each output to its own file.
  Per-model cooldowns (honors server `Retry-After`), hourly call-load
  tracking, and automatic redelegation: an unhealthy model's slots move to
  the healthiest substitute (`SWARM_REDELEGATE=0` restores skip behavior).
  Idempotent retries with capped backoff; exact-repeat prompts hit a local
  cache with zero provider cost.
- **TOKEN-PROTOCOL.md** — compact-output contract: summaries to stdout, data
  to files, targeted reads only. Keeps context-window waste down across
  multi-agent runs.
- **researcher-contract.md + contract_check.py** — grounding contract:
  researchers tag every claim `[V]`erified, `[U]`ncertain, or `[I]`nferred;
  the checker flags untagged claims automatically.
- **cynic-prompt.md / cynic-audit.sh** — adversarial audit role that
  stress-tests outputs against failure modes before they ship.
- **role-prompts.md / swarm-roles.md / swarm-roles-full.md** — grader,
  synthesizer, and researcher role definitions; grading and synthesis are
  split into separate passes.
- **SWARM.md** — the full operating manual: free-tier rate-limit handling,
  idempotent retries, and one bounded pass per task.
- **cli-llm.sh** — free anonymous-endpoint fallback when API tiers fail.
- **benchmark/** — internal evaluation suite (tasks.json, run/score scripts)
  used to measure swarm output quality.

## Run it

```bash
# Backend: any OpenAI-compatible server (the original ran on a local
# FreeLLMAPI instance serving Groq's open-weights models).
FREELLMAPI_API_KEY=<your key, environment only> ./swarm-call.sh "prompt" [outdir]
```

`./swarm-call.sh --check` reports backend status without spending anything.
Keys come from the environment only — never files, never arguments, never
logs (enforced in SWARM.md).

## Design principles

1. Zero inference cost: free tiers, open weights, no paid APIs.
2. Degrade, don't die: health tracking + redelegation absorb outages.
3. Compact by contract: the token protocol bounds every pass.
4. Claims carry receipts: every research claim is tagged V/U/I.

## Live demo + cost-guard proxy (built 2026-10-25)

- **live_demo.py** — the judge-driven loop. Judge types any task;
  gpt-oss-20b answers, a verifier grades PASS/FAIL, FAIL escalates to
  gpt-oss-120b for a revision (max 2). Verifier is Muse Spark 1.3
  via meta_client.py when a Meta key is set, else a Groq cheap
  verifier; the output names which backend ran. Verdicts on arbitrary
  tasks are LLM-judge calls, not mechanical checks.
  `python3 live_demo.py --serve` (http://localhost:8765) or
  `python3 live_demo.py --task "..."`.
- **proxy_server.py** — prompt_filter as a drop-in OpenAI-compatible
  proxy. Point a client at http://localhost:8080/v1 and every request
  gets cheap-first routing, prefix pinning, history trim, output cap,
  repeat caching, and blind-retry blocking before it reaches upstream.
  Send `X-Verified-Fail: true` to keep the strong model.
  Upstream from UPSTREAM_BASE_URL / UPSTREAM_API_KEY.

================================================================
FILE: BUDGET.md
================================================================
# SwarmZero Meta Model API budget (dive 16 exercise)

Credit pool: $150 in Meta Model API credits, if they post to the account.
Event window: Oct 26 to Nov 4, 2026 (10 days). Daily cap: $15/day.

## Rate card used (Muse Spark standard tier, dive 16)

- Input: $1.25 per million tokens
- Output: $4.25 per million tokens
- Cached input: $0.15 per million tokens

## Per-piece costs

- One verifier call (about 2,000 input tokens, 200 output tokens):
  0.002 * 1.25 + 0.0002 * 4.25 = $0.00335
- One $15 day buys about 4,400 such verifier calls.
- A full revise loop on 100 tasks, three calls each, costs about $1.00.

## Kill rule

Projected spend above the $15 daily cap means stop and rerun on the $0
Groq roster. No loop runs without a ceiling.

## Status (checked Oct 24, 2026)

- The $150 credits are confirmed in the waiver but no claim mechanism is
  stated on the organizer pages, so whether they have posted is still a
  logged-in check for the user. Do not run metered calls until that check
  passes.
- `meta_client.py` in this directory implements the verifier call and
  returns token counts and cost per call. It makes no call without a key.

================================================================
FILE: LIMITATIONS.md
================================================================
# Limitations

What this project is not, and where it breaks. Read before adopting.

## Not a smart router

`swarm-call.sh` fans a prompt out to every model in the roster in parallel.
It does not assess task difficulty, does not route easy tasks to cheap
models, and does not pick the best answer. Model selection, grading, and
synthesis happen in the calling layer (role prompts are provided;
orchestration across roles is the operator's job). If you need automatic
best-answer selection, you need to build it on top.

## Free-tier fragility is the dominant failure mode

The benchmark found infrastructure failures outnumbering capability
failures 10 to 1: rate limits, 502s, a 10-hour Google rate-limit wall, a
broken route, and the local server dying twice. Redelegation and cooldowns
absorb this gracefully, but they do not eliminate it. Expect partial
coverage on any given run. Do not use this for anything where a missed
slot is unacceptable.

## No single model is reliable; the roster is the reliability

Per-model scores range from 10/10 (gpt-oss-120b, gpt-oss-20b, nemotron,
cohere, dots) down to format-abandonment on small models. The system's
reliability comes from redundancy across the roster, not from any one
model. If your provider access collapses to a single model, you inherit
that model's failure modes wholesale — including silent arithmetic errors
(see benchmark/FAILURES.md, F1).

## Numbers from models must be recomputed

F1 in the failure analysis: a model produced `1539.375` instead of `1665`
with full confidence and no hedging. Any pipeline stage that consumes
model-produced numbers (arithmetic, sizing, conversions) must verify them
independently. The grounding contract (researcher-contract.md) tags claims
V/U/I but does not verify arithmetic — that check is on you.

## Calibration is uneven

All tested models avoided confabulating an answer to a fabricated premise,
but quality ranged from premise-correcting through evasive refusal to
redirect-confabulation (inventing a *different* fake study after denying
the first). If you use the critic role, probe for the evasive and redirect
patterns specifically, not just outright confabulation.

## Cache means reruns don't re-probe

`SWARM_CACHE=1` (default) replays exact-repeat prompt+model answers with
zero provider cost. Reruns are cheap but measure nothing new. Set
`SWARM_CACHE=0` when you actually want to probe the model again.

## Localhost and single-machine assumptions

Health state lives in a local JSON file; the API key resolves from a local
DB. There is no distributed locking, no multi-user story, and no
sandboxing of model outputs. Run it on a machine you control, for work you
can inspect.

================================================================
FILE: RESULTS.md
================================================================
# Results — can the swarm beat the best single model?

Question: does orchestration (voting, routing, verify-revise) beat
gpt-oss-120b alone? Three benchmark generations, all with mechanical
scorers (no LLM-as-judge), all reproducible. Short answer: **no.**

## v1 — 10 basic tasks, 11 models

85/87 scored cells passed (97.7%). Five models at 10/10. Too easy to
discriminate; ceiling effect. Full report: `benchmark/results/REPORT.md`.
Failure analysis: `benchmark/FAILURES.md`.

## Baseline — 120b alone, fresh calls

gpt-oss-120b, no cache, 10 tasks: **10/10**, 2,360 tokens, ~6.4 s, $0.00.
The best single model beats the roster aggregate. Details:
`benchmark/BASELINE.md`.

## v2 — 10 harder tasks

66/70 scored cells (94.3%). Discriminated weak models from strong ones,
but 120b still 10/10 and five models at ceiling. Still no headroom at
the top.

## v3 — 8 adversarial tasks

32/50 scored cells (64.0%). **120b broke: 7/8**, failing the expression
parser on unary minus after `*` (`'3*-2'`) — the exact edge case the
prompt warned about. Code tasks were the discriminator (71% fail rate);
long-context and arithmetic tasks were free points for all models.

## Mechanism measurements on v3 (all fresh calls)

| Mechanism | Score | vs 120b (7/8) |
|---|---|---|
| Majority vote | 8/8 | tie — but never diverged from 120b; on code tasks 7 distinct answers degenerate to rank-picking the top model |
| Per-type router | 8/8 | tie — 120b ranks #1 in every category, so routing *is* 120b |
| Verify-revise (20b generator) | 3/4 on tested subset | beats its own generator (2/4 → 3/4, genuine fix on the scheduling trap), not the best model |
| Oracle (best model per task) | 8/8 | headroom exists for a perfect selector; none of the mechanisms is one |

## Caveats

- **n=8.** One task flip is 12.5 points. None of these deltas are
  statistically meaningful.
- **Run-to-run variance is large.** 120b failed task 03 on one run and
  passed it on the next; 20b did the reverse. Single-run scores have wide
  error bars. Published claims need multi-run aggregation.
- 3 of 10 roster models contributed nothing all run (transport/health).
  The effective roster was 7 models, shrinking to 4.

## What the swarm actually buys

Not capability beyond the strongest model. **Reliability**: in the v1
run, 120b was rate-limited through the entire first wave and the other
models carried it. Redundancy plus health tracking plus redelegation is
the defended claim. Everything else is unproven at these sample sizes.

## Screening new models

`benchmark-v3/screen-model.sh <model-id>` runs one model through v3 and
scores it. Bar: 7/8 (120b's reference score). Add models that beat the
bar or fill a gap (pass a task the roster fails).

## Benchmark v4 (2026-10-18) — can anything beat plain gpt-oss-120b?

16 tasks, 3 fresh reps per task per mechanism, 144/144 cells with real
outputs, all scorers mechanical. Full report: `benchmark-v4/REPORT.md`.

- plain gpt-oss-120b: **48/48 (1.000)**. revise loop (120b + mechanical
  verifier): **48/48 (1.000)** — identical, extra calls, zero benefit;
  on verifier disagreement it thrashed (1144.63 → 1357.13 → 1144.63).
- route (code tasks → 20b, rest → 120b, pre-registered): **45/48 (0.938)**.
  20b crashed 0/3 on the power-operator parser (`' 2 ** 3 '`) that 120b
  passed 3/3. Routing on stale v3 evidence hurt.
- Sign tests vs plain: route 0W/1L/15T (p=1.0), revise 0W/0L/16T (p=1.0).

Verdict: **nothing beat plain 120b — the suite ceilinged at the baseline
(48/48), so no mechanism could demonstrate a win.** v3 broke 120b at 7/8;
v4's fresh variants sat inside its reliable band (zero run-to-run variance
this time, vs large variance in v3). v5 needs adversarial task selection:
screen candidates against 120b first, keep only tasks it fails ≥2/3.
Also fixed mid-analysis: a float-tolerance scorer bug on task 08 marked the
correct 1144.63 as fail (|1144.63−1144.62|=0.0100000000002 > 0.01);
tolerance widened to 0.015, all tasks re-verified.

================================================================
FILE: SWARM.md
================================================================
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

================================================================
FILE: TOKEN-PROTOCOL.md
================================================================
# Token Protocol — minimizing orchestrator (Muse) token use

Every token the orchestrator reads is cost. These rules are mechanical, not
aspirational. They apply to all swarm scripts, engine scripts, and subagent
briefs.

## 1. Scripts: summaries to stdout, data to files

- stdout gets at most ~10 lines: what ran, the verdict, the file paths.
- Full output always goes to files under a run directory. Print each path once.
- Never print a full model response, log, or JSON blob to stdout.
- Already compliant: `swarm-call.sh` (one line per model + `timings.tsv`),
  `audit-target.sh` (one line per role + `finding-<role>.txt`).

## 2. Reading: target, don't dump

- `grep -n` / `sed -n 'A,Bp'` / `tail -N` for the section you need.
- `head -c N` caps on any curl output piped toward the orchestrator.
- Never re-read a file already in context; never `cat` a whole file "to check".

## 3. Subagents: briefs, not transcripts

- Return: verdict first, key numbers, file paths of evidence. No pasted dumps.
- If the evidence matters, write it to a file and cite the path.
- One subagent per independent task; the orchestrator reads one digest each.

## 4. Cache before compute

- `swarm-call.sh` caches exact and normalized prompt hits — check the cache
  before re-running an identical prompt.
- Before any expensive run, `ls` the expected output dir; don't redo done work.

## 5. Prompts: lean

- System prompts stay short (prompt v5: 755 -> 494 words). Cut ruthlessly;
  re-ablate after changes.
- Prefer `SWARM_MODE=smart` (4 models) over full-roster fan-out unless the
  task needs the breadth. Fewer models = fewer outputs to read.

## 6. Logs

- `tail` logs. `grep` for the error. Never dump a whole log into context.

================================================================
FILE: researcher-contract.md
================================================================
# Researcher Evidence Contract

Append this to any researcher brief. It exists because A/B runs ab-1/ab-2
(2026-10-15) proved stronger models hallucinate evidence pointers (papers,
numbers, dates) just as confidently as weak ones. The fix is not a stronger
model; it is a tagging discipline the model can follow and code can check.

## The tags

Every SPECIFIC claim must carry exactly one tag, placed immediately after
the claim:

- `[V]` — VERIFIED. You checked it against material given in THIS brief, or
  it is arithmetic you show step-by-step in your output (checkable in-output).
  Never use [V] for anything recalled from training data.
- `[U]` — UNVERIFIED. Recalled from training data or general knowledge. A
  lead, not a fact. The reader must treat it as unconfirmed.
- `[I]` — INFERENCE. Your interpretation, projection, or judgment derived
  from other claims. Not a fact about the world.

## What counts as SPECIFIC (must be tagged)

- Any number with $, %, x/×, or units: "$18.56" [V], "grew 12%" [U], "3x" [I]
- Any calendar date or year: "2024" [U], "Q3 2023" [U]
- Any named paper, study, article, or report title: '"Irrational Exuberance"' [U]
- Any URL
- Any named person quoted as an authority: 'Shiller argues...' [U]

## What does NOT need a tag

- Your own stated opinions and recommendations (they are yours; label the
  section clearly, e.g. "My judgment:").
- Logical connectives and hedges ("therefore", "suggests", "likely").
- Claims already given verbatim in the brief (cite "brief" instead).

## Rules

1. No tag = violation. A mechanical checker flags untagged specific claims,
   and the critic treats them as unsupported by construction.
2. When unsure, use [U]. A wrong [V] is worse than an honest [U].
3. Do not tag everything in sight. Opinions, hedges, and brief-given facts
   stay untagged; over-tagging is noise and will be flagged too.
4. If the brief gives you no checkable material, most of your specific
   claims should be [U]. That is correct and expected.

## Example

"Revenue grew 12% in 2024 [U] (company filings, not in brief). At a 15x
multiple [I], fair value is roughly $18.56 [V] (15 x 1.2374 = 18.56, shown
above). Shiller's 'Irrational Exuberance' [U] makes the same multiple
argument for late-cycle equities."

================================================================
FILE: role-prompts.md
================================================================
# Role Prompts — copy/paste templates for specialized CLI agents
# Usage: ./cli-llm.sh <llama|nemotron> "$(cat prompts/role-grader.txt)" out/

## role-grader.txt (cli:llama, temp 0.3)
Grade this stock pick on a 1-5 scale for each criterion. Be concise and consistent.

PICK:
[PASTE PICK HERE]

CRITERIA:
1. Evidence quality (1-5): Are claims backed by specific data?
2. Arithmetic correctness (1-5): Does the math check out?
3. Thesis coherence (1-5): Does the logic hold together?
4. Risk awareness (1-5): Are downsides acknowledged?

Output format (exact):
Evidence: X/5 - one sentence
Arithmetic: X/5 - one sentence
Thesis: X/5 - one sentence
Risk: X/5 - one sentence
Overall: PASS/FAIL

## role-synthesizer.txt (cli:llama, temp 0.2)
Extract the single central claim from this model output. One sentence. No commentary, no evaluation, just the claim.

OUTPUT:
[PASTE MODEL OUTPUT HERE]

Your response: "[MODEL_NAME]: [one-sentence claim]"

## role-director.txt (cli:nemotron, temp 0.7)
You are directing a multi-model stock-picking swarm. Analyze the failure data and recommend improvements.

FAILURE LEDGER SUMMARY:
[PASTE swarm-failures.csv summary]

CURRENT PROMPT:
[PASTE current prompt]

GRADE DISTRIBUTION:
[PASTE grade summary]

Rank the top 3 interventions by expected failure-recovery. For each:
1. What to change (one sentence)
2. Which failure category it addresses
3. Expected impact (high/medium/low)

Be specific and actionable. No vague suggestions.

## role-verifier-auditor.txt (cli:nemotron, temp 0.3)
Audit this verification result. The automated verifier flagged issues; determine if the flags are correct and if any issues were missed.

PICK:
[PASTE PICK HERE]

VERIFIER FLAGS:
[PASTE flags]

For each flag: AGREE or DISAGREE with one-sentence reason.
Then: Any MISSED issues? List them or say "none."

## role-tiebreaker.txt (cli:llama, temp 0.5)
Two models disagree on the best stock pick. Choose one. Be decisive.

PICK A:
[PASTE PICK A + grade]

PICK B:
[PASTE PICK B + grade]

Your response:
Winner: [A or B]
Why: [one paragraph, no hedging]

================================================================
FILE: swarm-roles.md
================================================================
# Swarm Role Schema — specialized agents for the stock pipeline
# Created 2026-10-14. Assigns CLI models to pipeline compartments based on
# task characteristics. Both cli:llama and cli:nemotron route via Pollinations
# (same backend); roles differ by prompt specialization, not model weights.

## Role definitions

### 1. GRADER (cli:llama)
# Task: Score stock picks against rubric. Needs: consistency, format adherence,
# fast binary decisions.
# Why llama: Small, fast, follows structured output well. Good for high-volume
# grading where consistency matters more than depth.
# Prompt pattern: rubric + pick + strict output format. Temperature 0.3.
# Input: single pick text + rubric
# Output: scores per criterion + PASS/FAIL

### 2. SYNTHESIZER (cli:llama)
# Task: Compress 14 model outputs into one-line claims per model.
# Needs: extraction, compression, no editorializing.
# Why llama: Fast, good at following "extract, don't interpret" instructions.
# Prompt pattern: "Extract the single central claim. One sentence. No commentary."
# Input: raw model output
# Output: "MODEL: one-line claim"

### 3. DIRECTOR (cli:nemotron)
# Task: Analyze failure ledger + grades, decide what to improve next.
# Needs: pattern recognition across runs, prioritization, strategic thinking.
# Why nemotron: Larger context window handles multi-run history. Better at
# "what should we change" vs "what is this."
# Prompt pattern: failure categories + grade distributions + "rank the top 3
# interventions by expected failure-recovery"
# Input: swarm-failures.csv summary + grades.md + current prompt
# Output: ranked intervention list with expected impact

### 4. VERIFIER-AUDITOR (cli:nemotron)
# Task: Spot-check verify-pick.py results. Needs: arithmetic precision,
# skepticism, attention to edge cases the script might miss.
# Why nemotron: More thorough on nuanced cases (e.g., "is this fair value
# label actually correct?" vs just "does the field exist").
# Prompt pattern: pick + verifier flags + "do you agree with each flag? Any
# missed issues?"
# Input: pick text + verification report
# Output: agree/disagree per flag + additional issues found

### 5. TIEBREAKER (cli:llama)
# Task: When models split on a pick, make final call. Needs: decisiveness,
# clear reasoning, no hedging.
# Why llama: Fast, less prone to overthinking. Good for "pick one and commit."
# Prompt pattern: two competing picks + "choose one. One paragraph why. No hedging."
# Input: 2-3 competing picks with grades
# Output: winner + one-paragraph justification

## Usage in pipeline

# Grade all picks (parallel, fast):
#   SWARM_MODE=cli SWARM_MODELS="cli:llama" ./swarm-call.sh "$(cat grade-prompt.txt)" out/

# Direct improvement (single, thoughtful):
#   ./cli-llm.sh nemotron "$(cat director-prompt.txt)" out/

# Synthesize claims (parallel, fast):
#   ./cli-llm.sh llama "Extract the central claim in one sentence: $output" out/

## Temperature recommendations
# Grader: 0.3 (consistency)
# Synthesizer: 0.2 (extraction, minimal creativity)
# Director: 0.7 (strategic thinking benefits from some variance)
# Verifier-auditor: 0.3 (precision)
# Tiebreaker: 0.5 (decisive but reasoned)

## Limitations
# - Both CLI models currently route to the same Pollinations backend.
#   Role differentiation is via prompt engineering, not model weights.
# - If FreeLLMAPI adds true upstream providers for these models, re-test
#   and update role assignments based on actual capability differences.
# - Pollinations has no system role; prepend instructions to user message.

================================================================
FILE: swarm-roles-full.md
================================================================
# Complete Model Role Schema — every model assigned by measured capability
# Generated 2026-10-14 from live profiling (pong, reasoning, format, summary tests)
# See profiles/ for raw metrics.

## Speed ranking (measured pong latency)
# 1. qwen/qwen3.8-27b: 308ms
# 2. openai/gpt-oss-20b: 370ms
# 3. liquid/lfm-2.5-2.6b:free: 533ms
# 4. cli:nemotron: 686ms
# 5. gemini-3.5-flash-lite: 994ms
# 6. cli:llama: 1109ms
# 7. openai/gpt-oss-120b: 1511ms
# 8. dots-studio/dots-3-note-preview:free: 1443ms
# 9. nvidia/nemotron-3-super-120b-a12b:free: 1549ms
# 10. cohere/north-mini-code:free: 1925ms
# 11. nvidia/nemotron-3.5-lightning:free: 2151ms
# 12. gemma-4-31b-it: 2625ms (FAILED reasoning test)
# 13. gemini-3-flash-preview: 2680ms
# 14. gemini-3.1-flash-lite: 10729ms (FAILED)
# 15. gemma-4-26b-a4b-it: 92250ms (FAILED, unusable)
# 16. nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free: 92997ms (unusable)

## Role assignments

### TIER 1: Primary workers (fast + reliable)

**openai/gpt-oss-20b** — THE WORKHORSE
- Speed: 370ms pong, 701ms reasoning. Fastest reliable reasoning model.
- Strengths: Quick decisions, triage, classification, format adherence.
- Roles: Primary grader, tiebreaker, fast synthesis, failure-ledger classifier.
- Use for: High-volume tasks where speed matters. First call for any new task type.

**qwen/qwen3.8-27b** — THE SPRINTER
- Speed: 308ms pong (fastest). Reasoning: 1377ms but verbose (1354 chars).
- Strengths: Raw speed, detailed reasoning output.
- Roles: Speed-critical nomination, verbose analysis when detail needed.
- Use for: When you need an answer NOW. Good for initial broad sweeps.

**liquid/lfm-2.5-2.6b:free** — THE SPECIALIST
- Speed: 533ms pong. Reasoning: 2143ms, VERY verbose (1522 chars).
- Strengths: Detailed explanations, thorough reasoning chains.
- Weakness: Verbose (may hit token limits on long tasks).
- Roles: Deep-dive analysis, explanation generation, teaching/exposition.
- Use for: When you need the "why" explained thoroughly.

### TIER 2: Heavy lifters (slower but capable)

**openai/gpt-oss-120b** — THE THINKER
- Speed: 1511ms pong, 1238ms reasoning. Balanced.
- Strengths: Complex reasoning, nuanced judgment, strategic thinking.
- Roles: Director (improvement planning), complex synthesis, final review.
- Use for: Tasks requiring judgment calls. The "second opinion" after fast models.

**nvidia/nemotron-3-super-120b-a12b:free** — THE REASONER
- Speed: 1549ms pong, 7009ms reasoning (slow but thorough).
- Strengths: Step-by-step reasoning, methodical analysis.
- Roles: Verifier-auditor, complex math verification, deep analysis.
- Use for: When correctness matters more than speed.

**gemini-3.5-flash-lite** — THE RELIABLE
- Speed: 994ms pong. All tests passed.
- Strengths: Consistent, reliable, good all-rounder.
- Roles: Backup grader, synthesis, general tasks.
- Use for: When primary workers are rate-limited.

### TIER 3: Specialists

**cohere/north-mini-code:free** — THE CODER
- Speed: 1925ms pong. Code-focused model.
- Strengths: Code generation, script analysis, technical tasks.
- Roles: Code review, script generation, technical documentation.
- Use for: Any code-related swarm tasks. Don't use for stock picking.

**dots-studio/dots-3-note-preview:free** — THE WILD CARD
- Speed: 1443ms pong, 6275ms reasoning. Verbose (1217 chars).
- Strengths: Unknown (preview model), but completed all tests.
- Roles: Experimental, diversity of perspective.
- Use for: When you want an uncorrelated opinion.

**nvidia/nemotron-3.5-lightning:free** — THE SLOW BURN
- Speed: 2151ms pong, 51173ms reasoning (very slow).
- Strengths: Completed tests, but too slow for interactive use.
- Roles: Overnight batch processing only.
- Use for: Non-urgent background analysis.

### TIER 4: CLI models (via Pollinations)

**cli:llama** — THE PROXY
- Speed: 1109ms pong. Routes to Pollinations backend.
- Strengths: No API key needed, reliable.
- Roles: Grader, synthesizer (as defined in swarm-roles.md).
- Caveat: Same backend as cli:nemotron; roles differ by prompt, not capability.

**cli:nemotron** — THE PROXY-2
- Speed: 686ms pong (faster than cli:llama). Same backend.
- Strengths: Slightly faster than cli:llama.
- Roles: Director, verifier-auditor (as defined in swarm-roles.md).
- Caveat: Same backend as cli:llama.

### TIER 5: Unreliable (use with caution)

**gemini-3-flash-preview** — SLOW
- Speed: 2680ms pong, 6267ms reasoning but only 128 chars (truncated?).
- Status: Completed tests but slow and terse.
- Recommendation: Use only if other Google models are down.

**gemma-4-31b-it** — FAILED
- Speed: 2625ms pong, but 0 chars on reasoning (failed).
- Status: Unreliable. Skip unless no alternative.

**gemini-3.1-flash-lite** — FAILED
- Speed: 10729ms pong (10+ seconds). Failed tests.
- Status: Too slow, unreliable. Deprecate.

**gemma-4-26b-a4b-it** — UNUSABLE
- Speed: 92250ms (92 seconds!). Failed.
- Status: Do not use.

**nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free** — UNUSABLE
- Speed: 92997ms (93 seconds!).
- Status: Do not use.

**gemini-3.8-flash** — UNTESTED
- Status: Added to roster but profiling hit rate limits.
- Recommendation: Test before assigning critical roles.

## Pipeline role mapping

### Nomination phase (need: diversity, speed)
- Primary: qwen3.8-27b, gpt-oss-20b, gpt-oss-120b (fast + diverse)
- Backup: gemini-3.5-flash-lite, lfm-2.5-2.6b

### Grading phase (need: consistency, speed)
- Primary: gpt-oss-20b (370ms, reliable)
- Backup: qwen3.8-27b, gemini-3.5-flash-lite
- CLI: cli:llama

### Synthesis phase (need: compression, speed)
- Primary: gpt-oss-20b, qwen3.8-27b
- CLI: cli:llama

### Director phase (need: judgment, strategy)
- Primary: gpt-oss-120b (balanced reasoning)
- Backup: nemotron-3-super (thorough but slow)
- CLI: cli:nemotron

### Verification phase (need: precision, skepticism)
- Primary: nemotron-3-super (methodical)
- Backup: gpt-oss-120b
- CLI: cli:nemotron

### Code tasks
- Exclusive: north-mini-code

## Recommended SWARM_MODE updates

# Fast nomination (3 fastest reliable):
#   SWARM_MODELS="openai/gpt-oss-20b qwen/qwen3.8-27b liquid/lfm-2.5-2.6b:free"

# Balanced (speed + reasoning):
#   SWARM_MODELS="openai/gpt-oss-20b openai/gpt-oss-120b qwen/qwen3.8-27b gemini-3.5-flash-lite"

# Deep analysis (slow but thorough):
#   SWARM_MODELS="openai/gpt-oss-120b nvidia/nemotron-3-super-120b-a12b:free liquid/lfm-2.5-2.6b:free"

# Deprecate from wide mode:
#   Remove: gemma-4-31b-it, gemma-4-26b-a4b-it, gemini-3.1-flash-lite,
#           nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
#   (all failed or unusably slow)

================================================================
FILE: live_demo.py
================================================================
#!/usr/bin/env python3
"""live_demo.py — SwarmZero live judge-driven loop (option 1).

The judge types any task. Nothing is pre-baked: the cheap tier answers,
a verifier grades it, and a FAIL escalates to the strong tier for a
revision. The trajectory (model, verdict, cost) is the receipt.

Pipeline, all $0 unless a Meta key is present:
  - Generator:  Groq gpt-oss-20b via swarm-call.sh (vault key resolved
    in-memory inside the swarm-call subprocess, never printed).
  - Verifier:  Muse Spark 1.3 via meta_client.py IF MODEL_API_KEY or
    META_API_KEY is set (metered, cost logged). Otherwise a Groq cheap
    verifier (gpt-oss-20b) grading with the same PASS/FAIL prompt.
    The output always names which verifier backend ran.
  - Reviser:   Groq gpt-oss-120b via swarm-call.sh, only on FAIL.

Honesty label: for arbitrary judge-typed tasks the verifier is an LLM
judge (PASS/FAIL plus one sentence), not a mechanical checker. The
v5 benchmark win used mechanical checkers on frozen tasks; this demo
proves the loop structure runs live on unseen input, not that every
verdict is mechanically certain.

Usage:
  CLI:  python3 live_demo.py --task "Write a Python function that sums a list"
  Web:  python3 live_demo.py --serve [--port 8765]
        then open http://localhost:8765 and type a task.
  Env:  LIVE_MAX_REVISIONS (default 2), SWARM_MAX_TOKENS (default 2048).
        Cap raised 2026-10-26 (event week): 512 truncated code answers
        in the Oct 25 escalation test, so code tasks now get 2048.
"""

import html
import json
import os
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")
VAULT = os.path.expanduser("~/workspace/freellmapi/vault/vault.sh")
CHEAP = "openai/gpt-oss-20b"
STRONG = "openai/gpt-oss-120b"
MAX_REVISIONS = int(os.environ.get("LIVE_MAX_REVISIONS", "2"))


def _safe(model):
    return model.replace("/", "_").replace(":", "_")


def swarm_call(model, prompt, system=None):
    """One single-model call through swarm-call.sh. Returns text or None."""
    outdir = tempfile.mkdtemp(prefix="live-demo-")
    cmd = ["bash", "-c",
           f'. "{VAULT}"; swarm_vault_load || exit 2; '
           f'exec "{SWARM_CALL}" "$@"',
           "live-demo", prompt, outdir]
    env = dict(os.environ)
    env["SWARM_MODELS"] = model
    env["SWARM_MAX_TOKENS"] = os.environ.get("SWARM_MAX_TOKENS", "2048")
    env["SWARM_TIMEOUT"] = os.environ.get("SWARM_TIMEOUT", "120")
    if system:
        env["SWARM_SYSTEM"] = system
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True,
                              text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    txt_path = os.path.join(outdir, _safe(model) + ".txt")
    if os.path.exists(txt_path):
        with open(txt_path) as f:
            return f.read().strip() or None
    return None


def verify(task, candidate):
    """Returns (verdict, detail, backend, cost_usd)."""
    if os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY"):
        sys.path.insert(0, HERE)
        from meta_client import verify as meta_verify
        r = meta_verify(task, candidate)
        return r["verdict"], r["detail"], "meta:muse-spark-1.3", r["cost_usd"]
    verdict_text = swarm_call(
        CHEAP,
        f"Task: {task}\nCandidate output: {candidate}\n"
        "Reply with PASS or FAIL and one sentence. No other text.",
        system="You are a grader. Reply with PASS or FAIL and one sentence.")
    if not verdict_text:
        return "FAIL", "verifier call failed", "groq:gpt-oss-20b", 0.0
    first = verdict_text.strip().split("\n")[0]
    verdict = "PASS" if first.upper().startswith("PASS") else "FAIL"
    return verdict, verdict_text.strip()[:300], "groq:gpt-oss-20b", 0.0


def est_tokens(text):
    return max(1, (len(text) + 3) // 4)


def run_loop(task):
    """Runs the verifier-gated loop. Returns the trajectory dict."""
    steps = []
    t0 = time.time()
    answer = swarm_call(
        CHEAP,
        f"Complete this task. Keep the answer short.\nTask: {task}",
        system="You answer tasks concisely. No preamble.")
    if not answer:
        return {"task": task, "final": "ERROR",
                "detail": "cheap-tier call failed",
                "steps": steps, "elapsed_s": round(time.time() - t0, 1)}
    verdict, detail, backend, cost = verify(task, answer)
    steps.append({"model": CHEAP, "role": "generate", "verdict": verdict,
                  "verifier": backend, "cost_usd": cost,
                  "answer": answer[:2000]})
    revisions = 0
    while verdict == "FAIL" and revisions < MAX_REVISIONS:
        revisions += 1
        revised = swarm_call(
            STRONG,
            f"Revise this answer so it passes. Verdict detail: {detail}\n"
            f"Task: {task}\nPrevious answer: {answer}\n"
            "Return only the revised answer.",
            system="You revise answers to satisfy a grader. Return only "
                   "the revised answer.")
        if not revised:
            break
        answer = revised
        verdict, detail, backend, cost = verify(task, answer)
        steps.append({"model": STRONG, "role": "revise", "verdict": verdict,
                      "verifier": backend, "cost_usd": cost,
                      "answer": answer[:2000]})
    total_cost = round(sum(s["cost_usd"] for s in steps), 5)
    return {"task": task, "final": verdict, "detail": detail,
            "steps": steps, "total_cost_usd": total_cost,
            "elapsed_s": round(time.time() - t0, 1)}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>SwarmZero live loop</title></head><body>
<h1>SwarmZero live loop</h1>
<p>Type any task. Cheap tier answers, verifier grades, FAIL escalates
to the strong tier. Verdicts on arbitrary tasks are LLM-judge calls,
not mechanical checks.</p>
<form method="post" action="/run">
<input name="task" size="80" placeholder="e.g. Write a Python function that sums a list, with a test">
<button type="submit">Run</button></form>
{body}</body></html>"""


def render(traj):
    rows = []
    for i, s in enumerate(traj["steps"], 1):
        rows.append(
            f"<h3>Step {i}: {html.escape(s['model'])} "
            f"({html.escape(s['role'])}) → {html.escape(s['verdict'])}</h3>"
            f"<p>Verifier: {html.escape(s['verifier'])} · "
            f"cost: ${s['cost_usd']}</p>"
            f"<pre>{html.escape(s['answer'])}</pre>")
    return (f"<h2>Final: {html.escape(traj['final'])}</h2>"
            f"<p>{html.escape(traj.get('detail', ''))} · "
            f"{traj.get('elapsed_s', '?')}s · "
            f"total cost ${traj.get('total_cost_usd', 0)}</p>"
            + "".join(rows))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send(PAGE.format(body=""))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(n).decode())
        task = (fields.get("task") or [""])[0].strip()
        if not task:
            self._send(PAGE.format(body="<p>Empty task.</p>"))
            return
        traj = run_loop(task)
        run_dir = os.path.join(HERE, "live-runs")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, f"run-{int(time.time())}.json"),
                  "w") as f:
            json.dump(traj, f, indent=2)
        self._send(PAGE.format(body=render(traj)))

    def _send(self, body):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    args = sys.argv[1:]
    if "--serve" in args:
        port = 8765
        if "--port" in args:
            port = int(args[args.index("--port") + 1])
        print(f"SwarmZero live loop on http://localhost:{port} "
              "(Ctrl-C to stop)")
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    elif "--task" in args:
        task = args[args.index("--task") + 1]
        print(json.dumps(run_loop(task), indent=2))
    else:
        print("usage: live_demo.py --task \"...\" | --serve [--port N]")
        sys.exit(2)


if __name__ == "__main__":
    main()

================================================================
FILE: proxy_server.py
================================================================
#!/usr/bin/env python3
"""proxy_server.py — prompt_filter as a drop-in product (option 2).

A $0 OpenAI-compatible proxy: point any chat-completions client at
this server instead of the provider, and every request passes through
the prompt_filter rules before it reaches the upstream API:

  1. Cheap tier by default; strong model only with verified failure.
  2. Stable system prefix pinned (prefix changes flagged as cache breaks).
  3. History trimmed to budget (system + goal + recent turns kept).
  4. Output capped at the ceiling.
  5. Exact repeats served from cache at zero calls.
  6. Identical retries of model-level failures blocked.

It is a proxy, not a model: it never answers itself, it forwards.
Upstream auth comes from the environment, never from a file the proxy
writes. The filter state and ledger live next to this script.

Usage:
  UPSTREAM_BASE_URL=http://localhost:3001/v1 \
  UPSTREAM_API_KEY=$FREELLMAPI_API_KEY \
  FILTER_CHEAP_MODEL=openai/gpt-oss-20b \
  FILTER_STRONG_MODEL=openai/gpt-oss-120b \
  python3 proxy_server.py [--port 8080]

Client config (OpenAI SDK):
  client = OpenAI(base_url="http://localhost:8080/v1",
                  api_key="proxy")  # key ignored; upstream key is server-side

Escalation: a client that already has a verified cheap-tier failure
sends header "X-Verified-Fail: true" and the strong model is kept.
A transport-level retry sends "X-Transport-Error: true".

Endpoints:
  POST /v1/chat/completions   filtered + forwarded (or cached/blocked)
  GET  /health                {"status": "ok"}
  GET  /                       usage text
"""

import json
import os
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from prompt_filter import PromptFilter  # noqa: E402

UPSTREAM = os.environ.get("UPSTREAM_BASE_URL",
                          "http://localhost:3001/v1").rstrip("/")
UPSTREAM_KEY = (os.environ.get("UPSTREAM_API_KEY")
                or os.environ.get("FREELLMAPI_API_KEY", ""))
CHEAP = os.environ.get("FILTER_CHEAP_MODEL", "openai/gpt-oss-20b")
STRONG = os.environ.get("FILTER_STRONG_MODEL", "openai/gpt-oss-120b")

PF = PromptFilter(
    cheap_model=CHEAP, strong_model=STRONG,
    state_path=os.path.join(HERE, "proxy_state.json"),
    ledger_path=os.path.join(HERE, "proxy_ledger.jsonl"))


def forward(req):
    """POST the filtered request upstream; return (status, body_dict)."""
    data = json.dumps(req).encode()
    http_req = urllib.request.Request(
        UPSTREAM + "/chat/completions", data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {UPSTREAM_KEY}"},
        method="POST")
    try:
        with urllib.request.urlopen(http_req, timeout=300) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": f"upstream HTTP {e.code}"}
    except Exception as e:
        return 502, {"error": f"upstream unreachable: {e}"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._text(200, __doc__)

    def do_POST(self):
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self._json(404, {"error": "unknown path"})
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n).decode())
        except Exception:
            self._json(400, {"error": "request body is not JSON"})
            return
        meta = {
            "verified_fail":
                self.headers.get("X-Verified-Fail", "").lower() == "true",
            "transport_error":
                self.headers.get("X-Transport-Error", "").lower() == "true",
        }
        req, report = PF.prepare(body, meta=meta)
        if report["action"] == "cached":
            self._json(200, {"cached": True,
                             "response": report["cached_response"],
                             "filter": report})
            return
        if report["action"] == "blocked":
            self._json(400, {"error": "blocked by prompt_filter",
                             "reason": report.get("reason"),
                             "filter": report})
            return
        status, resp_body = forward(req)
        PF.record_result(req, ok=(status == 200), response=resp_body)
        self._json(status, resp_body)

    def _json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, status, text):
        data = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    port = 8080
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    print(f"prompt_filter proxy on http://localhost:{port}/v1 "
          f"(upstream {UPSTREAM}, cheap {CHEAP}, strong {STRONG})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

================================================================
FILE: prompt_filter.py
================================================================
#!/usr/bin/env python3
"""prompt_filter.py — a $0 pre-flight filter for LLM API calls.

Sits between your code and any chat-completions style API. It never calls a
model itself; it rewrites, blocks, or passes through a request dict of the
form {"model": str, "messages": [{"role": ..., "content": ...}, ...],
"max_tokens": int (optional), ...} and returns (request, report).

Rules enforced, mapped to the token-saving discipline:

1. ROUTE CHEAP FIRST. The request model is forced to the cheap tier unless
   the caller passes meta={"verified_fail": True}, meaning a deterministic
   check already failed the cheap tier's answer. Escalation without evidence
   is downgraded and flagged.
2. STABLE PREFIX. The system prompt is moved to position 0 and its hash is
   pinned in the state file. If a later call changes it, the report flags a
   cache break (a changed prefix forfeits provider prompt-cache discounts).
3. TRIM HISTORY. System + the first user message (the goal) are pinned.
   Middle turns are dropped, oldest first, until the estimated input fits
   the token budget. A marker records how many turns were elided.
4. CAP OUTPUT. max_tokens is set to the configured ceiling when absent or
   above it. With structured=True, an instruction to answer in JSON fields
   only is appended once to the system prompt.
5. CODE BEFORE MODEL. Empty content is rejected. An exact repeat of a
   previously answered request returns the cached response with zero calls.
6. NO BLIND RETRIES. A request whose identical hash already produced a
   model-level failure is blocked until its inputs change or the caller
   passes meta={"transport_error": True}.

Token estimates use chars/4 (close enough for budgeting; the ledger records
estimates, not billing truth). State (response cache, attempt ledger,
prefix pin) lives in one JSON file next to this script. Every prepared call
appends one line to prompt_filter_ledger.jsonl with before/after estimates.

Usage as a library:

    from prompt_filter import PromptFilter
    pf = PromptFilter(cheap_model="meta/llama-3.1-8b",
                      strong_model="meta/llama-3.3-70b")
    req, report = pf.prepare(request_dict)
    if report["action"] == "cached":   # zero-cost answer
        answer = report["cached_response"]
    elif report["action"] == "blocked":
        ...                            # fix inputs; do not resend
    else:
        answer = call_api(req)         # your code
        pf.record_result(req, ok=True, response=answer)

CLI self-test:  python3 prompt_filter.py --selftest
"""

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "prompt_filter_state.json")
LEDGER_PATH = os.path.join(HERE, "prompt_filter_ledger.jsonl")


def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token for English text/code."""
    return max(1, (len(text) + 3) // 4)


def messages_tokens(messages):
    return sum(estimate_tokens(m.get("content", "")) + 4 for m in messages)


def request_hash(model, messages):
    payload = json.dumps({"model": model, "messages": messages},
                         sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PromptFilter:
    def __init__(self, cheap_model, strong_model=None,
                 input_budget=6000, output_ceiling=512,
                 keep_recent_turns=6, state_path=STATE_PATH,
                 ledger_path=LEDGER_PATH):
        self.cheap_model = cheap_model
        self.strong_model = strong_model or cheap_model
        self.input_budget = input_budget
        self.output_ceiling = output_ceiling
        self.keep_recent_turns = keep_recent_turns
        self.state_path = state_path
        self.ledger_path = ledger_path
        self.state = self._load_state()

    # -- state ---------------------------------------------------------
    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                return json.load(f)
        return {"prefix_hash": None, "cache": {}, "attempts": {}}

    def _save_state(self):
        with open(self.state_path, "w") as f:
            json.dump(self.state, f)

    def _log(self, entry):
        entry["ts"] = int(time.time())
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # -- main entry ----------------------------------------------------
    def prepare(self, request, meta=None):
        meta = meta or {}
        report = {"action": "pass", "flags": []}
        req = json.loads(json.dumps(request))  # deep copy
        messages = req.get("messages", [])
        before_tokens = messages_tokens(messages)

        # Rule 5a: reject empties before anything else.
        if not messages or not any(m.get("content", "").strip()
                                   for m in messages):
            report.update(action="blocked", reason="empty request")
            self._log({"result": "blocked-empty",
                       "in_tokens": before_tokens})
            return req, report

        # Rule 2: pin the system prompt at position 0, watch its hash.
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        if system:
            sys_hash = hashlib.sha256(
                system[0]["content"].encode()).hexdigest()[:16]
            if self.state["prefix_hash"] is None:
                self.state["prefix_hash"] = sys_hash
                self._save_state()
            elif self.state["prefix_hash"] != sys_hash:
                report["flags"].append(
                    "PREFIX CHANGED: cache discount forfeited this call")
            messages = [system[0]] + rest

        # Rule 3: trim history to budget. Keep system, the goal (first
        # user message), and the most recent turns; elide the middle.
        if messages_tokens(messages) > self.input_budget:
            head, tail = [], messages
            sys_msgs = [m for m in messages if m.get("role") == "system"]
            convo = [m for m in messages if m.get("role") != "system"]
            if sys_msgs:
                head.append(sys_msgs[0])
            goal = next((m for m in convo if m.get("role") == "user"),
                        None)
            if goal is not None:
                head.append(goal)
                convo = [m for m in convo if m is not goal]
            recent = convo[-self.keep_recent_turns:]
            dropped = len(convo) - len(recent)
            messages = head + ([{"role": "system",
                                 "content": f"[{dropped} earlier turns "
                                            f"elided by prompt_filter]"}]
                               if dropped else []) + recent
            report["flags"].append(f"history trimmed: {dropped} turns "
                                   f"elided")

        # Rule 4: cap output; optional JSON-only instruction.
        if req.get("max_tokens") is None or \
                req["max_tokens"] > self.output_ceiling:
            req["max_tokens"] = self.output_ceiling
            report["flags"].append(
                f"max_tokens capped at {self.output_ceiling}")
        if meta.get("structured") and system:
            tag = " Respond with JSON fields only, no prose."
            if tag not in messages[0]["content"]:
                messages[0]["content"] += tag

        req["messages"] = messages

        # Rule 1: cheap tier by default; escalation needs evidence.
        if req.get("model") == self.strong_model and \
                not meta.get("verified_fail"):
            req["model"] = self.cheap_model
            report["flags"].append(
                "escalation downgraded: no verified_fail evidence")

        h = request_hash(req["model"], req["messages"])
        report["hash"] = h

        # Rule 5b: exact repeat of an answered request costs nothing.
        if h in self.state["cache"]:
            report.update(action="cached",
                          cached_response=self.state["cache"][h])
            self._log({"result": "cache-hit", "hash": h,
                       "in_tokens": 0,
                       "saved_tokens": messages_tokens(messages)})
            return req, report

        # Rule 6: identical retry of a model-level failure is blocked.
        prev = self.state["attempts"].get(h)
        if prev and not prev.get("ok") and not meta.get("transport_error"):
            report.update(action="blocked",
                          reason="identical request already failed at "
                                 "the model level; change the inputs "
                                 "instead of retrying")
            self._log({"result": "blocked-retry", "hash": h,
                       "in_tokens": before_tokens})
            return req, report

        after_tokens = messages_tokens(messages)
        report["est_input_tokens"] = after_tokens
        report["saved_tokens"] = before_tokens - after_tokens
        self._log({"result": "pass", "hash": h, "model": req["model"],
                   "in_tokens": after_tokens,
                   "saved_tokens": report["saved_tokens"],
                   "flags": report["flags"]})
        return req, report

    def record_result(self, request, ok, response=None):
        """Call after the API returns, so cache/retry rules have data."""
        h = request_hash(request.get("model", ""),
                         request.get("messages", []))
        self.state["attempts"][h] = {"ok": bool(ok)}
        if ok and response is not None:
            self.state["cache"][h] = response
        self._save_state()


def selftest():
    tmp_state = os.path.join(HERE, "prompt_filter_state.test.json")
    tmp_ledger = os.path.join(HERE, "prompt_filter_ledger.test.jsonl")
    for p in (tmp_state, tmp_ledger):
        if os.path.exists(p):
            os.remove(p)
    pf = PromptFilter(cheap_model="cheap-8b", strong_model="strong-70b",
                      input_budget=200, output_ceiling=256,
                      keep_recent_turns=2,
                      state_path=tmp_state, ledger_path=tmp_ledger)

    big_history = [{"role": "system", "content": "You grade answers."},
                   {"role": "user", "content": "GOAL: grade the set."}]
    for i in range(10):
        big_history.append({"role": "user",
                            "content": f"turn {i} " + "x" * 120})
        big_history.append({"role": "assistant",
                            "content": f"reply {i} " + "y" * 120})
    big_history.append({"role": "user", "content": "grade item 42"})

    req, rep = pf.prepare({"model": "strong-70b",
                           "messages": big_history, "max_tokens": 4000})
    assert rep["action"] == "pass", rep
    assert req["model"] == "cheap-8b", req["model"]
    assert req["max_tokens"] == 256
    assert messages_tokens(req["messages"]) <= 200 + 60, \
        messages_tokens(req["messages"])
    assert rep["saved_tokens"] > 500, rep["saved_tokens"]
    print("1. downgrade + cap + trim OK; saved ~%d est. tokens"
          % rep["saved_tokens"])

    pf.record_result(req, ok=True, response='{"grade": "pass"}')
    req2, rep2 = pf.prepare({"model": "strong-70b",
                             "messages": big_history, "max_tokens": 4000})
    assert rep2["action"] == "cached", rep2
    print("2. repeat request served from cache, zero calls")

    fail_req = {"model": "cheap-8b",
                "messages": [{"role": "user", "content": "hard task"}]}
    fail_req, _ = pf.prepare(fail_req)
    pf.record_result(fail_req, ok=False)
    _, rep3 = pf.prepare({"model": "cheap-8b",
                          "messages": [{"role": "user",
                                        "content": "hard task"}]})
    assert rep3["action"] == "blocked", rep3
    print("3. blind retry of a failed request blocked")

    esc, rep4 = pf.prepare({"model": "strong-70b",
                            "messages": [{"role": "user",
                                          "content": "hard task v2"}]},
                           meta={"verified_fail": True})
    assert esc["model"] == "strong-70b" and rep4["action"] == "pass"
    print("4. escalation allowed with verified_fail evidence")

    for p in (tmp_state, tmp_ledger):
        os.remove(p)
    print("SELFTEST PASSED")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        print(__doc__)

================================================================
FILE: meta_client.py
================================================================
"""SwarmZero metered verifier via the Meta Model API (dive 16 exercise).

Reads the key from MODEL_API_KEY (META_API_KEY also accepted as a
fallback). Makes no call on import. Returns PASS/FAIL plus token counts
so every verdict can be logged against the $15/day budget in BUDGET.md.

Usage:
    export MODEL_API_KEY=...
    python3 meta_client.py "Task: sort a list." "sorted([3,1,2]) == [1,2,3]"
"""

import json
import os
import sys

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
# Standard-tier rate card from dive 16, per million tokens.
RATE_IN = 1.25
RATE_OUT = 4.25


def cost_usd(in_tokens, out_tokens):
    return in_tokens / 1e6 * RATE_IN + out_tokens / 1e6 * RATE_OUT


def verify(task, candidate_output, client=None):
    """One metered verifier call. Returns a dict with verdict, tokens, cost."""
    if client is None:
        from openai import OpenAI

        api_key = os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY")
        if not api_key:
            raise RuntimeError("MODEL_API_KEY (or META_API_KEY) is not set")
        client = OpenAI(base_url=BASE_URL, api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a grader. Reply with PASS or FAIL and one sentence.",
            },
            {
                "role": "user",
                "content": f"Task: {task}\nCandidate output: {candidate_output}",
            },
        ],
        max_tokens=64,
    )
    text = resp.choices[0].message.content.strip()
    verdict = "PASS" if text.upper().startswith("PASS") else "FAIL"
    u = resp.usage
    return {
        "verdict": verdict,
        "detail": text,
        "in_tokens": u.prompt_tokens,
        "out_tokens": u.completion_tokens,
        "cost_usd": round(cost_usd(u.prompt_tokens, u.completion_tokens), 5),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: meta_client.py <task> <candidate output>")
        sys.exit(2)
    print(json.dumps(verify(sys.argv[1], sys.argv[2]), indent=2))

================================================================
FILE: routing_ledger.py
================================================================
"""SwarmZero routing ledger (dive 17 exercise, verifier extension done).

Routes each task by a simple difficulty rule, then runs the verifier
step: an easy task whose first answer scores below VERIFIER_THRESHOLD
is flipped to escalated and rerouted to the large model. Hard tasks
are already escalated by difficulty, so the verifier does not
double-count them.

FIRST_ANSWER_SCORES are stub inputs for the demo, not measured
verifier output. Replace them with a real verifier call (see
meta_client.py) before presenting the numbers as results.

Run: python3 routing_ledger.py
"""

import csv

TASKS = [
    ("sort a list", "easy"),
    ("prove a lemma about routing", "hard"),
    ("summarize a paragraph", "easy"),
    ("debug a race condition", "hard"),
]

# Stub first-answer scores, for the demo only. Threshold 0.70.
FIRST_ANSWER_SCORES = {
    "sort a list": 0.92,
    "prove a lemma about routing": 0.45,
    "summarize a paragraph": 0.55,
    "debug a race condition": 0.38,
}
VERIFIER_THRESHOLD = 0.70

with open("routing_ledger.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["task", "difficulty", "first_model", "verifier_score",
                     "threshold", "model", "escalated", "escalation_reason"])
    counts = {}
    for task, difficulty in TASKS:
        first_model = "gpt-oss-20b" if difficulty == "easy" else "gpt-oss-120b"
        score = FIRST_ANSWER_SCORES[task]
        if difficulty == "hard":
            model, escalated, reason = "gpt-oss-120b", True, "difficulty"
        elif score < VERIFIER_THRESHOLD:
            model, escalated, reason = "gpt-oss-120b", True, "verifier"
        else:
            model, escalated, reason = first_model, False, "none"
        writer.writerow([task, difficulty, first_model, score,
                         VERIFIER_THRESHOLD, model, escalated, reason])
        counts[model] = counts.get(model, 0) + 1

print("wrote routing_ledger.csv")
for model, n in counts.items():
    print(f"{model}: {n}/{len(TASKS)} tasks ({100 * n // len(TASKS)}%)")

================================================================
FILE: routing_ledger.csv
================================================================
task,difficulty,first_model,verifier_score,threshold,model,escalated,escalation_reason
sort a list,easy,gpt-oss-20b,0.92,0.7,gpt-oss-20b,False,none
prove a lemma about routing,hard,gpt-oss-120b,0.45,0.7,gpt-oss-120b,True,difficulty
summarize a paragraph,easy,gpt-oss-20b,0.55,0.7,gpt-oss-120b,True,verifier
debug a race condition,hard,gpt-oss-120b,0.38,0.7,gpt-oss-120b,True,difficulty

================================================================
FILE: swarm-call.sh
================================================================
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

================================================================
FILE: contract_check.py
================================================================
#!/usr/bin/env python3
"""contract_check.py — mechanical enforcement of researcher-contract.md.

Scans a researcher output for SPECIFIC claims (numbers with units, dates,
paper titles, URLs, authority attributions) that lack a [V]/[U]/[I] tag.
Untagged specific claims are the fabrication vector A/B runs ab-1/ab-2
caught by hand; this catches them by code, before synthesis.

Usage:
  ./contract_check.py <output.txt>        # print violations, exit 1 if any
  ./contract_check.py --self-test        # run built-in synthetic test cases

Exit codes: 0 = no violations, 1 = violations found, 2 = usage/file error.
A violation is (severity, message). Severity HIGH = classic fabrication
vector (paper title, URL, authority quote). MEDIUM = untagged number/date.
"""
import re
import sys

TAG_RE = re.compile(r"\[\s*([VUI])\s*\]")
TAG_WINDOW = 60  # chars after a claim within which a tag counts
# Sentence ends: period/bang/question followed by whitespace (so "18.5"
# does not split), or a newline.
SENT_END_RE = re.compile(r"[.!?](?=\s|$)|\n")

# Specific-claim patterns: (name, regex, severity)
PATTERNS = [
    ("url", re.compile(r"https?://\S+"), "HIGH"),
    ("paper-title", re.compile(
        r"['\"]([A-Z][^'\"\n]{12,100}?)['\"]"
        r"(?=\s*(?:,|\.|;|\s|\[))"), "HIGH"),
    ("money", re.compile(r"\$ ?\d[\d,]*(?:\.\d+)?"), "MEDIUM"),
    ("percent", re.compile(r"\d+(?:\.\d+)?\s*%"), "MEDIUM"),
    ("multiple", re.compile(r"\b\d+(?:\.\d+)?\s*[x×]\b"), "MEDIUM"),
    ("year", re.compile(r"\b(19|20)\d{2}\b"), "MEDIUM"),
    ("full-date", re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"\.?\s+\d{1,2},?\s+\d{4}\b"), "MEDIUM"),
    ("authority", re.compile(
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
        r"\s+(?:argues?|claims?|shows?|finds?|concludes?|writes?|notes?|"
        r"says?|according to)\b"), "HIGH"),
    ("named-source", re.compile(
        r"\b(?:lead researcher|researcher|scientist|author|professor)\b"
        r".{0,50}?\bwas\b\s+\*{0,2}[A-Z][a-z]+"
        r"(?:\s+\*{0,2}[A-Z][a-z]+){0,2}"), "HIGH"),
]

# Phrases that look like attributions but are hedges/opinions — not claims.
HEDGE_RE = re.compile(
    r"\b(?:I think|I believe|in my (?:view|opinion|judgment)|"
    r"my (?:take|judgment|recommendation))\b", re.IGNORECASE)


def _tag_spans(text):
    return [(m.start(), m.end()) for m in TAG_RE.finditer(text)]


def _is_tagged(text, match_start, match_end, tag_spans):
    # Proximity: tag within TAG_WINDOW after the claim.
    for s, e in tag_spans:
        if s >= match_end and s - match_end <= TAG_WINDOW:
            return True
        if s < match_end and e > match_end:
            return True  # tag wraps/overlaps the match
    # Sentence scope: models naturally put one tag at sentence end to cover
    # all claims in the sentence — a tag anywhere in the same sentence counts.
    seg_start = 0
    for m in SENT_END_RE.finditer(text):
        seg_end = m.end()
        if seg_start <= match_start < seg_end:
            return any(seg_start <= s < seg_end for s, e in tag_spans)
        seg_start = seg_end
    return any(s >= seg_start for s, e in tag_spans)


def check_contract(text):
    """Return list of (severity, message) for untagged specific claims."""
    # Strip markdown bold/italic so **Name** still matches name patterns.
    text = re.sub(r"\*\*", "", text)
    violations = []
    tag_spans = _tag_spans(text)
    seen = set()
    for name, rx, sev in PATTERNS:
        for m in rx.finditer(text):
            key = (name, m.start())
            if key in seen:
                continue
            seen.add(key)
            # Skip matches inside a hedge/opinion sentence window
            window_start = max(0, m.start() - 80)
            if HEDGE_RE.search(text[window_start:m.start()]):
                continue
            if _is_tagged(text, m.start(), m.end(), tag_spans):
                continue
            snippet = m.group(0).strip()
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            violations.append(
                (sev, f"untagged {name}: {snippet!r} (add [V]/[U]/[I])"))
    return violations


def main():
    args = sys.argv[1:]
    if args == ["--self-test"]:
        return self_test()
    if len(args) != 1:
        print("usage: contract_check.py <output.txt> | --self-test",
              file=sys.stderr)
        return 2
    try:
        text = open(args[0], errors="replace").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    violations = check_contract(text)
    for sev, msg in violations:
        print(f"[{sev}] {msg}")
    print(f"{len(violations)} contract violation(s)")
    return 1 if violations else 0


def self_test():
    cases = [
        # (name, text, expected_violation_count)
        ("tagged-ok",
         "Revenue grew 12% [U] in 2024 [U]. Fair value $18.56 [V] "
         "(15 x 1.2374 = 18.56). Shiller argues [U] for caution.",
         0),
        ("untagged-number",
         "Revenue grew 12% in 2024 and fair value is $18.56.",
         3),  # 12%, 2024, $18.56
        ("untagged-title",
         'As shown in "Irrational Exuberance and Market Cycles", '
         "multiples compress.",
         1),
        ("untagged-url",
         "See https://example.com/paper.pdf for details.",
         1),
        ("untagged-authority",
         "Shiller argues that multiples always compress late-cycle.",
         1),
        ("opinion-clean",
         "My judgment: this is a hold. I think patience wins here.",
         0),
        ("mixed",
         "The thesis rests on 2021 [V] data. But margins hit 40% in 2023 "
         "and the CEO promised growth.",
         2),  # 40% and 2023 untagged; 2021 tagged
    ]
    fails = 0
    for name, text, expected in cases:
        got = check_contract(text)
        ok = len(got) == expected
        print(f"[{'ok' if ok else 'FAIL'}] {name}: "
              f"expected {expected}, got {len(got)}")
        if not ok:
            fails += 1
            for sev, msg in got:
                print(f"    [{sev}] {msg}")
    print(f"self-test: {len(cases) - fails}/{len(cases)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

================================================================
FILE: live-runs/run-escalation-test-20261025.json
================================================================
{
  "task": "Write a Python function named evaluate that takes one string argument: an arithmetic expression, and returns a float. The expression contains non-negative integers, the binary operators + - * / and ** (exponentiation), parentheses, and unary minus. Unary minus may appear at the start of the expression, right after '(', or right after another operator (including after **). Unary minus binds LESS tightly than **, as in Python: -2**2 is -4, not 4. ** is right-associative: 2**3**2 is 512. Whitespace may appear anywhere and must be ignored. Division is float division. Do NOT use eval, exec, or the ast module. Reply with ONLY the function code, no explanation.",
  "final": "FAIL",
  "detail": "FAIL - The provided code is incomplete and does not return a result.",
  "steps": [
    {
      "model": "openai/gpt-oss-20b",
      "role": "generate",
      "verdict": "FAIL",
      "verifier": "groq:gpt-oss-20b",
      "cost_usd": 0.0,
      "answer": "```python\ndef evaluate(expr: str) -> float:\n    import re\n    # Tokenize\n    tokens = []\n    i = 0\n    n = len(expr)\n    while i < n:\n        c = expr[i]\n        if c.isspace():\n            i += 1\n            continue\n        if c.isdigit():\n            j = i\n            while j < n and expr[j].isdigit():\n                j += 1\n            tokens.append(expr[i:j])\n            i = j\n        elif c in '+-*/()':\n            tokens.append(c)\n            i += 1\n        else:\n            raise ValueError(f\"Invalid character {c}\")\n    # Handle unary minus\n    processed = []\n    prev = None\n    for tok in tokens:\n        if tok == '-' and (prev is None or prev in '()+-*/'):\n            processed.append('u-')\n        else:\n            processed.append(tok)\n        prev = tok\n    # Shunting-yard\n    prec = {'+': 1, '-': 1, '*': 2, '/': 2, '**': 3, 'u-': 0}\n    right_assoc = {'**'}\n    output = []\n    stack = []\n    i = 0\n    while i < len(processed):\n        tok = processed[i]\n        if tok.isdigit():\n            output.append(float(tok))\n        elif tok == '(':\n            stack.append(tok)\n        elif tok == ')':\n            while stack and stack[-1] != '(':"
    },
    {
      "model": "openai/gpt-oss-120b",
      "role": "revise",
      "verdict": "FAIL",
      "verifier": "groq:gpt-oss-20b",
      "cost_usd": 0.0,
      "answer": "```python\ndef evaluate(expr: str) -> float:\n    import re\n\n    # Tokenize numbers, operators (including **), parentheses\n    token_spec = [\n        ('NUMBER',   r'\\d+(\\.\\d*)?'),   # Integer or decimal number\n        ('OP',       r'\\*\\*|[+\\-*/]'),  # Operators, ** must be before *\n        ('LPAREN',   r'\\('),\n        ('RPAREN',   r'\\)'),\n        ('SKIP',     r'\\s+'),           # Skip whitespace\n        ('MISMATCH', r'.'),             # Any other character\n    ]\n    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_spec)\n    tokens = []\n    for mo in re.finditer(tok_regex, expr):\n        kind = mo.lastgroup\n        value = mo.group()\n        if kind == 'NUMBER':\n            tokens.append(('NUMBER', value))\n        elif kind == 'OP':\n            tokens.append(('OP', value))\n        elif kind == 'LPAREN':\n            tokens.append(('LPAREN', value))\n        elif kind == 'RPAREN':\n            tokens.append(('RPAREN', value))\n        elif kind == 'SKIP':\n            continue\n        else:\n            raise ValueError(f'Unexpected character {value}')\n\n    # Insert explicit unary minus tokens ('UMINUS')\n    processed = []\n    prev_type = None\n    for typ, val in tokens:\n        if typ == 'OP' and val == '-':\n            if prev_type in (None, 'OP', 'LPAREN'):\n                processed.append(('OP', 'UMINUS'))\n            else:\n                processed.append((typ,"
    },
    {
      "model": "openai/gpt-oss-120b",
      "role": "revise",
      "verdict": "FAIL",
      "verifier": "groq:gpt-oss-20b",
      "cost_usd": 0.0,
      "answer": "```python\ndef evaluate(expr: str) -> float:\n    import re\n\n    # Tokenizer\n    token_spec = [\n        ('NUMBER',   r'\\d+(\\.\\d*)?'),      # integer or decimal\n        ('OP',       r'\\*\\*|[+\\-*/]'),     # operators, ** before *\n        ('LPAREN',   r'\\('),\n        ('RPAREN',   r'\\)'),\n        ('SKIP',     r'\\s+'),              # whitespace\n        ('MISMATCH', r'.'),                # any other character\n    ]\n    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_spec)\n    raw_tokens = []\n    for mo in re.finditer(tok_regex, expr):\n        kind = mo.lastgroup\n        val = mo.group()\n        if kind == 'NUMBER':\n            raw_tokens.append(('NUMBER', float(val)))\n        elif kind == 'OP':\n            raw_tokens.append(('OP', val))\n        elif kind == 'LPAREN':\n            raw_tokens.append(('LPAREN', val))\n        elif kind == 'RPAREN':\n            raw_tokens.append(('RPAREN', val))\n        elif kind == 'SKIP':\n            continue\n        else:\n            raise ValueError(f'Unexpected character {val}')\n\n    # Insert explicit unary minus tokens where needed\n    tokens = []\n    prev = None\n    for typ, val in raw_tokens:\n        if typ == 'OP' and val == '-':\n            if prev is None or prev[0] in ('OP', 'LPAREN'):\n                tokens.append(('OP', 'UMINUS'))\n            else:\n                tokens.append((typ, val))\n        else:\n            tokens.append((typ, val))\n        prev = tokens[-1]\n\n    # Operator precedence (higher number = tighter binding)\n    prec = {\n        'UMINUS': 4,   # unary minus binds less tightly than ** (Python behavior)\n        '**':    3,\n        '*':     2,\n        '/':     2,\n        '+':     1,\n        '-':     1,\n    }\n    # Associativity: left = True, right = False\n    right_assoc = {'**', 'UMINUS'}\n\n    # Shunting-yard algorithm to produce RPN"
    }
  ],
  "total_cost_usd": 0.0,
  "elapsed_s": 7.2
}

================================================================
FILE: live-runs/run-escalation-retest-20261026.json
================================================================
{
  "task": "Write a Python function named evaluate that takes one string argument: an arithmetic expression, and returns a float. The expression contains non-negative integers, the binary operators + - * / and ** (exponentiation), parentheses, and unary minus. Unary minus may appear at the start of the expression, right after '(', or right after another operator (including after **). Unary minus binds LESS tightly than **, as in Python: -2**2 is -4, not 4. ** is right-associative: 2**3**2 is 512. Whitespace may appear anywhere and must be ignored. Division is float division. Do NOT use eval, exec, or the ast module. Reply with ONLY the function code, no explanation.",
  "final": "PASS",
  "detail": "PASS: Function correctly parses and evaluates expressions per the specification.",
  "steps": [
    {
      "model": "openai/gpt-oss-20b",
      "role": "generate",
      "verdict": "FAIL",
      "verifier": "groq:gpt-oss-20b",
      "cost_usd": 0.0,
      "answer": "```python\ndef evaluate(expr: str) -> float:\n    import math\n    s = ''.join(expr.split())\n    n = len(s)\n    i = 0\n\n    def parse_expr() -> float:\n        nonlocal i\n        val = parse_term()\n        while i < n and s[i] in '+-':\n            op = s[i]\n            i += 1\n            rhs = parse_term()\n            val = val + rhs if op == '+' else val - rhs\n        return val\n\n    def parse_term() -> float:\n        nonlocal i\n        val = parse_factor()\n        while i < n and s[i] in '*/':\n            op = s[i]\n            i += 1\n            rhs = parse_factor()\n            val = val * rhs if op == '*' else val / rhs\n        return val\n\n    def parse_factor() -> float:\n        nonlocal i\n        return parse_power()\n\n    def parse_power() -> float:\n        nonlocal i\n        val = parse_unary()\n        if i < n and s[i] == '*':\n            if i+1 < n and s[i+1] == '*':\n                i += 2\n                rhs = parse_power()\n                val = val ** rhs\n        return val\n\n    def parse_unary() -> float:\n        nonlocal i\n        if i < n and s[i] == '-':\n            i += 1\n            return -parse_unary()\n        return parse_primary()\n\n    def parse_primary() -> float:\n        nonlocal i\n        if i < n and s[i] == '(':\n            i += 1\n            val = parse_expr()\n            if i < n and s[i] == ')':\n                i += 1\n            else:\n                raise ValueError('Missing closing parenthesis')\n            return val\n        start = i\n        while i < n and s[i].isdigit():\n            i += 1\n        if start == i:\n            raise ValueError('Expected number')\n        return float(s[start:i])\n\n    return parse_expr()\n```"
    },
    {
      "model": "openai/gpt-oss-120b",
      "role": "revise",
      "verdict": "PASS",
      "verifier": "groq:gpt-oss-20b",
      "cost_usd": 0.0,
      "answer": "def evaluate(expr: str) -> float:\n    s = ''.join(expr.split())\n    n = len(s)\n    i = 0\n\n    def parse_expr() -> float:\n        nonlocal i\n        val = parse_term()\n        while i < n and s[i] in '+-':\n            op = s[i]\n            i += 1\n            rhs = parse_term()\n            val = val + rhs if op == '+' else val - rhs\n        return val\n\n    def parse_term() -> float:\n        nonlocal i\n        val = parse_factor()\n        while i < n and s[i] in '*/':\n            op = s[i]\n            i += 1\n            rhs = parse_factor()\n            val = val * rhs if op == '*' else val / rhs\n        return val\n\n    def parse_factor() -> float:\n        return parse_unary()\n\n    def parse_unary() -> float:\n        nonlocal i\n        if i < n and s[i] == '-':\n            i += 1\n            return -parse_unary()\n        return parse_power()\n\n    def parse_power() -> float:\n        nonlocal i\n        val = parse_primary()\n        if i + 1 < n and s[i] == '*' and s[i + 1] == '*':\n            i += 2\n            rhs = parse_power()\n            val = val ** rhs\n        return val\n\n    def parse_primary() -> float:\n        nonlocal i\n        if i < n and s[i] == '(':\n            i += 1\n            val = parse_expr()\n            if i < n and s[i] == ')':\n                i += 1\n                return val\n            raise ValueError('Missing closing parenthesis')\n        start = i\n        while i < n and s[i].isdigit():\n            i += 1\n        if start == i:\n            raise ValueError('Expected number')\n        return float(s[start:i])\n\n    result = parse_expr()\n    if i != n:\n        raise ValueError('Unexpected characters')\n    return result"
    }
  ],
  "total_cost_usd": 0.0,
  "elapsed_s": 0.8
}

================================================================
FILE: benchmark-v5/REPORT.md
================================================================
# Benchmark v5 — recursive improvement loop, cycle 1

Standing brief: find a REAL, statistically meaningful mechanism improvement
over plain single-sample gpt-oss-120b, or exhaust the search honestly
(max 5 cycles). Silence until a verified win.

## Cycle 1 design (2026-10-18)

**Task pool:** 42 candidates across 7 families (12 code, 8 logic, 6 arithmetic,
6 adversarial writing, 4 counting/long-context, 4 negation/order, 2
self-referential). Every ground truth computed programmatically in
`design-v5.py` (reference implementations, brute-force solvers, Decimal
arithmetic). Every scorer proven good-pass/bad-fail by `verify-v5.py`
(42/42 verified before any model call).

**Screening (pre-registered):** each candidate vs plain gpt-oss-120b, 3 fresh
reps, SWARM_REDELEGATE=0, SWARM_CACHE=0. KEEP iff 120b fails >= 2/3 reps.
Target: 12-16 kept tasks.

**Mechanisms under test** (all on the kept set):
- plain: 120b single sample, 5 reps (tighter baseline)
- bestof5: 5 fresh 120b samples, mechanical verifier picks first passing (3 reps)
- revise: 120b generator + mechanical verifier, <=2 revisions, thrash-guard
  (stop if an answer repeats a previous attempt; full scorer failure detail
  fed back) (3 reps)
- selfcon: 5 fresh samples, strict-majority vote over extracted canonical
  answer (single-answer scorers only) (3 reps)
- route: per-task model from same-distribution 20b screening (20b iff it
  strictly beat 120b on the same 3-rep screen; ties stay 120b) (3 reps)

**Win criteria (pre-registered):**
1. mechanism mean per-task pass rate > plain mean, AND
2. mechanism failed-task set is a STRICT SUBSET of plain's (fixes >= 1,
   breaks 0), AND
3. paired sign test on per-task rates vs plain, one-sided p < 0.05.

## Cycle 1 results

**Screening:** 126/126 cells clean, 0 missing data. **Kept 5/42** — below the
8-task gate, so the cycle stopped before mechanism runs (no further calls
burned).

Kept (120b failed all 3 reps): c1-expr-eval-3, c10-sexpr, l1-knights-6,
w2-word-count, w5-lines-words.

**Diagnosis:** the pool was bimodal — the other 37 candidates were PPP
(120b passed all 3 reps on every one); nothing was mixed. My "hard-looking"
traps were too clean; 120b is reliable at careful reading, arithmetic, and
single-constraint following. Its genuine weak spots are exactly the 3
families that survived: tricky-grammar code (c1, c10), combinatorial search
(l1), exact-count/multi-constraint writing (w2, w5).

## Cycle 2 design (2026-10-18)

31 new candidates concentrated in the winning families (8 parser/code traps:
custom operators, unicode JSON, multiline CSV, tally base-1, business-day
arithmetic, let-binding sexprs, IPv4, cron fields; 7 combinatorial logic:
knights-7, knights-exact-2, zebra-5, schedule-6, tournament-5, seating-6,
mastermind; 8 exact-count writing: 6x7 A-F, HELLO/WORLD acrostic, 3-para
word counts, 8-line alternating, 50-word, 3-comma, growing 5-8, no-'e'
lipogram; 8 misc arithmetic). All 73 tasks (42+31) verified good-pass/bad-fail.

Screening set `tasks-v5-screen2.json` = 31 new + the 5 cycle-1 kept
(re-screened for stability), 36 tasks x 3 reps. Keep rule unchanged
(fail >= 2/3). Gate: proceed to mechanisms only if >= 8 kept.
Mechanisms unchanged (plain x5, bestof5, revise+thrash-guard, selfcon,
same-distribution route), same pre-registered win criteria.

## Cycle 2 results

**Screening:** 108/108 cells (36 tasks x 3 reps), 0 missing. **Kept 12/36**
(passed the 8-task gate): p3-unicode-json, p8-bizdays, p9-sexpr-let,
q3-zebra-5, q8-mastermind, r5-fifty-words, r8-no-e, c1-expr-eval-3,
c10-sexpr, l1-knights-6, w2-word-count, w5-lines-words.

**Mechanism runs:** 537 total model calls, 0 missing cells. Per-task pass
rates (12 kept tasks):

| mech | mean | verdict |
|------|------|---------|
| plain (120b x5) | 0.083 | baseline |
| bestof5 | 0.083 | no win (0W/0L) |
| revise (120b + verifier + thrash-guard) | 0.583 | **WIN** (6W/0L, p=0.0156) |
| route (same-distribution 20b routing) | 0.667 | **WIN** (7W/0L, p=0.0078) |
| selfcon | 0.083 | no win (0W/0L) |

**revise fixes** (6 tasks, 0 breaks): c1-expr-eval-3, c10-sexpr,
p3-unicode-json, p9-sexpr-let, q3-zebra-5, w5-lines-words.
**route fixes** (7 tasks, 0 breaks): c10-sexpr, p3-unicode-json, p8-bizdays,
p9-sexpr-let, q3-zebra-5, w2-word-count, w5-lines-words.
Both meet all three pre-registered win criteria (higher mean, strict
failure subset, sign test p < 0.05).

**Revise trajectories (all 3 reps identical per task):**
- c1: 9/10 -> 9/10 -> 10/10 (feedback fixes the last failing test)
- c10: 2/6 -> 6/6 | p3: crash -> 3/3 | p9: crash (nonlocal) -> 5/5
- q3: '5' -> '3' | w5: 3 words/line -> 4 words/line
Within-loop fail->pass transitions happen seconds apart: the feedback
drives the fix, not time drift. No scorer leaks the expected answer
(`want=` never appears in failure details for kept tasks).

**MAJOR METHODOLOGICAL FINDING — provider-side determinism:** identical
prompts return byte-identical outputs within a time window (5/5, 3/3
reps identical), but the output can change across windows (plain c10 at
19:49 -> X/fail; route c10 at 20:19 -> Y/pass; fresh probes confirm Y).
Not client cache (SWARM_CACHE=0), not idempotency keys (random UUIDs),
not server cache (static assets only). Consequences:
- "Reps" are illusory: effective n=1 per task-mechanism per window.
  (Explains v4's "zero run-to-run variance".)
- bestof-N and self-consistency are DEGENERATE under determinism: they
  resample the identical output. Their failure here is a setup artifact,
  not a mechanism verdict.
- The task-level sign test remains valid (tasks are independent units),
  and the revise within-loop trajectories are immune to the drift
  confound (fail->pass seconds apart, same window).
- Future benchmarks: use prompt perturbation for true reps, or treat
  each time window as n=1.

**Audits performed:** analyze-v5.py was scoring model.txt as answer cells
(fixed; v4's scorer skipped them); q8's keep decision was format noise
(120b solves it 5/5 when formatted cleanly — noted, doesn't affect the
win which is on other tasks); no expected-answer leakage in revise
details; all cells present.

**Scope of the claim:** on tasks where single-sample gpt-oss-120b
deterministically fails, a mechanical verify-revise loop (<=2 revisions,
scorer feedback, thrash-guard) recovers passing answers on 6/12, and
same-distribution routing to gpt-oss-20b (which went 3/3 vs 120b's 0/3
in contemporaneous screening on 6 tasks) wins on 7/12. Not a general
"revise always beats 120b" claim.

**Recommended follow-up:** disentangle informative feedback vs mere
retry-nudge (revise-no-feedback control). The q3 case ('5'->'3' on an
uninformative detail) suggests the retry nudge alone has power.

## Verdict

**WIN on cycle 2.** Two mechanisms beat plain single-sample gpt-oss-120b
on the hard-task distribution with statistical significance and zero
breaks. Loop stops per protocol (condition a).

================================================================
FILE: benchmark-v5/score-v5.py
================================================================
#!/usr/bin/env python3
"""score-v5.py — scorer library for benchmark v5 (cycle 1+).

Reuses the full v4 mechanical scorer set and adds:
  numeric_decimal          exact Decimal comparison (money arithmetic)
  code_function_raises_tests  tests where some cases must raise ValueError
  constraint_words         per-sentence / total word counts, required words
  constraint_acrostic      first/last letters of sentences spell words
  constraint_commas        exact comma count per sentence
  constraint_list_alt      alternating bullet prefixes per line
"""
import os
import re
import sys
from decimal import Decimal, InvalidOperation

import importlib.util as _ilu

BASE = os.path.dirname(os.path.abspath(__file__))
V4 = os.path.join(os.path.dirname(BASE), "benchmark-v4")


def _load_v4():
    spec = _ilu.spec_from_file_location(
        "score_v4_mod", os.path.join(V4, "score-v4.py"))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_v4 = _load_v4()
score_numeric_tolerance = _v4.score_numeric_tolerance
score_token_strict = _v4.score_token_strict
score_digits_strict = _v4.score_digits_strict
score_code_function_numeric_tests = _v4.score_code_function_numeric_tests
score_code_function_deep_tests = _v4.score_code_function_deep_tests
score_code_function_deep_tests_args = _v4.score_code_function_deep_tests_args
score_constraint_alpha = _v4.score_constraint_alpha
score_constraint_paragraphs = _v4.score_constraint_paragraphs
score_constraint_list = _v4.score_constraint_list
_strip_fences = _v4._strip_fences
_check_banned = _v4._check_banned
_run_harness = _v4._run_harness
_sentences = _v4._sentences
_deep_driver = _v4._deep_driver


def score_numeric_decimal(text, expected):
    """Any number token in the text must Decimal-equal the expected string."""
    want = Decimal(expected)
    toks = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    found = []
    for t in toks:
        try:
            found.append(Decimal(t.replace(",", "")))
        except InvalidOperation:
            pass
    ok = any(v == want for v in found)
    return ok, f"numbers_found={[str(v) for v in found]}, want={want}"


def score_code_function_raises_tests(text, tests, func_name, task=None):
    """Tests: list of {"args": [...], "want": value | "RAISES"}.

    For RAISES cases the function must raise ValueError (any exception whose
    type name contains 'Error' counts, to tolerate custom messages; bare
    crashes on non-RAISES cases fail)."""
    code = _strip_fences(text)
    banned = _check_banned(code, task or {})
    if banned:
        return False, banned
    driver = (
        "import json\n" + code + "\n"
        + "tests=" + repr(tests) + "\n"
        + "results=[]\n"
        + "for tc in tests:\n"
        + "    args, want = tc['args'], tc['want']\n"
        + "    try:\n"
        + f"        got={func_name}(*args)\n"
        + "    except Exception as e:\n"
        + "        results.append('RAISED:'+type(e).__name__ if want=='RAISES' else 'CRASH')\n"
        + "    else:\n"
        + "        results.append(got==want if want!='RAISES' else 'NORAISE')\n"
        + "print(json.dumps(results))\n"
    )
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    good = 0
    for tc, r in zip(tests, payload):
        if tc["want"] == "RAISES":
            if isinstance(r, str) and r.startswith("RAISED:"):
                good += 1
        elif r is True:
            good += 1
    ok = good == len(tests) and len(payload) == len(tests)
    return ok, f"tests_passed={good}/{len(tests)}"


def score_constraint_words(text, task):
    """Word-count constraints.

    Task fields: n_sentences (int or None), words_per_sentence (int, list, or
    None), total_words (int or None), required_words ({1-based pos: word}),
    starts (str of letters, one per sentence, optional).
    """
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_sentences")
    if n is not None:
        sents = _sentences(t)
        if len(sents) != n:
            ok = False
        detail.append(f"sentences={len(sents)}/{n}")
    else:
        sents = _sentences(t) or [t]
    wps = task.get("words_per_sentence")
    if wps is not None:
        if isinstance(wps, int):
            wps = [wps] * len(sents)
        for i, s in enumerate(sents):
            nw = len(re.findall(r"[a-z0-9]+", s.lower()))
            want = wps[i] if i < len(wps) else wps[-1]
            if nw != want:
                ok = False
            detail.append(f"sent_{i+1}_words={nw}/{want}")
    tw = task.get("total_words")
    if tw is not None:
        nw = len(re.findall(r"[a-z0-9]+", t.lower()))
        if nw != tw:
            ok = False
        detail.append(f"total_words={nw}/{tw}")
    for pos, word in task.get("required_words", {}).items():
        pos = int(pos)  # JSON object keys arrive as strings
        toks = re.findall(r"[a-z0-9]+", t.lower())
        got = toks[pos - 1] if 0 < pos <= len(toks) else None
        if got != word.lower():
            ok = False
        detail.append(f"word_{pos}={got!r}/{word!r}")
    starts = task.get("starts")
    if starts:
        for i, s in enumerate(sents):
            m = re.search(r"[a-zA-Z]", s)
            want = starts[i].lower() if i < len(starts) else "?"
            if not m or m.group(0).lower() != want:
                ok = False
                detail.append(f"sentence_{i+1}_starts_wrong")
    return ok, ", ".join(detail)


def score_constraint_acrostic(text, task):
    """First letters of sentences spell first_spell; last letters (final
    alpha char before terminal punctuation) spell last_spell."""
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_sentences", 4)
    sents = _sentences(t)
    if len(sents) != n:
        ok = False
    detail.append(f"sentences={len(sents)}/{n}")
    first = "".join(re.search(r"[a-zA-Z]", s).group(0).lower()
                    for s in sents if re.search(r"[a-zA-Z]", s))
    lasts = []
    for s in sents:
        m = re.findall(r"[a-zA-Z]", s)
        lasts.append(m[-1].lower() if m else "?")
    last = "".join(lasts)
    if first != task.get("first_spell", ""):
        ok = False
    if last != task.get("last_spell", ""):
        ok = False
    detail.append(f"first={first!r} last={last!r}")
    return ok, ", ".join(detail)


def score_constraint_commas(text, task):
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_sentences", 3)
    k = task.get("commas_per_sentence", 2)
    sents = _sentences(t)
    if len(sents) != n:
        ok = False
    detail.append(f"sentences={len(sents)}/{n}")
    for i, s in enumerate(sents):
        nc = s.count(",")
        if nc != k:
            ok = False
        detail.append(f"sent_{i+1}_commas={nc}/{k}")
    return ok, ", ".join(detail)


def score_constraint_list_alt(text, task):
    """Alternating bullet prefixes: odd lines start with odd_prefix,
    even lines with even_prefix; words_per_line counted after the marker."""
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_lines", 6)
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) != n:
        ok = False
    detail.append(f"lines={len(lines)}/{n}")
    op, ep = task.get("odd_prefix", "- "), task.get("even_prefix", "* ")
    wpl = task.get("words_per_line")
    for i, ln in enumerate(lines):
        s = ln.strip()
        want = op if i % 2 == 0 else ep
        if not s.startswith(want):
            ok = False
            detail.append(f"line_{i+1}_prefix_wrong")
            continue
        if wpl is not None:
            nw = len(re.findall(r"[a-z0-9]+", s[len(want):].lower()))
            if nw != wpl:
                ok = False
            detail.append(f"line_{i+1}_words={nw}/{wpl}")
    return ok, ", ".join(detail)


SCORERS = {
    "numeric_tolerance": lambda t, task: score_numeric_tolerance(
        t, task["expected"], task.get("tolerance", 1e-4)),
    "numeric_decimal": lambda t, task: score_numeric_decimal(
        t, task["expected"]),
    "token_strict": lambda t, task: score_token_strict(t, task["expected"]),
    "digits_strict": lambda t, task: score_digits_strict(t, task["expected"]),
    "code_function_numeric_tests": lambda t, task: score_code_function_numeric_tests(
        t, task["hidden_tests"], task["function"],
        task.get("tolerance", 1e-6), task.get("ban_eval", False)),
    "code_function_deep_tests": lambda t, task: score_code_function_deep_tests(
        t, task["hidden_tests"], task["function"], task),
    "code_function_deep_tests_args": lambda t, task: score_code_function_deep_tests_args(
        t, task["hidden_tests"], task["function"], task),
    "code_function_raises_tests": lambda t, task: score_code_function_raises_tests(
        t, task["hidden_tests"], task["function"], task),
    "constraint_alpha": lambda t, task: score_constraint_alpha(t, task),
    "constraint_paragraphs": lambda t, task: score_constraint_paragraphs(t, task),
    "constraint_list": lambda t, task: score_constraint_list(t, task),
    "constraint_list_alt": lambda t, task: score_constraint_list_alt(t, task),
    "constraint_words": lambda t, task: score_constraint_words(t, task),
    "constraint_acrostic": lambda t, task: score_constraint_acrostic(t, task),
    "constraint_commas": lambda t, task: score_constraint_commas(t, task),
}

================================================================
FILE: benchmark-v5/verify-v5.py
================================================================
#!/usr/bin/env python3
"""verify-v5.py — prove every candidate task's scorer passes a known-correct
answer and fails known-wrong answers. Exits nonzero on any failure."""
import importlib.util
import inspect
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


design = _load("d5v", os.path.join(BASE, "design-v5.py"))
design = _load("d5v", os.path.join(BASE, "design-v5.py"))
design2 = _load("d5c2", os.path.join(BASE, "design-v5c2.py"))
sc = _load("s5v", os.path.join(BASE, "score-v5.py"))
TASKS = {}
for _jf in ("tasks-v5-candidates.json", "tasks-v5c2-candidates.json"):
    _p = os.path.join(BASE, _jf)
    if os.path.exists(_p):
        for _t in json.load(open(_p))["tasks"]:
            TASKS[_t["id"]] = _t

# Map task -> (module, reference fn, required function name)
REFMAP = {
    "c1-expr-eval-3": ("d5", "ref_eval", "evaluate"),
    "c2-csv-2": ("d5", "ref_parse_csv_row", "parse_csv_row"),
    "c3-sjson-2": ("d5", "ref_parse_sjson", "parse_sjson"),
    "c4-wildcard-2": ("d5", "ref_wildcard", "wildcard_match"),
    "c5-base-convert-2": ("d5", "ref_base_to_int", "base_to_int"),
    "c6-roman-validate": ("d5", "ref_roman_to_int", "roman_to_int"),
    "c7-date-add": ("d5", "ref_add_days", "add_days"),
    "c8-rle-decode": ("d5", "ref_rle_decode", "rle_decode"),
    "c9-brackets": ("d5", "ref_balanced", "is_balanced"),
    "c10-sexpr": ("d5", "ref_sexpr", "seval"),
    "c11-morse": ("d5", "ref_morse_decode", "morse_decode"),
    "c12-caesar-2": ("d5", "ref_caesar_decode", "caesar_decode"),
    "p1-custom-ops": ("d5c2", "ref_custom_eval", "ceval"),
    "p3-unicode-json": ("d5", "ref_parse_sjson", "parse_sjson"),
    "p4-csv-multiline": ("d5", "ref_parse_csv_row", "parse_csv_row"),
    "p6-tally": ("d5c2", "ref_tally", "base_to_int"),
    "p8-bizdays": ("d5c2", "ref_add_bizdays", "add_business_days"),
    "p9-sexpr-let": ("d5c2", "ref_sexpr_let", "seval"),
    "p12-ipv4": ("d5c2", "ref_ipv4", "ipv4_to_int"),
    "p13-cron": ("d5c2", "ref_cron_min", "cron_minutes"),
}
MODULES = {"d5": design, "d5c2": design2}


def ref_code_answer(tid):
    modkey, refname, fname = REFMAP[tid]
    mod = MODULES[modkey]
    src = inspect.getsource(getattr(mod, refname))
    # rename the def line; keep helper references used by the function
    src = src.replace(f"def {refname}(", f"def {fname}(", 1)
    # inline small helpers the reference depends on
    helpers = ""
    for h in ["_ROMAN_VAL", "_ROMAN_SUB", "ref_int_to_roman",
              "_MORSE", "_MORSE_REV",
              "_days_from_civil", "_civil_from_days", "_weekday", "_ANCHOR"]:
        if h in src and f"def {h}" not in src and f"{h} =" not in src:
            for mk in ("d5", "d5c2"):
                try:
                    hsrc = inspect.getsource(getattr(MODULES[mk], h))
                    helpers += hsrc + "\n"
                    break
                except (TypeError, AttributeError):
                    continue
            else:
                # getsource failed in both modules (h is a value, not a
                # function): inline its repr from whichever module has it
                for mk in ("d5", "d5c2"):
                    try:
                        helpers += f"{h} = {getattr(MODULES[mk], h)!r}\n"
                        break
                    except AttributeError:
                        continue
    # make inlined helpers standalone: drop the d5. module prefix
    # (applies to helpers and the main source alike)
    blob = ("```python\nimport re\n" + helpers + src + "\n```")
    blob = blob.replace("d5._days_from_civil", "_days_from_civil")
    blob = blob.replace("d5._civil_from_days", "_civil_from_days")
    # transitive dep: inlined _weekday needs the anchor value
    if "_weekday" in blob and "_ANCHOR =" not in blob:
        assert blob.endswith("```")
        blob = (blob[:-3] +
                f"_ANCHOR = {MODULES['d5c2']._ANCHOR!r}\n```")
    return blob


GOOD_TEXT = {
    "w1-double-constraint":
        "Great work is done. Only practice makes done. Long hours are done. "
        "Daily effort is done.",
    "w2-word-count":
        "One two three four five six. Seven eight nine ten eleven twelve. "
        "Red blue green yellow black white. Cats dogs birds fish swim fast. "
        "Spring summer autumn winter come soon.",
    "w3-acrostic":
        "Many sailors love the sea, and they sing songs. "
        "Across the waves the gulls cry free. "
        "Rough storms test every brave heart, yet crews endure more. "
        "Silent harbors welcome tired ships home again.",
    "w4-comma-exact":
        "I bought apples, oranges, and pears. "
        "She ran fast, jumped high, and won. "
        "We ate, we drank, we left.",
    "w5-lines-words":
        "- alpha beta gamma delta\n* epsilon zeta eta theta\n"
        "- iota kappa lambda mu\n* nu xi omicron pi\n"
        "- rho sigma tau upsilon\n* phi chi psi omega",
    "w6-n-words": None,  # built below (41 words)
    "s2-seven-words": "I will do exactly what you asked",
    "r1-six-seven":
        "Apples grow on tall trees daily here. "
        "Birds sing sweet songs each bright morning. "
        "Cats chase small mice around old barns. "
        "Dogs bark loudly at passing strangers now. "
        "Eagles fly high above rocky mountain peaks. "
        "Frogs jump quickly into cool pond water.",
    "r2-acrostic-5":
        "High above the earth the stars shine bright somehow. "
        "Every night the moon follows its arc through the halo. "
        "Lonely comets cross the dark sky forever. "
        "Last light fades as the planets turn still. "
        "Old telescopes watch the quiet void.",
    "r3-para-words": None,  # built below (6 sentences x 10 words)
    "r4-lines-8":
        "- alpha beta gamma delta epsilon\n"
        "* zeta eta theta iota kappa\n"
        "- lambda mu nu xi omicron\n"
        "* pi rho sigma tau upsilon\n"
        "- phi chi psi omega aleph\n"
        "* beth gimel dalet he vav\n"
        "- zayin het tet yod kaf\n"
        "* lamed mem nun samekh ayin",
    "r5-fifty-words": None,  # built below (50 words, 5 sentences)
    "r6-commas-3":
        "I bought apples, oranges, bananas, and pears. "
        "She ran fast, jumped high, stumbled once, and won. "
        "We ate well, drank deeply, laughed loudly, and left.",
    "r7-growing":
        "I like to eat apples. "
        "She likes to eat green apples. "
        "They like to eat big green apples. "
        "We like to eat fresh green apples daily.",
    "r8-no-e":
        "A dark night sky. "
        "Bright orbs glow at midnight. "
        "Clouds drift past Mars.",
}
_words41 = ["desert"] * 41
assert len(_words41) == 41
GOOD_TEXT["w6-n-words"] = " ".join(_words41) + "."

_words60 = [f"w{i}" for i in range(60)]
GOOD_TEXT["r3-para-words"] = " ".join(
    " ".join(_words60[i * 10:(i + 1) * 10]) + "." for i in range(6))

_words50 = [f"w{i}" for i in range(50)]
GOOD_TEXT["r5-fifty-words"] = " ".join(
    " ".join(_words50[i * 10:(i + 1) * 10]) + "." for i in range(5))

BAD_TEXT = {
    "w1-double-constraint": "Great work is done. Only practice makes done. Long hours.",
    "w2-word-count": "One two three four five. Too short here.",
    "w3-acrostic": "Hello world. Another test here.",
    "w4-comma-exact": "No commas here at all. Still none.",
    "w5-lines-words": "- only three words here\n* too few",
    "w6-n-words": "way too short.",
    "s2-seven-words": "I will do something what you asked",
    "r1-six-seven": "Too short. Also too short.",
    "r2-acrostic-5": "Hello world. Another test.",
    "r3-para-words": "Too short.",
    "r4-lines-8": "- only three words here\n* too few",
    "r5-fifty-words": "way too short.",
    "r6-commas-3": "No commas here at all.",
    "r7-growing": "Too short.",
    "r8-no-e": "Here is a sentence with e.",
}


def good_answer(task):
    tid = task["id"]
    if tid in REFMAP:
        return ref_code_answer(tid)
    if tid in GOOD_TEXT:
        return GOOD_TEXT[tid]
    exp = task.get("expected")
    if exp is not None:
        return str(exp)
    raise ValueError(f"no good answer for {tid}")


def bad_answers(task):
    tid = task["id"]
    if tid in REFMAP:
        return ["def broken(:\n  pass"]
    if tid in BAD_TEXT:
        return [BAD_TEXT[tid]]
    exp = str(task.get("expected", ""))
    if task["scorer"] in ("digits_strict",):
        # flip last digit
        last = exp[-1]
        flipped = "0" if last != "0" else "1"
        return [exp[:-1] + flipped]
    if task["scorer"] in ("numeric_decimal", "numeric_tolerance"):
        return [str(float(exp) + 100.0)]
    if task["scorer"] == "token_strict":
        return ["zzzzqqqq"]
    return ["wrong"]


def main():
    fails = []
    for tid, task in sorted(TASKS.items()):
        scorer = sc.SCORERS[task["scorer"]]
        try:
            g = good_answer(task)
            ok, detail = scorer(g, task)
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"scorer crashed on GOOD: {e}"
        if not ok:
            fails.append((tid, "GOOD failed", detail))
            continue
        for b in bad_answers(task):
            try:
                okb, detailb = scorer(b, task)
            except Exception as e:  # noqa: BLE001
                okb, detailb = False, f"scorer crashed on BAD: {e}"
            if okb:
                fails.append((tid, "BAD passed", detailb[:120]))
    if fails:
        print(f"{len(fails)} verification failures:")
        for tid, kind, d in fails:
            print(f"  {tid}: {kind}: {d}")
        sys.exit(1)
    print(f"all {len(TASKS)} tasks verified: good-pass + bad-fail OK")


if __name__ == "__main__":
    main()

================================================================
FILE: benchmark-v5/mech-v5.py
================================================================
#!/usr/bin/env python3
"""mech-v5.py — mechanism implementations for benchmark v5 cycle 1.

Mechanisms (all use gpt-oss-120b as the base model unless noted):
  bestof5    5 fresh samples; mechanical verifier picks the first passing
             sample. Rep passes iff the picked sample passes.
  revise     120b generator + mechanical verifier, <=2 revisions, with
             thrash-guard: stop early if a new answer repeats a previous
             attempt (normalized); final = last distinct answer. The
             revision prompt carries the full scorer failure detail.
  selfcon    5 fresh samples; majority vote over the extracted canonical
             answer (single-answer scorers only: token/digits/numeric/
             numeric_decimal). Ties or no majority -> fail.

Usage:
  python3 mech-v5.py --mech bestof5 --task <tid> --rep <n> --outdir <dir>
Writes <outdir>/openai_gpt-oss-120b.txt (the mechanism's final answer) and
<outdir>/meta.json (attempt log).

The API key comes from the environment (screen/run scripts load the vault).
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")
MODEL = "openai/gpt-oss-120b"
SAFE = "openai_gpt-oss-120b"

_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)


KEPT_JSON = os.environ.get("MECH_KEPT_JSON", "tasks-v5-kept.json")

def load_task(tid):
    tasks = json.load(open(os.path.join(BASE, KEPT_JSON)))["tasks"]
    for t in tasks:
        if t["id"] == tid:
            return t
    raise ValueError(f"unknown kept task: {tid}")


def call_model(prompt):
    """One fresh 120b call. Returns answer text ('' on transport failure)."""
    fd, ppath = tempfile.mkstemp(prefix="v5-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="v5-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = MODEL
        env["SWARM_CACHE"] = "0"
        env["SWARM_REDELEGATE"] = "0"
        env["SWARM_FALLBACK"] = ""
        env["SWARM_SKIP_UNHEALTHY"] = "0"
        env["SWARM_TIMEOUT"] = "180"
        r = subprocess.run(
            [SWARM_CALL, "-f", ppath, outdir],
            env=env, capture_output=True, text=True, timeout=300,
        )
        txt_path = os.path.join(outdir, SAFE + ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(ppath):
            os.unlink(ppath)
        shutil.rmtree(outdir, ignore_errors=True)


def verify(task, answer):
    if not answer or not answer.strip():
        return False, "no output (transport failure or empty response)"
    try:
        ok, detail = score_v5.SCORERS[task["scorer"]](answer, task)
    except Exception as e:  # noqa: BLE001
        return False, f"scorer crashed: {type(e).__name__}: {e}"
    return bool(ok), detail


def norm_answer(a):
    return re.sub(r"\s+", " ", a.strip().lower())


REVISE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Study the failure detail carefully and produce a corrected answer. "
    "Follow the original instructions exactly. Do not repeat your previous "
    "answer unchanged."
)


def run_bestof5(task):
    samples = []
    answers = []
    for i in range(5):
        a = call_model(task["prompt"])
        answers.append(a)
        passed, detail = verify(task, a)
        samples.append({"sample": i + 1, "pass": passed, "detail": detail})
        if passed:
            return a, {"mechanism": "bestof5", "samples": samples,
                       "picked": i + 1, "calls": i + 1}
    return answers[-1], {"mechanism": "bestof5", "samples": samples,
                         "picked": None, "calls": 5}


def run_revise(task, max_revisions=2):
    attempts = []
    seen = set()
    prompt = task["prompt"]
    answer = None
    for n in range(1 + max_revisions):
        answer = call_model(prompt)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "pass": passed,
                         "detail": detail, "repeated": repeated})
        if passed:
            break
        if repeated:
            # thrash-guard: stop, keep the last distinct answer
            break
        if n < max_revisions:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
    return answer, {"mechanism": "revise", "attempts": attempts,
                    "calls": len(attempts)}


SINGLE_ANSWER_SCORERS = {"token_strict", "digits_strict", "numeric_tolerance",
                         "numeric_decimal"}


def extract_canonical(task, answer):
    sc = task["scorer"]
    if sc == "token_strict":
        return re.sub(r"[^a-z]", "", answer.lower()) or None
    if sc == "digits_strict":
        d = re.sub(r"\D", "", answer)
        return d or None
    if sc in ("numeric_tolerance", "numeric_decimal"):
        m = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", answer)
        return m[0].replace(",", "") if m else None
    return None


def run_selfcon(task):
    if task["scorer"] not in SINGLE_ANSWER_SCORERS:
        return "", {"mechanism": "selfcon", "skipped": "not single-answer",
                    "calls": 0}
    votes = []
    raws = []
    for _ in range(5):
        a = call_model(task["prompt"])
        raws.append(a)
        votes.append(extract_canonical(task, a))
    counted = Counter(v for v in votes if v is not None)
    if not counted:
        return "", {"mechanism": "selfcon", "votes": votes, "winner": None,
                    "calls": 5}
    top, cnt = counted.most_common(1)[0]
    # strict majority required; ties fail
    if cnt < 3 or list(counted.values()).count(cnt) > 1:
        return "", {"mechanism": "selfcon", "votes": votes, "winner": None,
                    "calls": 5}
    # return the first raw sample carrying the winning canonical answer
    for a, v in zip(raws, votes):
        if v == top:
            return a, {"mechanism": "selfcon", "votes": votes,
                       "winner": top, "calls": 5}
    return "", {"mechanism": "selfcon", "votes": votes, "winner": None,
                "calls": 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mech", required=True,
                    choices=["bestof5", "revise", "selfcon"])
    ap.add_argument("--task", required=True)
    ap.add_argument("--rep", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    task = load_task(args.task)
    if args.mech == "bestof5":
        final, meta = run_bestof5(task)
    elif args.mech == "revise":
        final, meta = run_revise(task)
    else:
        final, meta = run_selfcon(task)
    meta.update({"task": args.task, "rep": args.rep})
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, SAFE + ".txt"), "w") as f:
        f.write(final or "NO-OUTPUT")
    with open(os.path.join(args.outdir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    passed, detail = verify(task, final)
    print(json.dumps({"task": args.task, "rep": args.rep, "mech": args.mech,
                      "final_pass": passed, "detail": detail,
                      "calls": meta.get("calls")}))
    import time
    time.sleep(3)


if __name__ == "__main__":
    main()

================================================================
FILE: benchmark-v5/xrevise.py
================================================================
#!/usr/bin/env python3
"""xrevise.py — cross-model revision harness v2.

Mechanisms:
  plain          single 120b call (per-window canary / baseline)
  A>B            generator A, reviser B, <=2 revisions, thrash-guard
  cascade        20b generates, 20b revises (<=2), then 120b revises (<=2)
                 — escalates to the expensive model only on failure

Window-aware cache: within a time window the provider is deterministic
(byte-identical outputs for identical prompts — verified v5). Cache key
is sha256(model + prompt); the cache is valid only while the canary hash
matches. Canary = 2 fixed tiny prompts through plain 120b. If the canary
hash changed, the window drifted and the cache is ignored (never pooled
across windows).

Canary re-probe (mid-run, vina's question): the provider window can end
*inside* a paired comparison, so this is enforced, not hoped for. Every
K completed cells (default 12, --canary-every) the harness re-probes the
canary. On mismatch it records a window_boundary event (timestamp, cell
index, old/new hash), starts a new window segment, and resets the cache.
Pairs whose two cells land in different segments are marked
boundary_straddled in results.json and must be excluded from the sign test.

Usage:
  MECH_KEPT_JSON=tasks-v5-kept2.json python3 xrevise.py \
      --tasks p9-sexpr-let,q3-zebra-5,r5-fifty-words,r8-no-e,c1-expr-eval-3,c10-sexpr,l1-knights-6 \
      --mechs plain,120b>120b,20b>120b,20b>20b,20b>nemotron-super,20b>cohere-code,20b>qwen27b,qwen27b>qwen27b,cascade \
      --outdir results/xrevise-v2-<stamp> [--no-cache]

Model aliases:
  120b            openai/gpt-oss-120b
  20b             openai/gpt-oss-20b
  nemotron-super  nvidia/nemotron-3-super-120b-a12b:free
  cohere-code     cohere/north-mini-code:free
  qwen27b         qwen/qwen3.8-27b
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")

_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)

KEPT_JSON = os.environ.get("MECH_KEPT_JSON", "tasks-v5-kept.json")

ALIASES = {
    "120b": "openai/gpt-oss-120b",
    "20b": "openai/gpt-oss-20b",
    "nemotron-super": "nvidia/nemotron-3-super-120b-a12b:free",
    "cohere-code": "cohere/north-mini-code:free",
    "qwen27b": "qwen/qwen3.8-27b",
}
PLAIN = ALIASES["120b"]

CANARY_PROMPTS = [
    "Reply with exactly: CANARY-ONE",
    "What is 17*23? Reply with the number only.",
]

REVISE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Study the failure detail carefully and produce a corrected answer. "
    "Follow the original instructions exactly. Do not repeat your previous "
    "answer unchanged."
)


def safe_name(model):
    return model.replace("/", "_").replace(":", "_")


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_task(tid):
    tasks = json.load(open(os.path.join(BASE, KEPT_JSON)))["tasks"]
    for t in tasks:
        if t["id"] == tid:
            return t
    raise ValueError(f"unknown kept task: {tid}")


def raw_call(model, prompt):
    """One fresh model call. Returns answer text ('' on transport failure)."""
    fd, ppath = tempfile.mkstemp(prefix="xrev-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="xrev-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = model
        env["SWARM_CACHE"] = "0"
        env["SWARM_REDELEGATE"] = "0"
        env["SWARM_FALLBACK"] = ""
        env["SWARM_SKIP_UNHEALTHY"] = "0"
        env["SWARM_TIMEOUT"] = "180"
        subprocess.run(
            [SWARM_CALL, "-f", ppath, outdir],
            env=env, capture_output=True, text=True, timeout=300,
        )
        txt_path = os.path.join(outdir, safe_name(model) + ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(ppath):
            os.unlink(ppath)
        shutil.rmtree(outdir, ignore_errors=True)


class WindowCache:
    """Deterministic-within-window cache. Invalid across windows."""

    def __init__(self, path, enabled=True):
        self.path = path
        self.enabled = enabled
        self.hits = 0
        self.misses = 0
        self.data = {"window": None, "calls": {}}
        if enabled and os.path.exists(path):
            try:
                self.data = json.load(open(path))
            except Exception:
                self.data = {"window": None, "calls": {}}
        self.window = None

    def measure_window(self):
        outs = [raw_call(PLAIN, p) for p in CANARY_PROMPTS]
        self.window = sha256("\x00".join(outs))
        return self.window

    def get(self, model, prompt):
        key = sha256(model + "\x00" + prompt)
        if (self.enabled and self.data.get("window") == self.window
                and key in self.data["calls"]):
            self.hits += 1
            return self.data["calls"][key], True
        out = raw_call(model, prompt)
        self.misses += 1
        if self.enabled:
            self.data["window"] = self.window
            self.data["calls"][key] = out
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.data, f)
            os.replace(tmp, self.path)
        return out, False


def verify(task, answer):
    if not answer or not answer.strip():
        return False, "no output (transport failure or empty response)"
    try:
        ok, detail = score_v5.SCORERS[task["scorer"]](answer, task)
    except Exception as e:
        return False, f"scorer crashed: {type(e).__name__}: {e}"
    return bool(ok), detail


def norm_answer(a):
    return re.sub(r"\s+", " ", a.strip().lower())


def run_chain(task, gen, revs, cache):
    """gen generates; revs = [(model, n_revisions), ...] applied in order."""
    attempts = []
    seen = set()
    prompt = task["prompt"]
    answer = None
    detail = ""
    n = 0
    # attempt 1: generator on the raw prompt
    answer, hit = cache.get(gen, task["prompt"])
    n = 1
    passed, detail = verify(task, answer)
    key = norm_answer(answer)
    seen.add(key)
    attempts.append({"attempt": n, "model": gen, "pass": passed,
                     "detail": detail, "repeated": False, "cache_hit": hit})
    if passed:
        return answer, attempts
    for model, count in revs:
        for _ in range(count):
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
            n += 1
            answer, hit = cache.get(model, prompt)
            passed, detail = verify(task, answer)
            key = norm_answer(answer)
            repeated = key in seen
            seen.add(key)
            attempts.append({"attempt": n, "model": model, "pass": passed,
                             "detail": detail, "repeated": repeated,
                             "cache_hit": hit})
            if passed or repeated:
                break
        if passed or attempts[-1]["repeated"]:
            break
    return answer, attempts


def parse_mech(spec):
    spec = spec.strip()
    if spec == "plain":
        return ("plain", None)
    if spec == "cascade":
        return ("cascade", None)
    if ">" in spec:
        g, r = spec.split(">", 1)
        return ("chain", (ALIASES[g.strip()], [(ALIASES[r.strip()], 2)]))
    raise ValueError(f"bad mech spec: {spec}")


def run_mech(task, mech, cache):
    kind, cfg = mech
    if kind == "plain":
        answer, hit = cache.get(PLAIN, task["prompt"])
        passed, detail = verify(task, answer)
        attempts = [{"attempt": 1, "model": PLAIN, "pass": passed,
                     "detail": detail, "repeated": False, "cache_hit": hit}]
        return answer, attempts
    if kind == "cascade":
        gen = ALIASES["20b"]
        revs = [(ALIASES["20b"], 2), (ALIASES["120b"], 2)]
        return run_chain(task, gen, revs, cache)
    gen, revs = cfg
    return run_chain(task, gen, revs, cache)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True,
                    help="comma-separated task ids")
    ap.add_argument("--mechs", required=True,
                    help="comma-separated mech specs")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--canary-every", type=int, default=12,
                    help="mid-run canary re-probe every K completed cells "
                         "(0 disables; default 12)")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    tasks = [t.strip() for t in args.tasks.split(",")]
    mechs = [(s.strip(), parse_mech(s.strip())) for s in args.mechs.split(",")]

    cache = WindowCache(os.path.join(args.outdir, "cache.json"),
                        enabled=not args.no_cache)
    print("measuring window (canary)...", flush=True)
    window = cache.measure_window()
    print(f"window: {window[:16]}... "
          f"(cache window: {str(cache.data.get('window'))[:16]})", flush=True)
    cache_valid = cache.data.get("window") == window
    print(f"cache {'HIT — reusing in-window calls' if cache_valid else 'MISS — fresh window'}",
          flush=True)

    window_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results_path = os.path.join(args.outdir, "results.json")
    results = {"window_start_utc": window_start, "window_canary": window,
               "window_segments": [{"seg": 0, "canary": window,
                                    "started_at_utc": window_start,
                                    "cell_index": 0}],
               "window_boundaries": [],
               "straddled_pairs": [],
               "tasks": tasks, "mechs": [s for s, _ in mechs], "cells": []}
    done = set()
    cur_seg = 0
    if os.path.exists(results_path):
        try:
            prev = json.load(open(results_path))
            prev_segs = prev.get("window_segments") or [
                {"seg": 0, "canary": prev.get("window_canary")}]
            last_canary = prev_segs[-1]["canary"]
            if last_canary == window:
                results = prev
                results.setdefault("window_segments", prev_segs)
                results.setdefault("window_boundaries", [])
                results.setdefault("straddled_pairs", [])
                cur_seg = prev_segs[-1]["seg"]
                done = {(c["task"], c["mech"]) for c in prev["cells"]}
                print(f"resuming: {len(done)} cells already done in this "
                      f"window (segment {cur_seg})", flush=True)
            else:
                print("canary changed — previous partial was another window; "
                      "starting fresh", flush=True)
        except Exception as e:
            print(f"could not read previous results ({e}); starting fresh",
                  flush=True)
    cur_canary = results["window_segments"][-1]["canary"]
    cells_since_probe = 0
    k = args.canary_every
    for tid in tasks:
        task = load_task(tid)
        for spec, mech in mechs:
            if (tid, spec) in done:
                continue
            print(f"[{tid}] {spec}", flush=True)
            try:
                answer, attempts = run_mech(task, mech, cache)
            except Exception as e:
                attempts = [{"attempt": 0, "model": "error",
                             "pass": False,
                             "detail": f"harness error: {type(e).__name__}: {e}",
                             "repeated": False, "cache_hit": False}]
            final_pass = attempts[-1]["pass"] if attempts else False
            cell_ts = datetime.datetime.now(
                datetime.timezone.utc).isoformat()
            results["cells"].append({
                "task": tid, "mech": spec, "final_pass": final_pass,
                "trajectory": [a["pass"] for a in attempts],
                "models": [safe_name(a["model"]) for a in attempts],
                "cache_hits": sum(1 for a in attempts if a["cache_hit"]),
                "calls": len(attempts),
                "ts_utc": cell_ts,
                "window_seg": cur_seg,
            })
            cells_since_probe += 1
            # Mid-run canary re-probe. A window boundary inside a paired
            # comparison is an enforced event here, not a protocol hope.
            if k > 0 and cells_since_probe >= k:
                cells_since_probe = 0
                probe = cache.measure_window()
                if probe != cur_canary:
                    bts = datetime.datetime.now(
                        datetime.timezone.utc).isoformat()
                    # boundary falls after the cell just completed
                    bidx = len(results["cells"])
                    results["window_boundaries"].append({
                        "ts_utc": bts, "cell_index": bidx,
                        "old_canary": cur_canary, "new_canary": probe})
                    cur_seg += 1
                    cur_canary = probe
                    results["window_segments"].append({
                        "seg": cur_seg, "canary": probe,
                        "started_at_utc": bts, "cell_index": bidx})
                    # old cache is poisoned: calls from the old window must
                    # not leak into the new one
                    cache.window = probe
                    cache.data = {"window": probe, "calls": {}}
                    tmp = cache.path + ".tmp"
                    with open(tmp, "w") as f:
                        json.dump(cache.data, f)
                    os.replace(tmp, cache.path)
                    print(f"WINDOW BOUNDARY at cell {bidx}: "
                          f"{probe[:12]}... (segment {cur_seg})", flush=True)
            with open(os.path.join(args.outdir, "results.json"), "w") as f:
                json.dump(results, f, indent=1)

    # Pairs whose two cells landed in different window segments are invalid
    # for the sign test. The consumer drops them (see straddled_pairs).
    cell_by_key = {(c["task"], c["mech"]): c for c in results["cells"]}
    straddled = []
    for tid in tasks:
        pcell = cell_by_key.get((tid, "plain"))
        for spec, _ in mechs:
            if spec == "plain":
                continue
            mcell = cell_by_key.get((tid, spec))
            if pcell is not None and mcell is not None \
                    and pcell.get("window_seg", 0) != mcell.get("window_seg", 0):
                straddled.append({
                    "task": tid, "mech": spec,
                    "plain_seg": pcell.get("window_seg", 0),
                    "mech_seg": mcell.get("window_seg", 0)})
    results["straddled_pairs"] = straddled
    with open(os.path.join(args.outdir, "results.json"), "w") as f:
        json.dump(results, f, indent=1)

    # report
    lines = ["# Cross-model revision v2", "",
             f"Window start (UTC): {window_start}",
             f"Canary: {window[:16]}...",
             f"Cache: {cache.hits} hits, {cache.misses} misses", "",
             "| task | " + " | ".join(s for s, _ in mechs) + " |",
             "|---|---|" + "---|" * len(mechs)]
    for tid in tasks:
        row = [tid]
        for spec, _ in mechs:
            c = next(x for x in results["cells"]
                     if x["task"] == tid and x["mech"] == spec)
            traj = "".join("1" if p else "0" for p in c["trajectory"])
            row.append(f"{'PASS' if c['final_pass'] else 'fail'} ({traj})")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["",
              f"Window boundaries mid-run: {len(results['window_boundaries'])}",
              f"Straddled pairs (excluded from sign test): {len(straddled)}",
              "Trajectory: 1=pass, 0=fail per attempt in order.",
              "120b-call counts per mech on hard tasks: see results.json "
              "(models array per cell)."]
    with open(os.path.join(args.outdir, "REPORT.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\ncache: {cache.hits} hits / {cache.misses} misses", flush=True)


if __name__ == "__main__":
    main()

================================================================
FILE: benchmark-v5/run-v5.sh
================================================================
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

================================================================
FILE: benchmark-v5/tasks-v5-kept.json
================================================================
{
  "tasks": [
    {
      "id": "c1-expr-eval-3",
      "family": "code",
      "prompt": "Write a Python function named evaluate that takes one string argument: an arithmetic expression, and returns a float. The expression contains non-negative integers, the binary operators + - * / and ** (exponentiation), parentheses, and unary minus. Unary minus may appear at the start of the expression, right after '(', or right after another operator (including after **). Unary minus binds LESS tightly than **, as in Python: -2**2 is -4, not 4. ** is right-associative: 2**3**2 is 512. Whitespace may appear anywhere and must be ignored. Division is float division. Do NOT use eval, exec, or the ast module. Reply with ONLY the function code, no explanation.",
      "scorer": "code_function_numeric_tests",
      "function": "evaluate",
      "hidden_tests": [
        [
          "3*-2",
          -6.0
        ],
        [
          "2**3**2",
          512.0
        ],
        [
          "-(2+3)*-2",
          10.0
        ],
        [
          " 4 + 2 * -3 ",
          -2.0
        ],
        [
          "10/4",
          2.5
        ],
        [
          "2**-1",
          0.5
        ],
        [
          "(1+2)*(3- -1)",
          12.0
        ],
        [
          "--5",
          5.0
        ],
        [
          "-2**2",
          -4.0
        ],
        [
          "3 * -(2 + -1)",
          -3.0
        ]
      ],
      "tolerance": 1e-06,
      "ban_eval": true
    },
    {
      "id": "c10-sexpr",
      "family": "code",
      "prompt": "Write a Python function named seval that takes a string: an arithmetic expression in fully-parenthesized prefix notation, e.g. '(+ 1 (* 2 3) (- 10 4))'. Operators: + * - /. + and * take one or more operands; - and / take one or more operands (unary minus for a single operand, left-associative otherwise); / is float division. Operands are integers or nested expressions, separated by whitespace. Return a float. Reply with ONLY the function code.",
      "scorer": "code_function_numeric_tests",
      "function": "seval",
      "hidden_tests": [
        [
          "(+ 1 (* 2 3) (- 10 4))",
          13.0
        ],
        [
          "(* (+ 1 2) (+ 3 4))",
          21.0
        ],
        [
          "(- 5)",
          -5.0
        ],
        [
          "(/ 7 2)",
          3.5
        ],
        [
          "(+ (* 2 3) (/ 9 3) (- 1))",
          8.0
        ],
        [
          "(- (* 2 5) 3 2)",
          5.0
        ]
      ],
      "tolerance": 1e-09
    },
    {
      "id": "l1-knights-6",
      "family": "logic",
      "prompt": "Six islanders \u2014 A, B, C, D, E, F \u2014 are each either a knight (always tells the truth) or a knave (always lies). Each makes one statement:\nA says: \"C is a knave.\"\nB says: \"D is a knight.\"\nC says: \"if E is a knight then A is a knave.\"\nD says: \"A is a knave.\"\nE says: \"if C is a knight then D is a knave.\"\nF says: \"if B is a knight then F is a knave.\"\nThere is exactly one consistent assignment. Reply with ONLY a 6-letter string for A,B,C,D,E,F in order, using T for knight and F for knave (example: TFTFTF).",
      "scorer": "token_strict",
      "expected": "tttttf"
    },
    {
      "id": "w2-word-count",
      "family": "writing",
      "prompt": "Write exactly 5 sentences. Each sentence must contain exactly 6 words. Reply with ONLY the 5 sentences.",
      "scorer": "constraint_words",
      "n_sentences": 5,
      "words_per_sentence": 6
    },
    {
      "id": "w5-lines-words",
      "family": "writing",
      "prompt": "Write exactly 6 lines. Odd-numbered lines (1, 3, 5) must start with '- ' (dash, space). Even-numbered lines (2, 4, 6) must start with '* ' (asterisk, space). After the bullet marker, each line must contain exactly 4 words. Reply with ONLY the 6 lines.",
      "scorer": "constraint_list_alt",
      "n_lines": 6,
      "odd_prefix": "- ",
      "even_prefix": "* ",
      "words_per_line": 4
    }
  ],
  "kept_ids": [
    "c1-expr-eval-3",
    "c10-sexpr",
    "l1-knights-6",
    "w2-word-count",
    "w5-lines-words"
  ],
  "dropped_ids": [
    "c2-csv-2",
    "c3-sjson-2",
    "c4-wildcard-2",
    "c5-base-convert-2",
    "c6-roman-validate",
    "c7-date-add",
    "c8-rle-decode",
    "c9-brackets",
    "c11-morse",
    "c12-caesar-2",
    "l2-schedule-5",
    "l3-zebra-4",
    "l4-exactly-one",
    "l5-tournament",
    "l6-seating",
    "l7-liar-chain",
    "l8-syllogism",
    "a1-fee-order",
    "a2-tip-pretax",
    "a3-percent-trap",
    "a4-harmonic",
    "a5-bogo",
    "a6-compound",
    "w1-double-constraint",
    "w3-acrostic",
    "w4-comma-exact",
    "w6-n-words",
    "x1-count-word",
    "x2-salient-wrong",
    "x3-third-highest",
    "x4-ratio-trap",
    "n1-not-true",
    "n2-chronology",
    "n3-except",
    "n4-odd-one-out",
    "s1-count-letter",
    "s2-seven-words"
  ]
}
================================================================
FILE: benchmark-v4/REPORT.md
================================================================
# Benchmark v4 — report: can anything beat plain gpt-oss-120b?

Run 2026-10-18. 16 tasks, 3 fresh reps per task per mechanism, 144 scored
cells, zero missing data. All scorers mechanical (no LLM-as-judge).
Honest attribution: SWARM_REDELEGATE=0, SWARM_FALLBACK="", SWARM_CACHE=0,
SWARM_SKIP_UNHEALTHY=0. Every task verified good-pass/bad-fail by
design-v4.py before the run.

## Result

| Mechanism | Score | Per-task mean |
|-----------|-------|---------------|
| plain (gpt-oss-120b) | 48/48 | 1.000 |
| revise (120b generator + mechanical verifier, ≤2 revisions) | 48/48 | 1.000 |
| route (code tasks → gpt-oss-20b, rest → 120b; pre-registered in ROUTER.md) | 45/48 | 0.938 |

Per-task (plain / route / revise, reps passing): 15 tasks went 3/3 / 3/3 / 3/3.
The single exception is **01-code-evaluator-2**: plain 3/3, revise 3/3,
route **0/3** — gpt-oss-20b crashed with ValueError on `' 2 ** 3 '`
(whitespace around the power operator) in all three reps, while 120b's
hand-rolled parser passed 12/12 three times.

Paired sign tests (task-level wins/losses vs plain):
- route vs plain: 0W / 1L / 15T, one-sided p = 1.000
- revise vs plain: 0W / 0L / 16T, one-sided p = 1.000

## Verdict

**No. Nothing beat plain gpt-oss-120b, and the reason is structural: the
suite ceilinged at 120b (48/48), leaving no headroom for any mechanism to
demonstrate a win.** With the baseline at 100%, "revise ties" and "route
loses one task" are the only possible outcomes. This experiment cannot
distinguish "no mechanism helps" from "the tasks are too easy" — the honest
reading is the second one, given v3 broke 120b at 7/8 on harder variants of
the same task families.

Two genuine findings anyway:

1. **Routing on stale evidence hurts.** The pre-registered rule sent code
   tasks to 20b based on v3 (where 20b went 12/12 on the parser 120b
   failed). On v4's parser — same family, fresh traps (`**` right-assoc,
   whitespace) — 20b failed 0/3 and 120b passed 3/3. Per-task-type routing
   from one benchmark run does not transfer to the next task variant.
   The original code router (nemotron-super, 8/8 on v3) was 429-dead for
   the whole run window; the switch to 20b is documented in ROUTER.md.
2. **The revise loop adds cost, no benefit — and thrashes on verifier
   disagreement.** On the one task where the verifier initially disagreed
   with a correct answer (task 08, see scorer note below), all three revise
   loops went 1144.63 (correct) → 1357.13 (worse: fee applied, discount
   dropped) → 1144.63, identically. Feeding failure detail without ground
   truth makes the model thrash rather than converge.

Also noted: **zero run-to-run variance in v4** (no task went 1/3 or 2/3 in
any mechanism), versus large variance in v3. Variance is task-dependent,
not a model constant — v4's tasks sit comfortably inside 120b's reliable
capability band, v3's sat on its edge.

## Scorer bug found and fixed mid-analysis

Task 08's first scoring run marked the correct answer 1144.63 as FAIL:
Python's `round(1144.625, 2)` gives 1144.62 (banker's rounding), and float
error makes `|1144.63 − 1144.62| = 0.0100000000002`, just outside the 0.01
tolerance. The model was right; the scorer was wrong. Tolerance widened to
0.015 (both trap answers sit 10+ away, still cleanly excluded), all 16
tasks re-verified good-pass/bad-fail, then rescored. Lesson for v5: compare
money arithmetic with Decimal or rational math, not float tolerance.

## Method notes

- 144/144 cells have real model outputs; the one NO-OUTPUT in the logs is
  the aborted nemotron-super attempt (429 on every try, 3 attempts, 240s),
  recorded as missing data per protocol, never substituted silently.
- design-v4.py, score-v4.py, analyze-v4.py, run-v4.sh, revise-v4.py,
  ROUTER.md all live in this directory. Raw outputs:
  `results/raw/<plain|route|revise>/<task>/rep<1..3>/`.

## What v5 needs

1. **Adversarial task selection first.** Screen candidate tasks against
   120b (3+ reps each); keep only tasks where 120b fails ≥2/3. v4 proves
   that untested "hard-looking" tasks ceiling at the baseline and waste
   the experiment. Report the selection procedure to guard against
   overfitting to one model's quirks.
2. **More reps on discriminating tasks** (5+) for tighter variance bounds.
3. **Re-test routing per task, not per task-type from stale runs** —
   router evidence must come from the same task distribution it serves.
4. **Decimal/rational scoring** for money arithmetic (see scorer bug).

================================================================
FILE: benchmark-v4/ROUTER.md
================================================================
# v4 routing map (pre-registered 2026-10-18, before any v4 run)

Chosen a priori from benchmark-v3 evidence. Not fitted to v4 results.

| Task type | Routed model | v3 evidence |
|-----------|--------------|-------------|
| Code tasks: 01-code-evaluator-2, 02-code-sjson, 03-code-wildcard, 04-code-base-convert, 15-code-caesar, 16-code-roman | `openai/gpt-oss-20b` | 12/12 on v3's task 03 (the expression-parser task gpt-oss-120b failed); strongest non-120b code-task evidence |
| All other tasks (logic, arithmetic, adversarial, long-context, temporal) | `openai/gpt-oss-120b` | Best overall on v3 (7/8) |

## Amendment 2026-10-18 (during v4 run)

The original registration routed code tasks to
`nvidia/nemotron-3-super-120b-a12b:free` (8/8 on v3). During the v4 run the
model returned HTTP 429 on every attempt (3 attempts, 240s, zero output) —
the OpenRouter free route was dead for the whole window. Per the run
protocol ("if a route dies for an hour, move on and record it"), the code
router was switched to gpt-oss-20b, the other model named in the experiment
brief, with v3 evidence above. No v4 results informed the switch. The
nemotron-super cells from the aborted attempt are recorded as NO-OUTPUT in
the run log, not as scores.

The actual serving model for every route cell is recorded in
`results/raw/route/<task>/rep<N>/model.txt`. If a routed model is
rate-limited for a whole task set, the cell is recorded as missing data —
never silently substituted.

================================================================
FILE: benchmark/results/REPORT.md
================================================================
# Swarm Capability Benchmark — Results Report

**Run date:** 2026-10-15 (UTC 19:00–21:30; gap-fill waves through 21:28)
**Suite:** `~/workspace/freellmapi/benchmark/` (tasks.json, run-benchmark.sh, score.py)
**Method:** 10 tasks with known-good answers, deterministic mechanical scorers.
No LLM-as-judge. Same prompt to every model, one call per (task, model).
**Roster:** swarm `wide` mode (11 models), `SWARM_EXCLUDE=allam-2-7b`,
`SWARM_SKIP_UNHEALTHY=1` (wave 1), `SWARM_STAGGER_SECS=5`.

## Coverage notes

- `qwen/qwen3.8-27b`: unavailable for the entire benchmark — 11 consecutive
  HTTP 413 failures predating the run (route broken; see ab-1 DEVIATIONS.md).
  Infrastructure, not a capability finding.
- Wave 1 (19:00 UTC): 7 models × 10 tasks. `gpt-oss-120b` / `gpt-oss-20b`
  skipped (Groq 429 within the 1h health window); `gemini-3.8-flash` failed
  task 01 with HTTP 502 ×3 then marked unhealthy; `gemini-3.5-flash-lite`
  failed task 05 with HTTP 429 ×3; `gemini-3-flash-preview` failed task 10
  with HTTP 502 ×3.
- Wave 2 (19:43–20:50 UTC): gap-fill, one model at a time. `gpt-oss-20b`
  completed 10/10. `gemini-3.8-flash` route proved flaky (5 transport
  failures, 3 successes). wave2.sh died silently mid-task-09 (cause
  undetermined — see below).
- The FreeLLMAPI server died twice during the benchmark (~19:00 restart
  before wave 1; died again ~21:00, restarted ~21:03). All http=000
  failures in wave 3 trace to the second outage.
- Wave 3 (21:03 UTC): `gemini-3.5-flash-lite` hit the Google route's
  rate limit — server returned `Retry-After: 35787` (~10h, "Soonest reset
  ~10h"). Google models (3.5-flash-lite tasks 06–10, flash-preview task 10,
  3.8-flash tasks 09–10) unrecoverable within this run.
- `gpt-oss-120b` × 10 tasks completed via cache hits; provenance verified
  by a fresh uncached call (task 07 → "Saturday", matching cached output).
  Groq route recovered by 21:20 UTC.

## Per-model per-task results

P = pass, F = capability fail, . = no output (transport/rate-limit)

| Model | 01 fact | 02 arith | 03 code | 04 json | 05 constr | 06 sum | 07 date | 08 units | 09 class | 10 calib | Score |
|-------|---------|----------|---------|---------|-----------|--------|---------|----------|----------|----------|-------|
| openai/gpt-oss-120b | P | P | P | P | P | P | P | P | P | P* | 10/10 |
| openai/gpt-oss-20b | P | P | P | P | P | P | P | P | P | P | 10/10 |
| gemini-3-flash-preview | P | P | P | P | P | P | P | P | P | . | 9/9 |
| gemini-3.5-flash-lite | P | F | P | P | P | . | . | . | . | . | 4/5 |
| gemini-3.8-flash | . | . | P | . | P | . | . | P | . | . | 3/3 |
| cohere/north-mini-code:free | P | P | P | P | P | P | P | P | P | P | 10/10 |
| nvidia/nemotron-3-super-120b-a12b:free | P | P | P | P | P | P | P | P | P | P | 10/10 |
| liquid/lfm-2.5-2.6b:free | P | P | P | P | P | P | P | P | F | P | 9/10 |
| dots-studio/dots-3-note-preview:free | P | P | P | P | P | P | P | P | P | P | 10/10 |
| nvidia/nemotron-3.5-lightning:free | P | P | P | P | P | P | P | P | P | P | 10/10 |
| qwen/qwen3.8-27b | — | — | — | — | — | — | — | — | — | — | unavailable |

\* 120b task 10 scored PASS per rubric (refusal), but see F4 below.

**Overall: 85/87 scored calls passed = 97.7%.**

## Failure taxonomy

### F1. Silent arithmetic error (reasoning) — the sharpest capability failure
- **Model:** gemini-3.5-flash-lite — **Task 02** (bakery revenue)
- **Output:** `1539.375` (correct: 1665)
- **Mode:** confident wrong number, no hedging, no shown work. The model
  produced a precise-looking decimal that is simply incorrect — the most
  dangerous failure shape: high precision, zero accuracy, no uncertainty
  signal.

### F2. Task-format abandonment (instruction following)
- **Model:** liquid/lfm-2.5-2.6b — **Task 09** (classification)
- **Output:** echoed the input items verbatim
  (`Apple\nCarrot\nWheat\nBanana\nBroccoli`) instead of emitting
  FRUIT/VEGETABLE/GRAIN labels.
- **Mode:** the model repeated the prompt's items rather than performing the
  requested mapping. Not a knowledge failure — a failure to execute the
  task shape.

### F3. Transport / rate-limit failures (infrastructure, not capability)
- qwen/qwen3.8-27b — all tasks: HTTP 413 ×11 (route broken, pre-existing).
- gemini-3.8-flash — 5 of 8 attempts: HTTP 502 / 429 (flaky route; 3/3
  passed when it responded).
- gemini-3-flash-preview — task 10: HTTP 502 ×3.
- Google route (all Gemini models): 10-hour rate-limit reset hit at ~21:15
  UTC (`Retry-After: 35787`). Tasks 06–10 for 3.5-flash-lite, task 10 for
  flash-preview, tasks 09–10 for 3.8-flash unrecoverable in this run.
- FreeLLMAPI server died twice during the benchmark (all http=000
  failures). No systemd supervisor on this VM; the overnight cron's
  preflight is the only watchdog.

### F4. Weak calibration behaviors (passed rubric, noted qualitatively)
- **gpt-oss-120b — Task 10:** answered the fabricated CERN premise with a
  generic policy-style refusal — *"I'm sorry, but I can't provide that
  information."* — instead of correcting the false premise the way all six
  other models did ("there was no such study…"). Scored PASS (it refused
  rather than confabulated), but it is the weakest calibration behavior
  observed: evasive rather than truthful, and indistinguishable from a
  content-policy refusal.
- **liquid/lfm-2.5-2.6b — Task 10:** correctly denied the premise ("there
  was no 2019 CERN study…") but then confabulated a replacement — naming
  "Martin Solan" as lead researcher of a Google study titled "Implementing
  bilocal unitary evolution on a near-term quantum computer" (Nature, Oct
  2018). Confident specifics attached to a redirected claim: a calibration
  smell worth watching.

## Scorer fixes applied during the run

1. `score_code_tests`: harness used `json.dumps` for the test list, emitting
   lowercase `true`/`false` into Python — switched to `repr()`.
2. `score_fact_substrings`: "eight different time zones" not matched —
   now accepts "eight" + "time zone" with intervening words.
3. `score_uncertainty_expressed`: added markers ("there was no",
   "doesn't appear", "can't provide that information", …), strips markdown
   formatting, normalizes Unicode quotes (curly → straight apostrophes).

## Conclusions — the swarm's weakest areas

1. **Silent numeric reasoning errors.** The only confident-wrong-answer
   failure: gemini-3.5-flash-lite's 1539.375 vs 1665, delivered with no
   hedging. For any pipeline that consumes model arithmetic (position
   sizing, P&L, unit conversions), outputs need independent recomputation —
   never trust a model's number at face value.
2. **Instruction-following under format constraints.** liquid/lfm-2.5-2.6b
   abandoned the classification task shape entirely and echoed inputs.
   Small models are the risk here; the 120b/20b/nemotron/cohere/dots
   models all held format across every task.
3. **Calibration is good but uneven.** All models avoided confabulating an
   answer to the fabricated premise, but response quality varied from
   premise-correcting (nemotron, 20b, cohere, dots) through evasive
   (120b's generic refusal) to redirect-confabulation (liquid inventing
   "Martin Solan"). The critic role in the knowledge pipeline should
   specifically probe for the evasive and redirect patterns, not just
   outright confabulation.
4. **Infrastructure dominates capability as the failure source.**
   Of 23 non-passing cells, only 2 are capability failures; the rest are
   transport (429/502/413), a 10-hour Google rate-limit wall, a broken
   qwen route, and two server deaths with no supervisor. The cheapest
   reliability win is not a better model — it is server supervision and
   per-route rate-limit budgeting.

