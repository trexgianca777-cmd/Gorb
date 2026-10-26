# Benchmark v2 — generate-verify-revise

Exploits the verification asymmetry: checking an answer is easier than
producing one. A (usually small) generator model answers, the task's
*mechanical* scorer from `benchmark/score.py` verifies — no LLM-as-judge —
and on failure the generator gets the scorer's failure detail plus one
revision attempt (max 2 revisions, then stop and report).

## The loop (`revise.py`)

```
generator answer -> mechanical scorer -> pass? done
                                      -> fail? append "your answer failed
                                         because: <scorer detail>" and retry
```

Default generator is `openai/gpt-oss-20b` (the small model) to prove the
loop adds value beyond the generator alone. `--verifier` is accepted for a
future LLM-judge mode; verification today is purely mechanical.

```bash
python3 revise.py --task 02-multi-step-arithmetic
python3 revise.py --task 03-code-prime --generator openai/gpt-oss-20b --max-revisions 2
```

Output: JSON with per-attempt pass/fail + scorer detail, final answer,
revisions used, total model calls. Results land in `results/`.

## v1 shakedown results (2026-10-17) — honest

| Task | Generator-only | With loop | Revisions | Extra calls |
|---|---|---|---|---|
| 02-multi-step-arithmetic | pass | pass | 0 | 0 |
| 03-code-prime | pass (10/10 tests) | pass | 0 | 0 |
| 05-constrained-instructions | pass | pass | 0 | 0 |

The loop added **nothing** on v1 tasks: the 20b generator passes them
first try (cache hits, sub-second). This is the expected ceiling effect —
v1 tasks are too easy to discriminate, which is why benchmark v2 needs
harder tasks (multi-hop reasoning, adversarial instruction-following,
long-context retrieval) where single models actually fail.

The revision *machinery* is tested and works: a stubbed wrong-first-answer
run confirmed the scorer's failure detail propagates into the revision
prompt, the loop revises and passes on attempt 2, and an always-wrong
generator stops cleanly at max revisions (3 attempts total).

## Majority voting

`vote.py` implements majority vote across the full 10-model roster with
rank-based tie-breaking; see `VOTING.md`. Measured on v1: 10/10, tying
gpt-oss-120b with zero divergences (ceiling effect, as expected). The
interesting test is voting on the harder `tasks-v2.json` set, where the
top model has headroom to fail.
