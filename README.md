# SwarmZero — $0 multi-agent orchestration on open-weights models

A delegation-first orchestration layer that fans work out across free-tier
and open model APIs at zero inference cost. Per-model health tracking
reroutes around rate limits and outages so the swarm degrades gracefully
instead of dying.

## How it works

- **swarm-call.sh** — parallel multi-model caller. Sends one prompt to every
  model in the roster concurrently and collects each output to its own file.
  Per-model cooldowns (honors server `Retry-After`), hourly call-load
  tracking, and automatic redelegation: an unhealthy model's slots move to
  the healthiest substitute (`SWARM_REDELEGATE=0` restores skip behavior).
  Idempotent retries with capped backoff; exact-repeat prompts hit a local
  cache with zero provider cost.
- **TOKEN-PROTOCOL.md** — compact-output contract: summaries to stdout, data
  to files, targeted reads only. Keeps context-window waste down across
  multi-agent runs.
- **researcher-contract.md + contract_check.py** — grounding contract:
  researchers tag every claim `[V]`erified, `[U]`ncertain, or `[I]`nferred;
  the checker flags untagged claims automatically.
- **cynic-prompt.md / cynic-audit.sh** — adversarial audit role that
  stress-tests outputs against failure modes before they ship.
- **role-prompts.md / swarm-roles.md / swarm-roles-full.md** — grader,
  synthesizer, and researcher role definitions; grading and synthesis are
  split into separate passes.
- **SWARM.md** — the full operating manual: free-tier rate-limit handling,
  idempotent retries, and one bounded pass per task.
- **cli-llm.sh** — free anonymous-endpoint fallback when API tiers fail.
- **benchmark/** — internal evaluation suite (tasks.json, run/score scripts)
  used to measure swarm output quality.

## Run it

```bash
# Backend: any OpenAI-compatible server (the original ran on a local
# FreeLLMAPI instance serving Groq's open-weights models).
FREELLMAPI_API_KEY=<your key, environment only> ./swarm-call.sh "prompt" [outdir]
```

`./swarm-call.sh --check` reports backend status without spending anything.
Keys come from the environment only — never files, never arguments, never
logs (enforced in SWARM.md).

## Design principles

1. Zero inference cost: free tiers, open weights, no paid APIs.
2. Degrade, don't die: health tracking + redelegation absorb outages.
3. Compact by contract: the token protocol bounds every pass.
4. Claims carry receipts: every research claim is tagged V/U/I.

## Live demo + cost-guard proxy (built 2026-10-25)

- **live_demo.py** — the judge-driven loop. Judge types any task;
  gpt-oss-20b answers, a verifier grades PASS/FAIL, FAIL escalates to
  gpt-oss-120b for a revision (max 2). Verifier is Muse Spark 1.3
  via meta_client.py when a Meta key is set, else a Groq cheap
  verifier; the output names which backend ran. Verdicts on arbitrary
  tasks are LLM-judge calls, not mechanical checks.
  `python3 live_demo.py --serve` (http://localhost:8765) or
  `python3 live_demo.py --task "..."`.
- **proxy_server.py** — prompt_filter as a drop-in OpenAI-compatible
  proxy. Point a client at http://localhost:8080/v1 and every request
  gets cheap-first routing, prefix pinning, history trim, output cap,
  repeat caching, and blind-retry blocking before it reaches upstream.
  Send `X-Verified-Fail: true` to keep the strong model.
  Upstream from UPSTREAM_BASE_URL / UPSTREAM_API_KEY.
