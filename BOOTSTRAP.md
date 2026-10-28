# BOOTSTRAP — one upload, whole architecture, no hand-holding

Read this first. You were given one file (swarmzero-bundle.md) and you
are building the entire SwarmZero system from it, autonomously. The
user's only jobs are: create the accounts in Step 0 in one batch, then
paste the keys once. After that, do everything below without asking
again. Stop only if a verification check fails, and then say exactly
which check failed and what it printed. Never print, log, or commit a
key. Keys live in the environment only, never in a file inside the repo
(.env and *api_key* are git-ignored).

## Step 0 — the user creates accounts, all at once

Do this batch before anything else. Each account unlocks one part; the
table says which, so the user understands why they are making it.

| # | Account | What it gives | Needed for | If skipped |
|---|---------|---------------|------------|------------|
| 1 | Groq — console.groq.com, create an API key | Free-tier access to gpt-oss-20b (cheap) and gpt-oss-120b (strong) | Every model call in the system | Nothing runs. This one is mandatory. |
| 2 | Meta Model API — api.meta.ai, create an API key | Muse Spark 1.3 as an independent verifier | Real verifier output in the demo | Demo still runs, but the verifier falls back to Groq 20b grading its own tier. Optional but recommended. |
| 3 | GitHub — github.com, any account | A place to clone this repo and push changes | Getting the code, keeping it public | The bundle file alone is enough to start, but there is nowhere to save work. |
| 4 | A machine with Python 3 and bash | Somewhere to run the code (a laptop, a VM, a server) | Running anything at all | The user can only read about the system, not run it. |

That is the whole batch. No other accounts, no paid tiers, no credit
card for the mandatory path. Groq's free tier is the $0 engine.

## Step 1 — lay out the parts

Copy the bundle's files into a working directory, or clone the repo.
Then build the architecture in this order. Each part states what it is,
why it exists, and what breaks without it.

### 1. swarm-call.sh — the model caller. Mandatory.

What: sends one prompt to Groq's OpenAI-compatible endpoint and
collects the answer. Parallel calls, retries on 429/5xx with backoff,
exact-repeat cache so identical prompts cost zero calls, per-model
health tracking with redelegation to healthy substitutes.

Why: every other part calls models through this. It is the only file
that touches the network.

Wire it: set `FREELLMAPI_BASE_URL=https://api.groq.com/openai` and
`FREELLMAPI_API_KEY=<the Groq key>`. Note the base URL has no trailing
`/v1`: the script appends `/v1/chat/completions` itself.

Without it: no model calls, no demo, no benchmarks. Nothing else runs.

### 2. live_demo.py — the judge loop. Mandatory for the demo.

What: the user types any task. gpt-oss-20b answers, a verifier grades
PASS/FAIL, a FAIL escalates to gpt-oss-120b for a revision (max 2).
The trajectory (model, verdict, verifier backend, cost) is the receipt.

Why: this is the product. It proves cheap-first routing with
verified-fail escalation on unseen input.

Wire it: it finds swarm-call.sh on its own — the repo-local copy when
there is no vault, the vault path on the original machine. It reads
`MODEL_API_KEY`/`META_API_KEY` for the Meta verifier, else uses the
Groq cheap verifier. No extra setup.

Without it: the caller works, but there is no loop and no demo.

### 3. prompt_filter.py + proxy_server.py — the cost guard. Recommended.

What: a drop-in OpenAI-compatible proxy. Point any client at
http://localhost:8080/v1 and every request gets cheap-first
downgrade unless a verified failure is attached, an output cap, repeat
caching, and blind-retry blocking, before it reaches upstream.

Why: it is the answer to "why not just call the strong model every
time." It enforces the cheap-first rule mechanically instead of by
discipline.

Wire it: `UPSTREAM_BASE_URL=https://api.groq.com/openai/v1` (here the
`/v1` IS included, because the proxy appends `/chat/completions`) and
`UPSTREAM_API_KEY=<the same Groq key>`.

Without it: the demo still works, but nothing stops a client from
burning strong-model calls on easy tasks.

### 4. meta_client.py — the independent verifier. Optional.

What: grades a task/candidate through Muse Spark 1.3 on the Meta
Model API, returning PASS/FAIL plus one sentence and a metered cost.

Why: a verifier from a different provider family is stronger evidence
than the cheap tier grading itself.

Wire it: set `MODEL_API_KEY` (or `META_API_KEY`). Without either key,
live_demo.py silently uses the Groq cheap verifier and names that
backend in its output, so the receipt stays honest.

Without it: the loop still closes, with a weaker verifier.

### 5. routing_ledger.py + routing_ledger.csv — the receipt book. Recommended.

What: records each routing decision (model, score or verdict, reason)
so the cheap/strong split is auditable after a run.

Why: a demo without a ledger is a story; a demo with one is evidence.

Without it: everything still runs, but nothing is recorded.

### 6. benchmark-v5 + benchmark-v4 — the measured evidence. Recommended.

What: frozen task sets with mechanical checkers, plus the scripts that
ran them (score-v5.py, verify-v5.py, mech-v5.py, xrevise.py). The
v5 win: revise 0.583 vs plain 0.083 on 12 tasks where the strong model
deterministically fails.

Why: this is the number the demo's claim rests on. New runs re-measure
it instead of re-asserting it.

Without it: the demo runs, but its core claim is unverified on the
user's own machine.

### 7. make-bundle.sh + swarmzero-bundle.md — portability itself.

What: regenerates the single-file bundle from the repo, so the whole
system stays one upload away from a fresh session.

Why: this file is how the user got here. Keep it fresh with
`./make-bundle.sh` after any change, then commit and push.

## Step 2 — verify, autonomously

Run these checks in order. Do not declare success until all pass.

1. `./swarm-call.sh --check` — backend reachable. Expect an UP line
   for the Groq base URL. If it says DOWN, the base URL or the key is
   wrong; say so and stop.
2. One cheap call: `SWARM_MODELS=openai/gpt-oss-20b ./swarm-call.sh
   "Reply with exactly the word OK." /tmp/smoke` — expect OK in the
   output file. If it fails, report the http code from timings.tsv.
3. One demo task: `python3 live_demo.py --task "Write a Python
   function that returns the sum of a list, plus a one-line test call"`
   — expect a final PASS and a trajectory naming the verifier backend.
4. Optional, if a Meta key was provided: confirm a trajectory shows
   backend `meta:muse-spark-1.3` and a nonzero cost under $0.01.

## Step 3 — done state

The system is up when: the smoke call returns OK, the demo task ends
PASS, and the user can open `python3 live_demo.py --serve` and type
their own task in a browser. Tell the user exactly that, plus the
commands to re-run the demo and the proxy, and nothing else. Do not
re-explain the architecture unprompted; it is in this file.

## Rules that never relax

- Never print, log, or commit a key. Never ask the user to paste a key
  into the repo, a chat message that will be stored, or a shared doc.
- Never claim a check passed that was not run. The fallback verifier,
  the 512-to-2048 cap raise, and the LLM-judge honesty label in
  live_demo.py are part of the system, not footnotes to hide.
- If the user has no Groq key, stop at Step 0. There is no $0 path
  around it, and inventing one would be lying about the architecture.
