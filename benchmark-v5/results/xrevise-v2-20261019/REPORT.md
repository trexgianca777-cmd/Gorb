# Cross-model revision v2

Window start (UTC): 2026-10-19T22:32:05.729876+00:00
Canary: 42966c2d607a1b71...
Cache: 13 hits, 14 misses

| task | plain | 120b>120b | 20b>120b | 20b>20b | 20b>cohere-code | 20b>qwen27b | qwen27b>qwen27b | cascade |
|---|---|---|---|---|---|---|---|---|---|
| p9-sexpr-let | fail (0) | PASS (01) | PASS (01) | PASS (01) | fail (000) | PASS (001) | fail (00) | PASS (01) |
| q3-zebra-5 | fail (0) | PASS (01) | PASS (1) | PASS (1) | PASS (1) | PASS (1) | fail (00) | PASS (1) |
| r5-fifty-words | PASS (1) | PASS (1) | PASS (1) | PASS (1) | PASS (1) | PASS (1) | fail (00) | PASS (1) |
| r8-no-e | fail (0) | fail (000) | fail (000) | fail (000) | fail (000) | fail (000) | fail (00) | fail (00000) |
| c1-expr-eval-3 | fail (0) | PASS (01) | fail (000) | fail (000) | fail (000) | fail (000) | fail (00) | fail (00000) |
| c10-sexpr | fail (0) | PASS (01) | PASS (01) | PASS (01) | fail (000) | fail (000) | fail (00) | PASS (01) |
| l1-knights-6 | fail (0) | fail (00) | fail (00) | fail (00) | fail (000) | fail (000) | fail (00) | fail (00) |

Trajectory: 1=pass, 0=fail per attempt in order.
120b-call counts per mech on hard tasks: see results.json (models array per cell).
