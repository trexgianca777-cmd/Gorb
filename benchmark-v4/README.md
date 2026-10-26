# Benchmark v4 — can anything beat plain gpt-oss-120b?

v3 (8 tasks) found no mechanism beating plain 120b, but n=8 made nothing
significant and run-to-run variance was large. v4 doubles the task count
(16 tasks), runs every task 3 times per mechanism, and tests three mechanisms:

- **plain**: gpt-oss-120b, one fresh call per rep (baseline).
- **route**: per-task routing to the v3-best model for that task type
  (code tasks -> nemotron-super, everything else -> 120b). See ROUTER.md.
- **revise**: revise-v4.py — 120b generator + mechanical verifier, <=2
  revisions with the scorer's failure detail fed back, 3 independent loops.

All 16 tasks are mechanically scorable and were verified good-pass/bad-fail
by design-v4.py (reference solution passes, plausible-wrong answer fails;
ground truth computed independently: brute force, datetime, eval/json/
fnmatch/int, token counts).

Run: `./run-v4.sh plain`, `./run-v4.sh route`, `./run-v4.sh revise`
(idempotent per cell; resumes after interruption). Score: `python3 score-v4.py`.
Report: REPORT.md.

Honest attribution everywhere: SWARM_REDELEGATE=0, SWARM_FALLBACK="",
SWARM_SKIP_UNHEALTHY=0, SWARM_CACHE=0. Rate-limited cells are missing data,
never silently substituted.
