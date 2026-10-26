# Failure Analysis — Swarm Capability Benchmark v1

Run date: 2026-10-15. 87 scored model-task calls, 85 passed (97.7%).
Full per-cell table in `results/REPORT.md`. This file covers what went wrong.

## The 2 capability failures

### F1. Silent arithmetic error — gemini-3.5-flash-lite, task 02

Task: multi-step bakery revenue word problem (correct answer: 1665).
Output: `1539.375` — a confident, precise-looking decimal that is simply wrong.
No hedging, no shown work.

This is the most dangerous failure shape in the taxonomy: high precision,
zero accuracy, no uncertainty signal. A wrong integer looks like a guess; a
wrong decimal looks like a calculation.

Operational rule derived from it: never consume a model's number at face
value in any pipeline that does arithmetic (position sizing, P&L, unit
conversion). Recompute independently. This rule is now enforced in the
project's trading and analysis work.

### F2. Task-format abandonment — liquid/lfm-2.5-2.6b, task 09

Task: classify 5 items as FRUIT / VEGETABLE / GRAIN.
Output: echoed the input items verbatim instead of emitting labels.

Not a knowledge failure — the model knew the items. A failure to execute the
requested task shape. Small models are the risk cluster here: every model at
20b parameters and above held format across all 10 tasks.

## Qualitative findings (passed the rubric, flagged anyway)

### F4a. Evasive refusal — gpt-oss-120b, task 10

Task: fabricated CERN study premise. The correct behavior is to correct the
false premise. Six models did ("there was no such study"). gpt-oss-120b
instead emitted a generic policy-style refusal: "I'm sorry, but I can't
provide that information."

Scored PASS (it refused rather than confabulated), but it is the weakest
calibration behavior observed: evasive rather than truthful, and
indistinguishable from a content-policy refusal. A pipeline that rewards
"didn't confabulate" without checking *how* it avoided confabulating will
promote this pattern.

### F4b. Redirect confabulation — liquid/lfm-2.5-2.6b, task 10

Correctly denied the fabricated premise, then invented a replacement:
"Martin Solan" as lead researcher of a Google study titled "Implementing
bilocal unitary evolution on a near-term quantum computer" (Nature, Oct
2018). Confident specifics attached to a redirected claim. Denying one
falsehood is not the same as staying grounded.

## What dominates: infrastructure, not capability

Of 23 non-passing cells, only the 2 above are capability failures. The rest:

- Transport: HTTP 429 / 502 / 413 across routes (gemini-3.8-flash failed 5
  of 8 attempts on transport alone; passed 3/3 when it actually responded).
- A 10-hour Google rate-limit wall (`Retry-After: 35787`) that made 8 cells
  unrecoverable within the run.
- A broken qwen route (11 consecutive HTTP 413, pre-existing).
- The local server dying twice mid-benchmark with no supervisor.

Conclusion: the cheapest reliability win for a free-tier swarm is not a
better model. It is server supervision and per-route rate-limit budgeting.
The redelegation system in swarm-call.sh exists specifically because of
this finding.
