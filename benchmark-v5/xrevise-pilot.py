#!/usr/bin/env python3
"""xrevise-pilot.py — pilot: does the revise loop's revision step transfer
across models?

Novelty: v5 tested same-model revise (120b generates, 120b revises). Nobody
tested whether a different model revising is better/worse: is revision skill
model-specific, or does a strong reviser fix a weak generator's output?

Arms (generator -> reviser), <=2 revisions, thrash-guard, mechanical verifier:
  120b->120b   baseline (same as v5 revise)
  20b->120b    weak generator, strong reviser
  120b->20b    strong generator, weak reviser
  20b->20b     weak generator, weak reviser (control)

Tasks: 4 hard v5-kept2 tasks where 120b deterministically failed.
Interleaved per task inside one window (drift protocol). Task-level verdicts;
n=4 is a pilot, not a significance test — it decides whether a full run
is worth the calls.

Usage:
  MECH_KEPT_JSON=tasks-v5-kept2.json python3 xrevise-pilot.py --outdir results/xrevise-pilot-<stamp>
Writes results.json and REPORT.md.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")

_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)

KEPT_JSON = os.environ.get("MECH_KEPT_JSON", "tasks-v5-kept.json")
TASKS = ["c1-expr-eval-3", "p9-sexpr-let", "q3-zebra-5", "c10-sexpr"]
FULL_TASKS = ["p3-unicode-json", "p8-bizdays", "p9-sexpr-let", "q3-zebra-5",
              "q8-mastermind", "r5-fifty-words", "r8-no-e", "c1-expr-eval-3",
              "c10-sexpr", "l1-knights-6", "w2-word-count", "w5-lines-words"]
ARMS = [("openai/gpt-oss-120b", "openai/gpt-oss-120b"),
        ("openai/gpt-oss-20b", "openai/gpt-oss-120b"),
        ("openai/gpt-oss-120b", "openai/gpt-oss-20b"),
        ("openai/gpt-oss-20b", "openai/gpt-oss-20b")]
PLAIN_MODEL = "openai/gpt-oss-120b"

REVISE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Study the failure detail carefully and produce a corrected answer. "
    "Follow the original instructions exactly. Do not repeat your previous "
    "answer unchanged."
)


def safe_name(model):
    return model.replace("/", "_").replace(":", "_")


def load_task(tid):
    tasks = json.load(open(os.path.join(BASE, KEPT_JSON)))["tasks"]
    for t in tasks:
        if t["id"] == tid:
            return t
    raise ValueError(f"unknown kept task: {tid}")


def call_model(model, prompt):
    fd, ppath = tempfile.mkstemp(prefix="xrev-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="xrev-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = model
        env["SWARM_CACHE"] = "0"
        env["SWARM_REDELEGATE"] = "0"
        env["SWARM_FALLBACK"] = ""
        env["SWARM_SKIP_UNHEALTHY"] = "0"
        env["SWARM_TIMEOUT"] = "180"
        r = subprocess.run(
            [SWARM_CALL, "-f", ppath, outdir],
            env=env, capture_output=True, text=True, timeout=300,
        )
        txt_path = os.path.join(outdir, safe_name(model) + ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(ppath):
            os.unlink(ppath)
        shutil.rmtree(outdir, ignore_errors=True)


def verify(task, answer):
    if not answer or not answer.strip():
        return False, "no output (transport failure or empty response)"
    try:
        ok, detail = score_v5.SCORERS[task["scorer"]](answer, task)
    except Exception as e:
        return False, f"scorer crashed: {type(e).__name__}: {e}"
    return bool(ok), detail


def norm_answer(a):
    return re.sub(r"\s+", " ", a.strip().lower())


def run_xrevise(task, gen_model, rev_model, max_revisions=2):
    attempts = []
    seen = set()
    prompt = task["prompt"]
    answer = None
    for n in range(1 + max_revisions):
        model = gen_model if n == 0 else rev_model
        if n > 0:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
        answer = call_model(model, prompt)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "model": model,
                         "pass": passed, "detail": detail,
                         "repeated": repeated})
        if passed:
            break
        if repeated:
            break
    return answer, {"gen": gen_model, "rev": rev_model,
                    "attempts": attempts, "calls": len(attempts),
                    "final_pass": attempts[-1]["pass"] if attempts else False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--full", action="store_true",
                    help="run all 12 kept tasks plus a plain-120b arm")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    window_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tasks = FULL_TASKS if args.full else TASKS
    results = {"window_start_utc": window_start, "tasks": tasks,
               "arms": [{"gen": g, "rev": r} for g, r in ARMS],
               "cells": []}
    for tid in tasks:
        task = load_task(tid)
        if args.full:
            # plain arm: single 120b call, doubles as per-window canary
            print(f"[{tid}] plain 120b", flush=True)
            answer = call_model(PLAIN_MODEL, task["prompt"])
            passed, detail = verify(task, answer)
            results["cells"].append({"task": tid, "gen": "plain",
                                     "rev": None, "final_pass": passed,
                                     "trajectory": [passed], "calls": 1,
                                     "attempt_models": [PLAIN_MODEL]})
            with open(os.path.join(args.outdir, "results.json"), "w") as f:
                json.dump(results, f, indent=1)
        for gen_model, rev_model in ARMS:
            print(f"[{tid}] {safe_name(gen_model)} -> {safe_name(rev_model)}",
                  flush=True)
            answer, meta = run_xrevise(task, gen_model, rev_model)
            cell = {"task": tid, "gen": gen_model, "rev": rev_model,
                    "final_pass": meta["final_pass"],
                    "trajectory": [a["pass"] for a in meta["attempts"]],
                    "calls": meta["calls"],
                    "attempt_models": [a["model"] for a in meta["attempts"]]}
            results["cells"].append(cell)
            with open(os.path.join(args.outdir, "results.json"), "w") as f:
                json.dump(results, f, indent=1)
    # report
    lines = ["# Cross-model revision pilot" + (" (FULL 12-task run)" if args.full else ""),
             "",
             f"Window start (UTC): {window_start}", "",
             "| task | plain | 120b->120b | 20b->120b | 120b->20b | 20b->20b |",
             "|---|---|---|---|---|---|"]
    for tid in tasks:
        row = [tid]
        cell_order = [("plain", None)] + list(ARMS) if args.full else list(ARMS)
        for gen_model, rev_model in cell_order:
            c = next(x for x in results["cells"]
                     if x["task"] == tid and x["gen"] == gen_model
                     and x["rev"] == rev_model)
            traj = "".join("1" if p else "0" for p in c["trajectory"])
            row.append(f"{'PASS' if c['final_pass'] else 'fail'} ({traj})")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["",
              "Trajectory notation: 1=pass, 0=fail per attempt in order."]
    with open(os.path.join(args.outdir, "REPORT.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
