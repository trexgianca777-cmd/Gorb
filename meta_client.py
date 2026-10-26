"""SwarmZero metered verifier via the Meta Model API (dive 16 exercise).

Reads the key from MODEL_API_KEY (META_API_KEY also accepted as a
fallback). Makes no call on import. Returns PASS/FAIL plus token counts
so every verdict can be logged against the $15/day budget in BUDGET.md.

Usage:
    export MODEL_API_KEY=...
    python3 meta_client.py "Task: sort a list." "sorted([3,1,2]) == [1,2,3]"
"""

import json
import os
import sys

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
# Standard-tier rate card from dive 16, per million tokens.
RATE_IN = 1.25
RATE_OUT = 4.25


def cost_usd(in_tokens, out_tokens):
    return in_tokens / 1e6 * RATE_IN + out_tokens / 1e6 * RATE_OUT


def verify(task, candidate_output, client=None):
    """One metered verifier call. Returns a dict with verdict, tokens, cost."""
    if client is None:
        from openai import OpenAI

        api_key = os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY")
        if not api_key:
            raise RuntimeError("MODEL_API_KEY (or META_API_KEY) is not set")
        client = OpenAI(base_url=BASE_URL, api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a grader. Reply with PASS or FAIL and one sentence.",
            },
            {
                "role": "user",
                "content": f"Task: {task}\nCandidate output: {candidate_output}",
            },
        ],
        max_tokens=64,
    )
    text = resp.choices[0].message.content.strip()
    verdict = "PASS" if text.upper().startswith("PASS") else "FAIL"
    u = resp.usage
    return {
        "verdict": verdict,
        "detail": text,
        "in_tokens": u.prompt_tokens,
        "out_tokens": u.completion_tokens,
        "cost_usd": round(cost_usd(u.prompt_tokens, u.completion_tokens), 5),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: meta_client.py <task> <candidate output>")
        sys.exit(2)
    print(json.dumps(verify(sys.argv[1], sys.argv[2]), indent=2))
