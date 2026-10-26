# Cross-model revision pilot

Window start (UTC): 2026-10-19T21:40:18.808247+00:00

| task | 120b->120b | 20b->120b | 120b->20b | 20b->20b |
|---|---|---|---|---|
| c1-expr-eval-3 | PASS (01) | fail (000) | fail (000) | fail (000) |
| p9-sexpr-let | fail (00) | PASS (01) | fail (000) | PASS (01) |
| q3-zebra-5 | PASS (01) | PASS (1) | fail (000) | PASS (1) |
| c10-sexpr | PASS (001) | PASS (01) | fail (000) | PASS (01) |

Trajectory notation: 1=pass, 0=fail per attempt in order.
n=4 tasks: pilot only, not a significance test.
