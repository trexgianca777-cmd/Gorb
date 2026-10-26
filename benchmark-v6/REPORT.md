# Benchmark v6: Honing the Verify-Revise Loop + Novelty Study

Date: 2026-10-18. Mechanism under test: verify-revise (gpt-oss-120b generator +
mechanical verifier, thrash-guard), the one verified improvement over plain
120b from v5 cycle 2 (6 wins / 0 losses on 12 hard tasks, p=0.0156).

Task set: `tasks-v5-kept2.json` (12 tasks where plain 120b deterministically
fails): 5 code, 3 logic (single-answer), 4 writing (constraint).

## Part 1 — trajectory mining (v5 cycle-2 revise logs, 3 reps/task)

Every fix and every failure, categorized:

**Fixed in 1 revision (5 task-families):**
- Crash-type failures fix fastest. p3-unicode-json: `ValueError` traceback at
  line 162 -> 3/3 tests pass. p9-sexpr-let: `SyntaxError: name ...` at line
  64 -> 5/5. The traceback IS counterexample-grade feedback: exact line,
  exact error, exact location.
- Systematic constraint miss: w5-lines-words 3/4 words per line -> 4/4.
- Wrong single value: q3-zebra-5 digits='5' -> digits='3'.
- Partial progress: c10-sexpr 2/6 -> 6/6.

**Fixed in 2 revisions (1):**
- c1-expr-eval-3: 9/10 -> 9/10 -> 10/10. The terse detail ("tests_passed=9/10")
  does not say WHICH test fails; the model needed two rounds to find it.

**Never fixed (5):**
- l1-knights-6: thrash-guard fired. Attempt 2 reproduced attempt 1's answer
  byte-for-byte ('tffftt'). Single-answer logic puzzle; revision adds nothing
  because the detail carries no actionable information.
- r5-fifty-words: identical fail detail 3x (51/50). The model cannot decrement
  a word count by one across attempts — a fine-grained control failure.
- r8-no-e: sentence-start constraint barely moves across attempts.
- w2-word-count: oscillates (5,5,6,6,6 -> 6,6,6,7,6 -> same). The loop has no
  memory of direction; it cannot converge.
- p8-bizdays: REGRESSION. 1/6 -> 0/6. The loop keeps the LAST answer, not the
  best — strictly dominated behavior.

**What the mining says to improve:**
1. Crash tracebacks already carry counterexample detail — that is WHY code
   tasks fix fast. Non-code tasks get terse aggregates ("51/50") with no
   pinpoint. -> candidate: counterexample-rich detail for every scorer.
2. The loop keeps the last answer; p8 proves it should keep the best.
   -> candidate: keep-best-so-far.
3. r5 repeats identical detail 3x (wasted calls); w2 oscillates without
   converging (needs a different move, not more of the same).
   -> candidate: adaptive budget (stop on repeated detail) + divergence nudge.
4. One hypothesis per round; w2's oscillation suggests the single trajectory
   gets stuck. -> candidate: multi-hypothesis revision.
5. v4 showed thrash when the verifier disagrees with a correct answer; but a
   STRICTER verifier might guide better. -> candidate: strict verifier
   (extra edge tests guide revision; final judged by the original scorer).

## Part 1 — candidate results

(pending)

## Part 2 — novelty study

(pending)

## Recommended revise-v2 configuration

(pending)
