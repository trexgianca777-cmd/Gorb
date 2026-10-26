# Majority voting over the SwarmZero roster

`vote.py` runs every model in the roster on one benchmark task, extracts a
normalized answer per model, takes the majority, and scores the winner with
the task's mechanical scorer from `../benchmark/score.py`.

## Method

- Each model is run once via `swarm-call.sh` with `SWARM_MODELS="<model>"`
  and `SWARM_CACHE=1` (all answers in the measured run below came from
  cache; no provider calls were spent).
- `SWARM_FALLBACK` is disabled and `SWARM_REDELEGATE=0`, so a counted vote
  always comes from the named model. A model that produces no output
  abstains instead of being filled in by another model.
- Answer normalization reuses `score.py`'s extraction logic (imported, not
  reimplemented): the matched year / number list / stripped code / canonical
  JSON / fact triple / day name / label sequence / uncertainty verdict.
- Ties are broken by preferring the answer backed by the highest-ranked
  model (ranking: gpt-oss-120b, gpt-oss-20b, nemotron-3.5-lightning,
  nemotron-3-super-120b, cohere north-mini-code, dots-3-note-preview,
  gemini-3-flash-preview, gemini-3.5-flash-lite, gemini-3.8-flash,
  liquid lfm-2.5-2.6b).

## Measured result (v1 tasks, 2026-10-17)

**Voted score: 10/10 — ties the best single model (gpt-oss-120b: 10/10).**

On zero of ten tasks did the majority answer diverge from gpt-oss-120b's
answer. This is the expected ceiling effect: the v1 tasks are too easy for
voting to add anything, since the top models already agree on the right
answer.

Honest caveats from the run:

- **3 of 10 models abstained on every task** (both nemotron models and
  gemini-3-flash-preview produced no output — unhealthy or transport
  failure). The vote was effectively 7 models, not 10. Abstention is the
  correct behavior; a silent substitution would have been dishonest.
- **Free-text tasks degenerate to rank-picking.** On task 05
  (constrained writing), all 7 voting models gave different wordings, so
  every answer had exactly 1 vote and the tie-break selected gpt-oss-120b's
  text. Majority voting only helps where answers converge on a canonical
  form (numbers, labels, code, JSON).
- **All answers were cache replays**, not fresh probes. A live run could
  differ where models have drifted.

## What this shows

Voting is implemented correctly and matches the best single model, but v1
cannot demonstrate that voting *beats* any model. That requires harder
tasks where the top model actually fails while the ensemble converges —
the v2 task set in `tasks-v2.json`. Until then, the defended claim is
narrower: majority voting is a safe aggregation that never underperforms
the best-ranked model on these tasks.

## Reproduce

```bash
cd benchmark-v2
python3 vote.py --all          # all 10 v1 tasks, full roster
python3 vote.py 02-multi-step-arithmetic openai/gpt-oss-120b openai/gpt-oss-20b
```

Results land in `results/vote-results.json`. The API key is resolved
read-only from the local server DB into the subprocess environment and is
never printed or logged.
