# Complete Model Role Schema — every model assigned by measured capability
# Generated 2026-10-14 from live profiling (pong, reasoning, format, summary tests)
# See profiles/ for raw metrics.

## Speed ranking (measured pong latency)
# 1. qwen/qwen3.8-27b: 308ms
# 2. openai/gpt-oss-20b: 370ms
# 3. liquid/lfm-2.5-2.6b:free: 533ms
# 4. cli:nemotron: 686ms
# 5. gemini-3.5-flash-lite: 994ms
# 6. cli:llama: 1109ms
# 7. openai/gpt-oss-120b: 1511ms
# 8. dots-studio/dots-3-note-preview:free: 1443ms
# 9. nvidia/nemotron-3-super-120b-a12b:free: 1549ms
# 10. cohere/north-mini-code:free: 1925ms
# 11. nvidia/nemotron-3.5-lightning:free: 2151ms
# 12. gemma-4-31b-it: 2625ms (FAILED reasoning test)
# 13. gemini-3-flash-preview: 2680ms
# 14. gemini-3.1-flash-lite: 10729ms (FAILED)
# 15. gemma-4-26b-a4b-it: 92250ms (FAILED, unusable)
# 16. nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free: 92997ms (unusable)

## Role assignments

### TIER 1: Primary workers (fast + reliable)

**openai/gpt-oss-20b** — THE WORKHORSE
- Speed: 370ms pong, 701ms reasoning. Fastest reliable reasoning model.
- Strengths: Quick decisions, triage, classification, format adherence.
- Roles: Primary grader, tiebreaker, fast synthesis, failure-ledger classifier.
- Use for: High-volume tasks where speed matters. First call for any new task type.

**qwen/qwen3.8-27b** — THE SPRINTER
- Speed: 308ms pong (fastest). Reasoning: 1377ms but verbose (1354 chars).
- Strengths: Raw speed, detailed reasoning output.
- Roles: Speed-critical nomination, verbose analysis when detail needed.
- Use for: When you need an answer NOW. Good for initial broad sweeps.

**liquid/lfm-2.5-2.6b:free** — THE SPECIALIST
- Speed: 533ms pong. Reasoning: 2143ms, VERY verbose (1522 chars).
- Strengths: Detailed explanations, thorough reasoning chains.
- Weakness: Verbose (may hit token limits on long tasks).
- Roles: Deep-dive analysis, explanation generation, teaching/exposition.
- Use for: When you need the "why" explained thoroughly.

### TIER 2: Heavy lifters (slower but capable)

**openai/gpt-oss-120b** — THE THINKER
- Speed: 1511ms pong, 1238ms reasoning. Balanced.
- Strengths: Complex reasoning, nuanced judgment, strategic thinking.
- Roles: Director (improvement planning), complex synthesis, final review.
- Use for: Tasks requiring judgment calls. The "second opinion" after fast models.

**nvidia/nemotron-3-super-120b-a12b:free** — THE REASONER
- Speed: 1549ms pong, 7009ms reasoning (slow but thorough).
- Strengths: Step-by-step reasoning, methodical analysis.
- Roles: Verifier-auditor, complex math verification, deep analysis.
- Use for: When correctness matters more than speed.

**gemini-3.5-flash-lite** — THE RELIABLE
- Speed: 994ms pong. All tests passed.
- Strengths: Consistent, reliable, good all-rounder.
- Roles: Backup grader, synthesis, general tasks.
- Use for: When primary workers are rate-limited.

### TIER 3: Specialists

**cohere/north-mini-code:free** — THE CODER
- Speed: 1925ms pong. Code-focused model.
- Strengths: Code generation, script analysis, technical tasks.
- Roles: Code review, script generation, technical documentation.
- Use for: Any code-related swarm tasks. Don't use for stock picking.

**dots-studio/dots-3-note-preview:free** — THE WILD CARD
- Speed: 1443ms pong, 6275ms reasoning. Verbose (1217 chars).
- Strengths: Unknown (preview model), but completed all tests.
- Roles: Experimental, diversity of perspective.
- Use for: When you want an uncorrelated opinion.

**nvidia/nemotron-3.5-lightning:free** — THE SLOW BURN
- Speed: 2151ms pong, 51173ms reasoning (very slow).
- Strengths: Completed tests, but too slow for interactive use.
- Roles: Overnight batch processing only.
- Use for: Non-urgent background analysis.

### TIER 4: CLI models (via Pollinations)

**cli:llama** — THE PROXY
- Speed: 1109ms pong. Routes to Pollinations backend.
- Strengths: No API key needed, reliable.
- Roles: Grader, synthesizer (as defined in swarm-roles.md).
- Caveat: Same backend as cli:nemotron; roles differ by prompt, not capability.

**cli:nemotron** — THE PROXY-2
- Speed: 686ms pong (faster than cli:llama). Same backend.
- Strengths: Slightly faster than cli:llama.
- Roles: Director, verifier-auditor (as defined in swarm-roles.md).
- Caveat: Same backend as cli:llama.

### TIER 5: Unreliable (use with caution)

**gemini-3-flash-preview** — SLOW
- Speed: 2680ms pong, 6267ms reasoning but only 128 chars (truncated?).
- Status: Completed tests but slow and terse.
- Recommendation: Use only if other Google models are down.

**gemma-4-31b-it** — FAILED
- Speed: 2625ms pong, but 0 chars on reasoning (failed).
- Status: Unreliable. Skip unless no alternative.

**gemini-3.1-flash-lite** — FAILED
- Speed: 10729ms pong (10+ seconds). Failed tests.
- Status: Too slow, unreliable. Deprecate.

**gemma-4-26b-a4b-it** — UNUSABLE
- Speed: 92250ms (92 seconds!). Failed.
- Status: Do not use.

**nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free** — UNUSABLE
- Speed: 92997ms (93 seconds!).
- Status: Do not use.

**gemini-3.8-flash** — UNTESTED
- Status: Added to roster but profiling hit rate limits.
- Recommendation: Test before assigning critical roles.

## Pipeline role mapping

### Nomination phase (need: diversity, speed)
- Primary: qwen3.8-27b, gpt-oss-20b, gpt-oss-120b (fast + diverse)
- Backup: gemini-3.5-flash-lite, lfm-2.5-2.6b

### Grading phase (need: consistency, speed)
- Primary: gpt-oss-20b (370ms, reliable)
- Backup: qwen3.8-27b, gemini-3.5-flash-lite
- CLI: cli:llama

### Synthesis phase (need: compression, speed)
- Primary: gpt-oss-20b, qwen3.8-27b
- CLI: cli:llama

### Director phase (need: judgment, strategy)
- Primary: gpt-oss-120b (balanced reasoning)
- Backup: nemotron-3-super (thorough but slow)
- CLI: cli:nemotron

### Verification phase (need: precision, skepticism)
- Primary: nemotron-3-super (methodical)
- Backup: gpt-oss-120b
- CLI: cli:nemotron

### Code tasks
- Exclusive: north-mini-code

## Recommended SWARM_MODE updates

# Fast nomination (3 fastest reliable):
#   SWARM_MODELS="openai/gpt-oss-20b qwen/qwen3.8-27b liquid/lfm-2.5-2.6b:free"

# Balanced (speed + reasoning):
#   SWARM_MODELS="openai/gpt-oss-20b openai/gpt-oss-120b qwen/qwen3.8-27b gemini-3.5-flash-lite"

# Deep analysis (slow but thorough):
#   SWARM_MODELS="openai/gpt-oss-120b nvidia/nemotron-3-super-120b-a12b:free liquid/lfm-2.5-2.6b:free"

# Deprecate from wide mode:
#   Remove: gemma-4-31b-it, gemma-4-26b-a4b-it, gemini-3.1-flash-lite,
#           nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
#   (all failed or unusably slow)
