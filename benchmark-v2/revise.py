#!/usr/bin/env python3
"""Generate-verify-revise loop for SwarmZero benchmark tasks.

Pipeline: generator model produces an answer -> the task's MECHANICAL
scorer from benchmark/score.py checks it (no LLM-as-judge) -> on failure
the generator gets the scorer's failure detail and one revision attempt.

Usage:
    python3 revise.py --task 02-multi-step-arithmetic
    python3 revise.py --task 03-code-prime --generator openai/gpt-oss-20b \
        --verifier openai/gpt-oss-120b --max-revisions 2

Notes:
- The generator defaults to the SMALL model (gpt-oss-20b) to prove the
  loop adds value beyond the generator alone.
- --verifier is accepted for interface compatibility (a future LLM-judge
  mode); verification today is purely mechanical via score.py.
- The API key is resolved in-memory from the local server DB and passed
  only via the subprocess environment. It is never printed or logged.
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmark")
sys.path.insert(0, BENCH)
from score import SCORERS  # noqa: E402  (mechanical scorers only)

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
    """One prompt through swarm-call.sh, restricted to a single model.

    Returns (answer_text, returncode). SWARM_CACHE=1 keeps repeat prompts
    free; revision prompts differ from the original so they always re-probe.
    """
    safe = model.replace("/", "_").replace(":", "_")
    fd, ppath = tempfile.mkstemp(prefix="revise-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="revise-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = model
        env["SWARM_CACHE"] = "1"
        env["SWARM_SKIP_UNHEALTHY"] = "1"
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
    tasks = json.load(open(os.path.join(BENCH, "tasks.json")))["tasks"]
    for t in tasks:
        if t["id"] == task_id:
            return t
    raise ValueError(f"unknown task id: {task_id}")


def verify(task, answer):
    """Mechanical verification. Returns (passed: bool, detail: str)."""
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


def run(task_id, generator, max_revisions):
    task = load_task(task_id)
    key = resolve_key()
    attempts = []
    prompt = task["prompt"]
    calls_used = 0
    for n in range(1 + max_revisions):
        answer, rc = call_model(generator, prompt, key)
        calls_used += 1
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
    return {
        "task": task_id,
        "generator": generator,
        "scorer": task["scorer"],
        "max_revisions": max_revisions,
        "attempts": attempts,
        "final_pass": final["pass"],
        "final_answer": final["answer"],
        "revisions_used": len(attempts) - 1,
        "total_calls": calls_used,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, help="task id from tasks.json")
    ap.add_argument("--generator", default="openai/gpt-oss-20b")
    ap.add_argument("--verifier", default="openai/gpt-oss-120b",
                    help="reserved for future LLM-judge mode; "
                         "verification is mechanical today")
    ap.add_argument("--max-revisions", type=int, default=2)
    ap.add_argument("--out", default=None,
                    help="write result JSON here (default: "
                         "benchmark-v2/results/<task>_<gen>.json)")
    args = ap.parse_args()

    result = run(args.task, args.generator, args.max_revisions)
    out = args.out
    if out is None:
        resdir = os.path.join(HERE, "results")
        os.makedirs(resdir, exist_ok=True)
        safe_gen = args.generator.replace("/", "_").replace(":", "_")
        out = os.path.join(resdir, f"{args.task}_{safe_gen}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({
        "task": result["task"],
        "generator": result["generator"],
        "final_pass": result["final_pass"],
        "revisions_used": result["revisions_used"],
        "total_calls": result["total_calls"],
        "per_attempt": [(a["attempt"], a["pass"], a["detail"])
                        for a in result["attempts"]],
        "result_file": out,
    }, indent=2))


if __name__ == "__main__":
    main()
