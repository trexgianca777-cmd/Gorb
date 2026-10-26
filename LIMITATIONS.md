# Limitations

What this project is not, and where it breaks. Read before adopting.

## Not a smart router

`swarm-call.sh` fans a prompt out to every model in the roster in parallel.
It does not assess task difficulty, does not route easy tasks to cheap
models, and does not pick the best answer. Model selection, grading, and
synthesis happen in the calling layer (role prompts are provided;
orchestration across roles is the operator's job). If you need automatic
best-answer selection, you need to build it on top.

## Free-tier fragility is the dominant failure mode

The benchmark found infrastructure failures outnumbering capability
failures 10 to 1: rate limits, 502s, a 10-hour Google rate-limit wall, a
broken route, and the local server dying twice. Redelegation and cooldowns
absorb this gracefully, but they do not eliminate it. Expect partial
coverage on any given run. Do not use this for anything where a missed
slot is unacceptable.

## No single model is reliable; the roster is the reliability

Per-model scores range from 10/10 (gpt-oss-120b, gpt-oss-20b, nemotron,
cohere, dots) down to format-abandonment on small models. The system's
reliability comes from redundancy across the roster, not from any one
model. If your provider access collapses to a single model, you inherit
that model's failure modes wholesale — including silent arithmetic errors
(see benchmark/FAILURES.md, F1).

## Numbers from models must be recomputed

F1 in the failure analysis: a model produced `1539.375` instead of `1665`
with full confidence and no hedging. Any pipeline stage that consumes
model-produced numbers (arithmetic, sizing, conversions) must verify them
independently. The grounding contract (researcher-contract.md) tags claims
V/U/I but does not verify arithmetic — that check is on you.

## Calibration is uneven

All tested models avoided confabulating an answer to a fabricated premise,
but quality ranged from premise-correcting through evasive refusal to
redirect-confabulation (inventing a *different* fake study after denying
the first). If you use the critic role, probe for the evasive and redirect
patterns specifically, not just outright confabulation.

## Cache means reruns don't re-probe

`SWARM_CACHE=1` (default) replays exact-repeat prompt+model answers with
zero provider cost. Reruns are cheap but measure nothing new. Set
`SWARM_CACHE=0` when you actually want to probe the model again.

## Localhost and single-machine assumptions

Health state lives in a local JSON file; the API key resolves from a local
DB. There is no distributed locking, no multi-user story, and no
sandboxing of model outputs. Run it on a machine you control, for work you
can inspect.
