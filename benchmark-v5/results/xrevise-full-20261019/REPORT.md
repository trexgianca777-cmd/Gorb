# Cross-model revision pilot (FULL 12-task run)

Window start (UTC): 2026-10-19T21:52:39.376440+00:00

| task | plain | 120b->120b | 20b->120b | 120b->20b | 20b->20b |
|---|---|---|---|---|---|
| p3-unicode-json | PASS (1) | PASS (1) | PASS (1) | PASS (1) | PASS (1) |
| p8-bizdays | PASS (1) | PASS (1) | PASS (1) | PASS (1) | PASS (1) |
| p9-sexpr-let | fail (0) | PASS (01) | PASS (01) | PASS (001) | PASS (01) |
| q3-zebra-5 | fail (0) | PASS (01) | PASS (1) | PASS (01) | PASS (1) |
| q8-mastermind | PASS (1) | PASS (1) | fail (000) | PASS (1) | fail (00) |
| r5-fifty-words | fail (0) | PASS (1) | PASS (1) | PASS (1) | PASS (1) |
| r8-no-e | fail (0) | fail (000) | fail (000) | fail (000) | fail (000) |
| c1-expr-eval-3 | fail (0) | PASS (01) | fail (000) | fail (000) | fail (000) |
| c10-sexpr | fail (0) | PASS (001) | PASS (001) | fail (000) | PASS (01) |
| l1-knights-6 | fail (0) | fail (000) | fail (00) | fail (00) | fail (00) |
| w2-word-count | PASS (1) | PASS (1) | PASS (1) | PASS (1) | PASS (1) |
| w5-lines-words | PASS (1) | PASS (1) | PASS (01) | PASS (1) | fail (00) |

Trajectory notation: 1=pass, 0=fail per attempt in order.
