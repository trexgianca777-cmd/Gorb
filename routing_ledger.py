"""SwarmZero routing ledger (dive 17 exercise, verifier extension done).

Routes each task by a simple difficulty rule, then runs the verifier
step: an easy task whose first answer scores below VERIFIER_THRESHOLD
is flipped to escalated and rerouted to the large model. Hard tasks
are already escalated by difficulty, so the verifier does not
double-count them.

FIRST_ANSWER_SCORES are stub inputs for the demo, not measured
verifier output. Replace them with a real verifier call (see
meta_client.py) before presenting the numbers as results.

Run: python3 routing_ledger.py
"""

import csv

TASKS = [
    ("sort a list", "easy"),
    ("prove a lemma about routing", "hard"),
    ("summarize a paragraph", "easy"),
    ("debug a race condition", "hard"),
]

# Stub first-answer scores, for the demo only. Threshold 0.70.
FIRST_ANSWER_SCORES = {
    "sort a list": 0.92,
    "prove a lemma about routing": 0.45,
    "summarize a paragraph": 0.55,
    "debug a race condition": 0.38,
}
VERIFIER_THRESHOLD = 0.70

with open("routing_ledger.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["task", "difficulty", "first_model", "verifier_score",
                     "threshold", "model", "escalated", "escalation_reason"])
    counts = {}
    for task, difficulty in TASKS:
        first_model = "gpt-oss-20b" if difficulty == "easy" else "gpt-oss-120b"
        score = FIRST_ANSWER_SCORES[task]
        if difficulty == "hard":
            model, escalated, reason = "gpt-oss-120b", True, "difficulty"
        elif score < VERIFIER_THRESHOLD:
            model, escalated, reason = "gpt-oss-120b", True, "verifier"
        else:
            model, escalated, reason = first_model, False, "none"
        writer.writerow([task, difficulty, first_model, score,
                         VERIFIER_THRESHOLD, model, escalated, reason])
        counts[model] = counts.get(model, 0) + 1

print("wrote routing_ledger.csv")
for model, n in counts.items():
    print(f"{model}: {n}/{len(TASKS)} tasks ({100 * n // len(TASKS)}%)")
