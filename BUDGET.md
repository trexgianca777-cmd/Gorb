# SwarmZero Meta Model API budget (dive 16 exercise)

Credit pool: $150 in Meta Model API credits, if they post to the account.
Event window: Oct 26 to Nov 4, 2026 (10 days). Daily cap: $15/day.

## Rate card used (Muse Spark standard tier, dive 16)

- Input: $1.25 per million tokens
- Output: $4.25 per million tokens
- Cached input: $0.15 per million tokens

## Per-piece costs

- One verifier call (about 2,000 input tokens, 200 output tokens):
  0.002 * 1.25 + 0.0002 * 4.25 = $0.00335
- One $15 day buys about 4,400 such verifier calls.
- A full revise loop on 100 tasks, three calls each, costs about $1.00.

## Kill rule

Projected spend above the $15 daily cap means stop and rerun on the $0
Groq roster. No loop runs without a ceiling.

## Status (checked Oct 24, 2026)

- The $150 credits are confirmed in the waiver but no claim mechanism is
  stated on the organizer pages, so whether they have posted is still a
  logged-in check for the user. Do not run metered calls until that check
  passes.
- `meta_client.py` in this directory implements the verifier call and
  returns token counts and cost per call. It makes no call without a key.
