#!/usr/bin/env python3
"""live_demo.py — SwarmZero live judge-driven loop (option 1).

The judge types any task. Nothing is pre-baked: the cheap tier answers,
a verifier grades it, and a FAIL escalates to the strong tier for a
revision. The trajectory (model, verdict, cost) is the receipt.

Pipeline, all $0 unless a Meta key is present:
  - Generator:  Groq gpt-oss-20b via swarm-call.sh (vault key resolved
    in-memory inside the swarm-call subprocess, never printed).
  - Verifier:  Muse Spark 1.3 via meta_client.py IF MODEL_API_KEY or
    META_API_KEY is set (metered, cost logged). Otherwise a Groq cheap
    verifier (gpt-oss-20b) grading with the same PASS/FAIL prompt.
    The output always names which verifier backend ran.
  - Reviser:   Groq gpt-oss-120b via swarm-call.sh, only on FAIL.

Honesty label: for arbitrary judge-typed tasks the verifier is an LLM
judge (PASS/FAIL plus one sentence), not a mechanical checker. The
v5 benchmark win used mechanical checkers on frozen tasks; this demo
proves the loop structure runs live on unseen input, not that every
verdict is mechanically certain.

Usage:
  CLI:  python3 live_demo.py --task "Write a Python function that sums a list"
  Web:  python3 live_demo.py --serve [--port 8765]
        then open http://localhost:8765 and type a task.
  Env:  LIVE_MAX_REVISIONS (default 2), SWARM_MAX_TOKENS (default 2048).
        Cap raised 2026-10-26 (event week): 512 truncated code answers
        in the Oct 25 escalation test, so code tasks now get 2048.
"""

import html
import json
import os
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
# Portable paths (2026-10-28): on the original machine the swarm caller
# and key vault live under ~/workspace/freellmapi. Anywhere else, use the
# repo-local swarm-call.sh and a plain FREELLMAPI_API_KEY from the
# environment — no vault required. Vault path wins when it exists, so
# existing setups are unchanged.
_FREELLMAPI_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")
SWARM_CALL = (_FREELLMAPI_CALL if os.path.exists(_FREELLMAPI_CALL)
              else os.path.join(HERE, "swarm-call.sh"))
VAULT = os.path.expanduser("~/workspace/freellmapi/vault/vault.sh")
CHEAP = "openai/gpt-oss-20b"
STRONG = "openai/gpt-oss-120b"
MAX_REVISIONS = int(os.environ.get("LIVE_MAX_REVISIONS", "2"))


def _safe(model):
    return model.replace("/", "_").replace(":", "_")


def swarm_call(model, prompt, system=None):
    """One single-model call through swarm-call.sh. Returns text or None."""
    outdir = tempfile.mkdtemp(prefix="live-demo-")
    if os.path.exists(VAULT):
        cmd = ["bash", "-c",
               f'. "{VAULT}"; swarm_vault_load || exit 2; '
               f'exec "{SWARM_CALL}" "$@"',
               "live-demo", prompt, outdir]
    else:
        # No vault: swarm-call.sh reads FREELLMAPI_API_KEY and
        # FREELLMAPI_BASE_URL straight from the environment.
        cmd = ["bash", SWARM_CALL, prompt, outdir]
    env = dict(os.environ)
    env["SWARM_MODELS"] = model
    env["SWARM_MAX_TOKENS"] = os.environ.get("SWARM_MAX_TOKENS", "2048")
    env["SWARM_TIMEOUT"] = os.environ.get("SWARM_TIMEOUT", "120")
    if system:
        env["SWARM_SYSTEM"] = system
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True,
                              text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    txt_path = os.path.join(outdir, _safe(model) + ".txt")
    if os.path.exists(txt_path):
        with open(txt_path) as f:
            return f.read().strip() or None
    return None


def verify(task, candidate):
    """Returns (verdict, detail, backend, cost_usd)."""
    if os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY"):
        sys.path.insert(0, HERE)
        from meta_client import verify as meta_verify
        r = meta_verify(task, candidate)
        return r["verdict"], r["detail"], "meta:muse-spark-1.3", r["cost_usd"]
    verdict_text = swarm_call(
        CHEAP,
        f"Task: {task}\nCandidate output: {candidate}\n"
        "Reply with PASS or FAIL and one sentence. No other text.",
        system="You are a grader. Reply with PASS or FAIL and one sentence.")
    if not verdict_text:
        return "FAIL", "verifier call failed", "groq:gpt-oss-20b", 0.0
    first = verdict_text.strip().split("\n")[0]
    verdict = "PASS" if first.upper().startswith("PASS") else "FAIL"
    return verdict, verdict_text.strip()[:300], "groq:gpt-oss-20b", 0.0


def est_tokens(text):
    return max(1, (len(text) + 3) // 4)


def run_loop(task):
    """Runs the verifier-gated loop. Returns the trajectory dict."""
    steps = []
    t0 = time.time()
    answer = swarm_call(
        CHEAP,
        f"Complete this task. Keep the answer short.\nTask: {task}",
        system="You answer tasks concisely. No preamble.")
    if not answer:
        return {"task": task, "final": "ERROR",
                "detail": "cheap-tier call failed",
                "steps": steps, "elapsed_s": round(time.time() - t0, 1)}
    verdict, detail, backend, cost = verify(task, answer)
    steps.append({"model": CHEAP, "role": "generate", "verdict": verdict,
                  "verifier": backend, "cost_usd": cost,
                  "answer": answer[:2000]})
    revisions = 0
    while verdict == "FAIL" and revisions < MAX_REVISIONS:
        revisions += 1
        revised = swarm_call(
            STRONG,
            f"Revise this answer so it passes. Verdict detail: {detail}\n"
            f"Task: {task}\nPrevious answer: {answer}\n"
            "Return only the revised answer.",
            system="You revise answers to satisfy a grader. Return only "
                   "the revised answer.")
        if not revised:
            break
        answer = revised
        verdict, detail, backend, cost = verify(task, answer)
        steps.append({"model": STRONG, "role": "revise", "verdict": verdict,
                      "verifier": backend, "cost_usd": cost,
                      "answer": answer[:2000]})
    total_cost = round(sum(s["cost_usd"] for s in steps), 5)
    return {"task": task, "final": verdict, "detail": detail,
            "steps": steps, "total_cost_usd": total_cost,
            "elapsed_s": round(time.time() - t0, 1)}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>SwarmZero live loop</title></head><body>
<h1>SwarmZero live loop</h1>
<p>Type any task. Cheap tier answers, verifier grades, FAIL escalates
to the strong tier. Verdicts on arbitrary tasks are LLM-judge calls,
not mechanical checks.</p>
<form method="post" action="/run">
<input name="task" size="80" placeholder="e.g. Write a Python function that sums a list, with a test">
<button type="submit">Run</button></form>
{body}</body></html>"""


def render(traj):
    rows = []
    for i, s in enumerate(traj["steps"], 1):
        rows.append(
            f"<h3>Step {i}: {html.escape(s['model'])} "
            f"({html.escape(s['role'])}) → {html.escape(s['verdict'])}</h3>"
            f"<p>Verifier: {html.escape(s['verifier'])} · "
            f"cost: ${s['cost_usd']}</p>"
            f"<pre>{html.escape(s['answer'])}</pre>")
    return (f"<h2>Final: {html.escape(traj['final'])}</h2>"
            f"<p>{html.escape(traj.get('detail', ''))} · "
            f"{traj.get('elapsed_s', '?')}s · "
            f"total cost ${traj.get('total_cost_usd', 0)}</p>"
            + "".join(rows))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send(PAGE.format(body=""))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(n).decode())
        task = (fields.get("task") or [""])[0].strip()
        if not task:
            self._send(PAGE.format(body="<p>Empty task.</p>"))
            return
        traj = run_loop(task)
        run_dir = os.path.join(HERE, "live-runs")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, f"run-{int(time.time())}.json"),
                  "w") as f:
            json.dump(traj, f, indent=2)
        self._send(PAGE.format(body=render(traj)))

    def _send(self, body):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    args = sys.argv[1:]
    if "--serve" in args:
        port = 8765
        if "--port" in args:
            port = int(args[args.index("--port") + 1])
        print(f"SwarmZero live loop on http://localhost:{port} "
              "(Ctrl-C to stop)")
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    elif "--task" in args:
        task = args[args.index("--task") + 1]
        print(json.dumps(run_loop(task), indent=2))
    else:
        print("usage: live_demo.py --task \"...\" | --serve [--port N]")
        sys.exit(2)


if __name__ == "__main__":
    main()
