# Swarm Capability Benchmark v1

Deterministic, re-runnable probe of the FreeLLMAPI model swarm's failure
modes. 10 tasks, each with a known-good answer and a mechanical scorer —
no LLM-as-judge.

## Layout

- `tasks.json` — the 10 tasks: prompt, expected answer, scorer name, notes.
- `run-benchmark.sh [task-id ...]` — runs tasks through the swarm.
  Resolves `FREELLMAPI_API_KEY` in-memory from the server DB (never printed).
  Raw outputs land in `results/raw/<task-id>/<safe-model>.txt`
  (safe-model = model name with `/` and `:` replaced by `_`).
  Honors `SWARM_MODE` (default `wide`), `SWARM_MODELS`, `SWARM_SKIP_UNHEALTHY`,
  `SWARM_STAGGER_SECS`.
- `score.py` — deterministic scorers; writes `results/scores.json` and prints
  a pass/fail table.
- `wave2.sh` — gap-fill runner for models skipped in wave 1 by 429/5xx
  cooldowns (waits for each model's 1h window to clear).
- `results/` — raw outputs, `scores.json`, run logs, `REPORT.md`.

## The 10 tasks

| ID | Surface | Scorer |
|----|---------|--------|
| 01-factual-precision | One exact verifiable answer (Eiffel Tower year) | only 4-digit number == 1889 |
| 02-multi-step-arithmetic | 3+ step word problem (bakery revenue) | any number == 1665 |
| 03-code-prime | Write `is_prime(n)` | exec + 10 hidden tests, 15s timeout |
| 04-structured-json | ONLY valid JSON matching schema | parses and equals expected object |
| 05-constrained-instructions | Exactly 3 sentences, <40 words, no commas | terminator count, word count, comma check |
| 06-summary-coverage | Summary must contain 3 facts | case-insensitive substrings |
| 07-date-reasoning | Weekday of 2000-01-01 (verified: Saturday) | normalized == "saturday" |
| 08-unit-conversion | 5 mph → m/s, 4 decimals (2.2352) | within 0.00005 |
| 09-classification | 5 items → FRUIT/VEGETABLE/GRAIN | ordered label sequence, all 5 |
| 10-calibration-refusal | Fabricated CERN premise | uncertainty marker present |

## Re-running

```bash
cd ~/workspace/freellmapi/benchmark
./run-benchmark.sh            # all tasks, wide roster
./run-benchmark.sh 03-code-prime   # single task
SWARM_MODELS="openai/gpt-oss-20b" ./run-benchmark.sh  # single model
python3 score.py              # score everything under results/raw/
```

Note: `SWARM_CACHE=1` (default) replays exact-repeat prompt+model answers
with zero provider cost — reruns are cheap but will not re-probe the model.
Set `SWARM_CACHE=0` to force fresh calls.

## Known scorer fixes (2026-10-15)

- `score_code_tests`: harness used `json.dumps` for the test list, emitting
  lowercase `true`/`false` into Python — fixed to `repr()`.
- `score_fact_substrings`: "eight different time zones" wasn't matched —
  now accepts "eight" + "time zone" with words between.
- `score_uncertainty_expressed`: added markers ("there was no",
  "doesn't appear", ...) and strips markdown formatting before matching.
