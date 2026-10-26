#!/usr/bin/env python3
"""mech-v5.py — mechanism implementations for benchmark v5 cycle 1.

Mechanisms (all use gpt-oss-120b as the base model unless noted):
  bestof5    5 fresh samples; mechanical verifier picks the first passing
             sample. Rep passes iff the picked sample passes.
  revise     120b generator + mechanical verifier, <=2 revisions, with
             thrash-guard: stop early if a new answer repeats a previous
             attempt (normalized); final = last distinct answer. The
             revision prompt carries the full scorer failure detail.
  selfcon    5 fresh samples; majority vote over the extracted canonical
             answer (single-answer scorers only: token/digits/numeric/
             numeric_decimal). Ties or no majority -> fail.

Usage:
  python3 mech-v5.py --mech bestof5 --task <tid> --rep <n> --outdir <dir>
Writes <outdir>/openai_gpt-oss-120b.txt (the mechanism's final answer) and
<outdir>/meta.json (attempt log).

The API key comes from the environment (screen/run scripts load the vault).
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")
MODEL = "openai/gpt-oss-120b"
SAFE = "openai_gpt-oss-120b"

_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)


KEPT_JSON = os.environ.get("MECH_KEPT_JSON", "tasks-v5-kept.json")

def load_task(tid):
    tasks = json.load(open(os.path.join(BASE, KEPT_JSON)))["tasks"]
    for t in tasks:
        if t["id"] == tid:
            return t
    raise ValueError(f"unknown kept task: {tid}")


def call_model(prompt):
    """One fresh 120b call. Returns answer text ('' on transport failure)."""
    fd, ppath = tempfile.mkstemp(prefix="v5-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="v5-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = MODEL
        env["SWARM_CACHE"] = "0"
        env["SWARM_REDELEGATE"] = "0"
        env["SWARM_FALLBACK"] = ""
        env["SWARM_SKIP_UNHEALTHY"] = "0"
        env["SWARM_TIMEOUT"] = "180"
        r = subprocess.run(
            [SWARM_CALL, "-f", ppath, outdir],
            env=env, capture_output=True, text=True, timeout=300,
        )
        txt_path = os.path.join(outdir, SAFE + ".txt")
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
    except Exception as e:  # noqa: BLE001
        return False, f"scorer crashed: {type(e).__name__}: {e}"
    return bool(ok), detail


def norm_answer(a):
    return re.sub(r"\s+", " ", a.strip().lower())


REVISE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Study the failure detail carefully and produce a corrected answer. "
    "Follow the original instructions exactly. Do not repeat your previous "
    "answer unchanged."
)


def run_bestof5(task):
    samples = []
    answers = []
    for i in range(5):
        a = call_model(task["prompt"])
        answers.append(a)
        passed, detail = verify(task, a)
        samples.append({"sample": i + 1, "pass": passed, "detail": detail})
        if passed:
            return a, {"mechanism": "bestof5", "samples": samples,
                       "picked": i + 1, "calls": i + 1}
    return answers[-1], {"mechanism": "bestof5", "samples": samples,
                         "picked": None, "calls": 5}


def run_revise(task, max_revisions=2):
    attempts = []
    seen = set()
    prompt = task["prompt"]
    answer = None
    for n in range(1 + max_revisions):
        answer = call_model(prompt)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "pass": passed,
                         "detail": detail, "repeated": repeated})
        if passed:
            break
        if repeated:
            # thrash-guard: stop, keep the last distinct answer
            break
        if n < max_revisions:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
    return answer, {"mechanism": "revise", "attempts": attempts,
                    "calls": len(attempts)}


SINGLE_ANSWER_SCORERS = {"token_strict", "digits_strict", "numeric_tolerance",
                         "numeric_decimal"}


def extract_canonical(task, answer):
    sc = task["scorer"]
    if sc == "token_strict":
        return re.sub(r"[^a-z]", "", answer.lower()) or None
    if sc == "digits_strict":
        d = re.sub(r"\D", "", answer)
        return d or None
    if sc in ("numeric_tolerance", "numeric_decimal"):
        m = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", answer)
        return m[0].replace(",", "") if m else None
    return None


def run_selfcon(task):
    if task["scorer"] not in SINGLE_ANSWER_SCORERS:
        return "", {"mechanism": "selfcon", "skipped": "not single-answer",
                    "calls": 0}
    votes = []
    raws = []
    for _ in range(5):
        a = call_model(task["prompt"])
        raws.append(a)
        votes.append(extract_canonical(task, a))
    counted = Counter(v for v in votes if v is not None)
    if not counted:
        return "", {"mechanism": "selfcon", "votes": votes, "winner": None,
                    "calls": 5}
    top, cnt = counted.most_common(1)[0]
    # strict majority required; ties fail
    if cnt < 3 or list(counted.values()).count(cnt) > 1:
        return "", {"mechanism": "selfcon", "votes": votes, "winner": None,
                    "calls": 5}
    # return the first raw sample carrying the winning canonical answer
    for a, v in zip(raws, votes):
        if v == top:
            return a, {"mechanism": "selfcon", "votes": votes,
                       "winner": top, "calls": 5}
    return "", {"mechanism": "selfcon", "votes": votes, "winner": None,
                "calls": 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mech", required=True,
                    choices=["bestof5", "revise", "selfcon"])
    ap.add_argument("--task", required=True)
    ap.add_argument("--rep", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    task = load_task(args.task)
    if args.mech == "bestof5":
        final, meta = run_bestof5(task)
    elif args.mech == "revise":
        final, meta = run_revise(task)
    else:
        final, meta = run_selfcon(task)
    meta.update({"task": args.task, "rep": args.rep})
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, SAFE + ".txt"), "w") as f:
        f.write(final or "NO-OUTPUT")
    with open(os.path.join(args.outdir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    passed, detail = verify(task, final)
    print(json.dumps({"task": args.task, "rep": args.rep, "mech": args.mech,
                      "final_pass": passed, "detail": detail,
                      "calls": meta.get("calls")}))
    import time
    time.sleep(3)


if __name__ == "__main__":
    main()
