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
