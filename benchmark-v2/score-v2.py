#!/usr/bin/env python3
"""Deterministic scorer for the swarm capability benchmark v2.

Reads tasks-v2.json + results/raw/<task>/<safe_model>.txt, writes
results/scores.json. No LLM-as-judge anywhere.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "results", "raw")


def read_raw(task_id, safe_model):
    p = os.path.join(RAW, task_id, f"{safe_model}.txt")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def _numbers(text):
    out = []
    for m in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def score_numeric_exact(text, expected):
    nums = _numbers(text)
    ok = any(abs(n - expected) < 0.01 for n in nums)
    return ok, f"numbers_found={nums}"


def score_numeric_tolerance(text, expected, tol):
    nums = _numbers(text)
    ok = any(abs(n - expected) <= tol for n in nums)
    return ok, f"numbers_found={nums}"


def score_liar_letter(text, expected):
    norm = re.sub(r"[^a-z]", "", text.lower())
    ok = norm == expected
    return ok, f"normalized={norm!r}"


def score_constraint_counts(text):
    t = text.strip()
    sents = [s.strip() for s in re.split(r"[.!?]", t) if s.strip()]
    detail = []
    ok = True
    if len(sents) != 5:
        ok = False
    detail.append(f"sentences={len(sents)}")
    long = [len(s.split()) for s in sents if len(s.split()) >= 10]
    if long:
        ok = False
    detail.append(f"sentences_with_10+_words={len(long)}")
    low = t.lower()
    if "water" in low:
        ok = False
        detail.append("contains 'water'")
    blues = len(re.findall(r"\bblue\b", low))
    if blues != 2:
        ok = False
    detail.append(f"blue_count={blues}")
    return ok, ", ".join(detail)


def score_line_constraints(text):
    t = text.strip()
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    detail = []
    ok = True
    if len(lines) != 4:
        ok = False
    detail.append(f"lines={len(lines)}")
    bad_start = [l for l in lines if not re.match(r"(?i)^red\b", l)]
    if bad_start:
        ok = False
    detail.append(f"lines_not_starting_red={len(bad_start)}")
    if "," in t:
        ok = False
        detail.append("contains comma")
    words = t.split()
    last = re.sub(r"[^a-zA-Z]", "", words[-1]).lower() if words else ""
    if last != "sunset":
        ok = False
    detail.append(f"last_word={last!r}")
    return ok, ", ".join(detail)


def _strip_fences(text):
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _run_harness(driver, timeout=20):
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(driver)
            path = f.name
        try:
            r = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        finally:
            os.unlink(path)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, f"harness error: {type(e).__name__}"
    if r.returncode != 0:
        return False, f"code crashed: {r.stderr.strip()[:200]}"
    try:
        return True, json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return False, f"bad harness output: {r.stdout[:200]!r}"


def score_code_function_tests(text, tests, func_name):
    code = _strip_fences(text)
    driver = (
        "import json,sys\n" + code + "\n"
        + "tests=" + repr(tests) + "\n"
        + "results=[]\n"
        + "for arg,want in tests:\n"
        + "    try:\n"
        + f"        got={func_name}(arg)\n"
        + "        results.append(bool(got) is bool(want))\n"
        + "    except Exception:\n"
        + "        results.append(False)\n"
        + "print(json.dumps(results))\n"
    )
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    results = payload
    ok = all(results) and len(results) == len(tests)
    return ok, f"tests_passed={sum(results)}/{len(results)}"


def score_code_class_tests(text, scenarios):
    code = _strip_fences(text)
    driver = (
        "import json,sys\n" + code + "\n"
        + "scenarios=" + repr(scenarios) + "\n"
        + "step_results=[]\n"
        + "fatal=None\n"
        + "for sc in scenarios:\n"
        + "    try:\n"
        + "        c=LRUCache(sc['capacity'])\n"
        + "        for step in sc['steps']:\n"
        + "            op=step[0]\n"
        + "            if op=='put':\n"
        + "                c.put(*step[1])\n"
        + "            else:\n"
        + "                got=c.get(*step[1])\n"
        + "                step_results.append(got==step[2])\n"
        + "    except Exception as e:\n"
        + "        fatal=str(e)[:100]\n"
        + "        break\n"
        + "print(json.dumps({'fatal':fatal,'steps':step_results}))\n"
    )
    ok_run, payload = _run_harness(driver, timeout=20)
    if not ok_run:
        return False, payload
    if payload["fatal"]:
        return False, f"code crashed: {payload['fatal']}"
    results = payload["steps"]
    total_steps = sum(
        1 for sc in scenarios for s in sc["steps"] if s[0] == "get"
    )
    ok = all(results) and len(results) == total_steps and total_steps > 0
    return ok, f"get_checks_passed={sum(results)}/{len(results)}"


CORRECTION_MARKERS = [
    "moon", "no human", "never", "hasn't", "has not", "no one",
    "incorrect", "false premise", "did not walk", "didn't walk",
    "not mars", "nobody has",
]


def score_premise_correction(text):
    low = re.sub(r"[*_`#>]", "", text.lower())
    low = low.replace("\u2019", "'").replace("\u2018", "'")
    low = re.sub(r"\s+", " ", low)
    hit = next((m for m in CORRECTION_MARKERS if m in low), None)
    ok = hit is not None
    return ok, (f"marker={hit!r}" if ok else "no correction of the Mars premise")


SCORERS = {
    "numeric_exact": lambda t, task: score_numeric_exact(t, task["expected"]),
    "numeric_tolerance": lambda t, task: score_numeric_tolerance(
        t, task["expected"], task.get("tolerance", 1e-4)),
    "liar_letter": lambda t, task: score_liar_letter(t, task["expected"]),
    "constraint_counts": lambda t, task: score_constraint_counts(t),
    "line_constraints": lambda t, task: score_line_constraints(t),
    "code_function_tests": lambda t, task: score_code_function_tests(
        t, task["hidden_tests"], task["function"]),
    "code_class_tests": lambda t, task: score_code_class_tests(
        t, task["hidden_tests"]),
    "premise_correction": lambda t, task: score_premise_correction(t),
}


def main():
    tasks = json.load(open(os.path.join(BASE, "tasks-v2.json")))["tasks"]
    scores = {}
    for task in tasks:
        tid = task["id"]
        tdir = os.path.join(RAW, tid)
        per_model = {}
        if os.path.isdir(tdir):
            for fn in sorted(os.listdir(tdir)):
                if not fn.endswith(".txt"):
                    continue
                model = fn[:-4]
                text = read_raw(tid, model)
                if text is None:
                    per_model[model] = {"pass": False, "detail": "no output file"}
                    continue
                try:
                    ok, detail = SCORERS[task["scorer"]](text, task)
                except Exception as e:
                    ok, detail = False, f"scorer crashed: {type(e).__name__}: {e}"
                per_model[model] = {"pass": bool(ok), "detail": detail}
        scores[tid] = per_model
    out = os.path.join(BASE, "results", "scores.json")
    with open(out, "w") as f:
        json.dump(scores, f, indent=2)
    models = sorted({m for t in scores.values() for m in t})
    print(f"{'MODEL':45s} " + " ".join(f"{t['id'][:2]}" for t in tasks))
    for m in models:
        row = []
        for t in tasks:
            r = scores[t["id"]].get(m)
            row.append("." if r is None else ("P" if r["pass"] else "F"))
        print(f"{m:45s} " + " ".join(row))
    total = sum(1 for t in scores.values() for r in t.values() if r["pass"])
    denom = sum(len(t) for t in scores.values())
    print(f"\nOverall pass rate: {total}/{denom} = {total/denom:.1%}" if denom else "no results")


if __name__ == "__main__":
    main()
