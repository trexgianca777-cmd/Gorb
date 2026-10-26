#!/usr/bin/env python3
"""revise-v4.py — generate-verify-revise loop for benchmark v4.

Generator: gpt-oss-120b (default). Verifier: the task's MECHANICAL scorer
from score-v4.py (no LLM-as-judge). <=2 revisions with the scorer's failure
detail fed back. Every call fresh (SWARM_CACHE=0); honest attribution
(SWARM_REDELEGATE=0, SWARM_SKIP_UNHEALTHY=0).

Usage:
    python3 revise-v4.py --task 01-code-evaluator-2 --rep 1 \
        --generator openai/gpt-oss-120b --max-revisions 2 \
        --outdir results/raw/revise/01-code-evaluator-2/rep1

Writes the final answer to <outdir>/<safe_model>.txt and the loop trace to
<outdir>/loop.json.
"""
import argparse
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "sv4", os.path.join(HERE, "score-v4.py"))
sv4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv4)
SCORERS = sv4.SCORERS  # mechanical scorers only

SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")
DB_PATH = os.path.expanduser("~/workspace/freellmapi/server/data/freeapi.db")


def resolve_key():
    """Unified API key from the local server DB. In-memory only."""
    db = sqlite3.connect(DB_PATH)
    try:
        row = db.execute(
            "SELECT value FROM settings WHERE key='unified_api_key'"
        ).fetchone()
    finally:
        db.close()
    if not row or not row[0]:
        raise RuntimeError("no unified API key in local DB")
    return row[0]


def call_model(model, prompt, key):
    """One fresh prompt through swarm-call.sh, restricted to a single model."""
    safe = model.replace("/", "_").replace(":", "_")
    fd, ppath = tempfile.mkstemp(prefix="revise4-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="revise4-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = model
        env["SWARM_CACHE"] = "0"
        env["SWARM_REDELEGATE"] = "0"
        env["SWARM_SKIP_UNHEALTHY"] = "0"
        env["SWARM_STAGGER_SECS"] = "3"
        env["SWARM_TIMEOUT"] = "180"
        env["FREELLMAPI_API_KEY"] = key  # env only, never logged
        r = subprocess.run(
            [SWARM_CALL, "-f", ppath, outdir],
            env=env, capture_output=True, text=True, timeout=300,
        )
        txt_path = os.path.join(outdir, safe + ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="replace") as f:
                return f.read(), r.returncode
        return "", r.returncode
    finally:
        if os.path.exists(ppath):
            os.unlink(ppath)
        shutil.rmtree(outdir, ignore_errors=True)


def load_task(task_id):
    tasks = json.load(open(os.path.join(HERE, "tasks-v4.json")))["tasks"]
    for t in tasks:
        if t["id"] == task_id:
            return t
    raise ValueError(f"unknown task id: {task_id}")


def verify(task, answer):
    if not answer or not answer.strip():
        return False, "no output (transport failure or empty response)"
    try:
        ok, detail = SCORERS[task["scorer"]](answer, task)
    except Exception as e:  # noqa: BLE001
        return False, f"scorer crashed: {type(e).__name__}: {e}"
    return bool(ok), detail


REVISE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Your answer failed because: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Produce a corrected answer. Follow the original instructions exactly."
)


def run(task_id, generator, max_revisions, outdir):
    task = load_task(task_id)
    key = resolve_key()
    attempts = []
    prompt = task["prompt"]
    for n in range(1 + max_revisions):
        answer, rc = call_model(generator, prompt, key)
        passed, detail = verify(task, answer)
        attempts.append({
            "attempt": n + 1,
            "pass": passed,
            "detail": detail,
            "answer": answer,
        })
        if passed:
            break
        if n < max_revisions:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail, answer=answer.strip()
            )
    final = attempts[-1]
    safe = generator.replace("/", "_").replace(":", "_")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, safe + ".txt"), "w",
              encoding="utf-8") as f:
        f.write(final["answer"] or "")
    with open(os.path.join(outdir, "loop.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "task": task_id,
            "generator": generator,
            "scorer": task["scorer"],
            "max_revisions": max_revisions,
            "attempts": attempts,
            "final_pass": final["pass"],
            "revisions_used": len(attempts) - 1,
        }, f, indent=2)
    return {
        "task": task_id,
        "final_pass": final["pass"],
        "revisions_used": len(attempts) - 1,
        "per_attempt": [(a["attempt"], a["pass"], a["detail"])
                        for a in attempts],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True)
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--generator", default="openai/gpt-oss-120b")
    ap.add_argument("--max-revisions", type=int, default=2)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    result = run(args.task, args.generator, args.max_revisions, args.outdir)
    print(json.dumps({"rep": args.rep, **result}, indent=2))


if __name__ == "__main__":
    main()
