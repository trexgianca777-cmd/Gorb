# Swarm Role Schema — specialized agents for the stock pipeline
# Created 2026-10-14. Assigns CLI models to pipeline compartments based on
# task characteristics. Both cli:llama and cli:nemotron route via Pollinations
# (same backend); roles differ by prompt specialization, not model weights.

## Role definitions

### 1. GRADER (cli:llama)
# Task: Score stock picks against rubric. Needs: consistency, format adherence,
# fast binary decisions.
# Why llama: Small, fast, follows structured output well. Good for high-volume
# grading where consistency matters more than depth.
# Prompt pattern: rubric + pick + strict output format. Temperature 0.3.
# Input: single pick text + rubric
# Output: scores per criterion + PASS/FAIL

### 2. SYNTHESIZER (cli:llama)
# Task: Compress 14 model outputs into one-line claims per model.
# Needs: extraction, compression, no editorializing.
# Why llama: Fast, good at following "extract, don't interpret" instructions.
# Prompt pattern: "Extract the single central claim. One sentence. No commentary."
# Input: raw model output
# Output: "MODEL: one-line claim"

### 3. DIRECTOR (cli:nemotron)
# Task: Analyze failure ledger + grades, decide what to improve next.
# Needs: pattern recognition across runs, prioritization, strategic thinking.
# Why nemotron: Larger context window handles multi-run history. Better at
# "what should we change" vs "what is this."
# Prompt pattern: failure categories + grade distributions + "rank the top 3
# interventions by expected failure-recovery"
# Input: swarm-failures.csv summary + grades.md + current prompt
# Output: ranked intervention list with expected impact

### 4. VERIFIER-AUDITOR (cli:nemotron)
# Task: Spot-check verify-pick.py results. Needs: arithmetic precision,
# skepticism, attention to edge cases the script might miss.
# Why nemotron: More thorough on nuanced cases (e.g., "is this fair value
# label actually correct?" vs just "does the field exist").
# Prompt pattern: pick + verifier flags + "do you agree with each flag? Any
# missed issues?"
# Input: pick text + verification report
# Output: agree/disagree per flag + additional issues found

### 5. TIEBREAKER (cli:llama)
# Task: When models split on a pick, make final call. Needs: decisiveness,
# clear reasoning, no hedging.
# Why llama: Fast, less prone to overthinking. Good for "pick one and commit."
# Prompt pattern: two competing picks + "choose one. One paragraph why. No hedging."
# Input: 2-3 competing picks with grades
# Output: winner + one-paragraph justification

## Usage in pipeline

# Grade all picks (parallel, fast):
#   SWARM_MODE=cli SWARM_MODELS="cli:llama" ./swarm-call.sh "$(cat grade-prompt.txt)" out/

# Direct improvement (single, thoughtful):
#   ./cli-llm.sh nemotron "$(cat director-prompt.txt)" out/

# Synthesize claims (parallel, fast):
#   ./cli-llm.sh llama "Extract the central claim in one sentence: $output" out/

## Temperature recommendations
# Grader: 0.3 (consistency)
# Synthesizer: 0.2 (extraction, minimal creativity)
# Director: 0.7 (strategic thinking benefits from some variance)
# Verifier-auditor: 0.3 (precision)
# Tiebreaker: 0.5 (decisive but reasoned)

## Limitations
# - Both CLI models currently route to the same Pollinations backend.
#   Role differentiation is via prompt engineering, not model weights.
# - If FreeLLMAPI adds true upstream providers for these models, re-test
#   and update role assignments based on actual capability differences.
# - Pollinations has no system role; prepend instructions to user message.
