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
