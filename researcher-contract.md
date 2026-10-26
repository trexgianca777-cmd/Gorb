# Researcher Evidence Contract

Append this to any researcher brief. It exists because A/B runs ab-1/ab-2
(2026-10-15) proved stronger models hallucinate evidence pointers (papers,
numbers, dates) just as confidently as weak ones. The fix is not a stronger
model; it is a tagging discipline the model can follow and code can check.

## The tags

Every SPECIFIC claim must carry exactly one tag, placed immediately after
the claim:

- `[V]` — VERIFIED. You checked it against material given in THIS brief, or
  it is arithmetic you show step-by-step in your output (checkable in-output).
  Never use [V] for anything recalled from training data.
- `[U]` — UNVERIFIED. Recalled from training data or general knowledge. A
  lead, not a fact. The reader must treat it as unconfirmed.
- `[I]` — INFERENCE. Your interpretation, projection, or judgment derived
  from other claims. Not a fact about the world.

## What counts as SPECIFIC (must be tagged)

- Any number with $, %, x/×, or units: "$18.56" [V], "grew 12%" [U], "3x" [I]
- Any calendar date or year: "2024" [U], "Q3 2023" [U]
- Any named paper, study, article, or report title: '"Irrational Exuberance"' [U]
- Any URL
- Any named person quoted as an authority: 'Shiller argues...' [U]

## What does NOT need a tag

- Your own stated opinions and recommendations (they are yours; label the
  section clearly, e.g. "My judgment:").
- Logical connectives and hedges ("therefore", "suggests", "likely").
- Claims already given verbatim in the brief (cite "brief" instead).

## Rules

1. No tag = violation. A mechanical checker flags untagged specific claims,
   and the critic treats them as unsupported by construction.
2. When unsure, use [U]. A wrong [V] is worse than an honest [U].
3. Do not tag everything in sight. Opinions, hedges, and brief-given facts
   stay untagged; over-tagging is noise and will be flagged too.
4. If the brief gives you no checkable material, most of your specific
   claims should be [U]. That is correct and expected.

## Example

"Revenue grew 12% in 2024 [U] (company filings, not in brief). At a 15x
multiple [I], fair value is roughly $18.56 [V] (15 x 1.2374 = 18.56, shown
above). Shiller's 'Irrational Exuberance' [U] makes the same multiple
argument for late-cycle equities."
