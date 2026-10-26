# Role Prompts — copy/paste templates for specialized CLI agents
# Usage: ./cli-llm.sh <llama|nemotron> "$(cat prompts/role-grader.txt)" out/

## role-grader.txt (cli:llama, temp 0.3)
Grade this stock pick on a 1-5 scale for each criterion. Be concise and consistent.

PICK:
[PASTE PICK HERE]

CRITERIA:
1. Evidence quality (1-5): Are claims backed by specific data?
2. Arithmetic correctness (1-5): Does the math check out?
3. Thesis coherence (1-5): Does the logic hold together?
4. Risk awareness (1-5): Are downsides acknowledged?

Output format (exact):
Evidence: X/5 - one sentence
Arithmetic: X/5 - one sentence
Thesis: X/5 - one sentence
Risk: X/5 - one sentence
Overall: PASS/FAIL

## role-synthesizer.txt (cli:llama, temp 0.2)
Extract the single central claim from this model output. One sentence. No commentary, no evaluation, just the claim.

OUTPUT:
[PASTE MODEL OUTPUT HERE]

Your response: "[MODEL_NAME]: [one-sentence claim]"

## role-director.txt (cli:nemotron, temp 0.7)
You are directing a multi-model stock-picking swarm. Analyze the failure data and recommend improvements.

FAILURE LEDGER SUMMARY:
[PASTE swarm-failures.csv summary]

CURRENT PROMPT:
[PASTE current prompt]

GRADE DISTRIBUTION:
[PASTE grade summary]

Rank the top 3 interventions by expected failure-recovery. For each:
1. What to change (one sentence)
2. Which failure category it addresses
3. Expected impact (high/medium/low)

Be specific and actionable. No vague suggestions.

## role-verifier-auditor.txt (cli:nemotron, temp 0.3)
Audit this verification result. The automated verifier flagged issues; determine if the flags are correct and if any issues were missed.

PICK:
[PASTE PICK HERE]

VERIFIER FLAGS:
[PASTE flags]

For each flag: AGREE or DISAGREE with one-sentence reason.
Then: Any MISSED issues? List them or say "none."

## role-tiebreaker.txt (cli:llama, temp 0.5)
Two models disagree on the best stock pick. Choose one. Be decisive.

PICK A:
[PASTE PICK A + grade]

PICK B:
[PASTE PICK B + grade]

Your response:
Winner: [A or B]
Why: [one paragraph, no hedging]
