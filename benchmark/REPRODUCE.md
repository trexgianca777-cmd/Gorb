# Reproducing the benchmark

Everything needed to re-run the evaluation and check the 85/87 claim is in
this directory.

## What is here

- `tasks.json` — the 10 tasks: prompt, expected answer, scorer name.
- `score.py` — deterministic scorers. No LLM-as-judge; every check is
  mechanical (exact match, substring, numeric tolerance, code execution
  against hidden tests).
- `run-benchmark.sh` — runs all tasks through `swarm-call.sh`, saving raw
  outputs to `results/raw/<task-id>/<model>.txt`.
- `results/` — the full artifacts of the 2026-10-15 run: raw model outputs,
  `scores.json`, run logs, and `REPORT.md` with the per-cell pass/fail table.
- `FAILURES.md` — analysis of the 2 capability failures and qualitative
  findings.

## Re-run it

```bash
cd benchmark
SWARM_MODELS="openai/gpt-oss-120b" SWARM_CACHE=0 ./run-benchmark.sh
python3 score.py
```

`SWARM_MODELS` accepts any comma-separated model list the backend serves.
`SWARM_CACHE=0` forces fresh provider calls; the default `SWARM_CACHE=1`
replays cached answers for free (cheap, but does not re-probe the model).

## Check our numbers without running anything

```bash
python3 score.py   # scores results/raw/ in place, prints the pass/fail table
```

Compare its output against `results/scores.json` and the table in
`results/REPORT.md`. They should match exactly — same inputs, same
mechanical scorers, no model involved in grading.

## Caveats

- The 2026-10-15 run hit real rate limits (documented in REPORT.md):
  expect partial coverage on a fresh run, especially on free tiers.
- `run-benchmark.sh` resolves its API key from the local server DB
  (environment only, never files). Point it at your own OpenAI-compatible
  backend by adapting the key-resolution block at the top of the script.
- Model behavior drifts. A re-run months later measures the models of that
  day, not the models of 2026-10-15. The raw outputs in `results/` are the
  frozen record of what was actually scored.
