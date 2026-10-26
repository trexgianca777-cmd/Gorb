# Baseline comparison — single best model vs roster

Run date: 2026-10-17. Same 10 tasks, same mechanical scorers as the
2026-10-15 roster run. One model (openai/gpt-oss-120b), fresh provider
calls (`SWARM_CACHE=0`), no cache.

## Results

| | Score | Tokens (total) | Model time | Cost |
|---|---|---|---|---|
| gpt-oss-120b, single, fresh | **10/10 (100%)** | 2,360 | ~6.4 s | $0.00 |
| Full roster, 2026-10-15 run | 85/87 (97.7%) | — | — | $0.00 |

Per-task tokens ranged from 116 (factual lookup) to 397 (constrained
writing). Every call returned HTTP 200 on the first attempt.

## Honest reading

The single best free model beats the roster aggregate on raw capability.
This benchmark does **not** show that orchestration makes models smarter.
Do not claim that it does.

What the roster buys is **coverage under failure**:

- In the 2026-10-15 run, gpt-oss-120b was rate-limited (HTTP 429) through
  the entire first wave. Its 10 cells were filled from cache after the
  route recovered. The other 9 models carried the run.
- Across the roster run, transport failures (429/502/413), a 10-hour
  Google rate-limit wall, and two local server deaths hit 21 of 110 cells.
  The per-model scorecard exists so an operator can see exactly which
  models hold up and which do not — and the redelegation system in
  swarm-call.sh exists to route around the ones that don't.

The claim this project can defend: a free-tier swarm's reliability comes
from redundancy and health tracking, not from any single model. The
benchmark measures the roster so you can see the redundancy working.

## Reproduce

```bash
cd benchmark
SWARM_MODELS="openai/gpt-oss-120b" SWARM_CACHE=0 ./run-benchmark.sh
python3 score.py
```
