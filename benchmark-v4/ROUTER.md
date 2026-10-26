# v4 routing map (pre-registered 2026-10-18, before any v4 run)

Chosen a priori from benchmark-v3 evidence. Not fitted to v4 results.

| Task type | Routed model | v3 evidence |
|-----------|--------------|-------------|
| Code tasks: 01-code-evaluator-2, 02-code-sjson, 03-code-wildcard, 04-code-base-convert, 15-code-caesar, 16-code-roman | `openai/gpt-oss-20b` | 12/12 on v3's task 03 (the expression-parser task gpt-oss-120b failed); strongest non-120b code-task evidence |
| All other tasks (logic, arithmetic, adversarial, long-context, temporal) | `openai/gpt-oss-120b` | Best overall on v3 (7/8) |

## Amendment 2026-10-18 (during v4 run)

The original registration routed code tasks to
`nvidia/nemotron-3-super-120b-a12b:free` (8/8 on v3). During the v4 run the
model returned HTTP 429 on every attempt (3 attempts, 240s, zero output) —
the OpenRouter free route was dead for the whole window. Per the run
protocol ("if a route dies for an hour, move on and record it"), the code
router was switched to gpt-oss-20b, the other model named in the experiment
brief, with v3 evidence above. No v4 results informed the switch. The
nemotron-super cells from the aborted attempt are recorded as NO-OUTPUT in
the run log, not as scores.

The actual serving model for every route cell is recorded in
`results/raw/route/<task>/rep<N>/model.txt`. If a routed model is
rate-limited for a whole task set, the cell is recorded as missing data —
never silently substituted.
