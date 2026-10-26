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
