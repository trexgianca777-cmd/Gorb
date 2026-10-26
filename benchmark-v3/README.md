# Benchmark v3 — adversarial suite

v1 ceilinged at 10/10 for five models. v2 discriminated weak from strong,
but gpt-oss-120b still scored 10/10. Every v3 task targets a failure mode
where strong models are known to stumble.

| ID | Task | Designed to break |
|----|------|-------------------|
| 01-knights-knaves-4 | 4-speaker knights/knaves, unique solution | Proof-by-contradiction chains; models settle on partial assignments |
| 02-scheduling-trap | 4-person schedule, contradictory conditional | Models case-split instead of detecting the impossible branch |
| 03-code-evaluator | Expression parser, unary minus, no eval | One-shot parsers mishandle `-` after `*`/`(`; eval is banned |
| 04-code-csv | CSV row parser | Doubled-quote escapes defeat split/strip approaches |
| 05-adversarial-alpha | 6 sentences A–F, no repeated word, `42` ×1 | Global word-uniqueness vs reflexive function-word repetition |
| 06-adversarial-paragraphs | 3 paras 2/3/2, distinct final words, `red` ×3 | Final-word distinctness overlooked while counting |
| 07-longctx-conflicting | Two near-identical revenue figures | Salience/position bias vs precise referent matching |
| 08-arithmetic-double-trap | Discount scope + fee base traps | Non-commutative misreads; each wrong answer maps to one trap |

Run: `./run-benchmark.sh` equivalent from v1/v2 (same `results/raw/<task>/<model>.txt`
layout), then `python3 score-v3.py`. All scorers mechanical, no LLM-as-judge.
Every task verified: reference solution passes, trap solutions fail.
