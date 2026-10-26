#!/usr/bin/env python3
"""Deterministic scorer for the swarm capability benchmark.

Reads tasks.json + results/raw/<task>/<safe_model>.txt, writes
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


def score_exact_year(text, expected):
    years = re.findall(r"\b\d{4}\b", text)
    ok = years == [expected]
    return ok, f"years_found={years}"


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


def _strip_fences(text):
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def score_code_tests(text, tests):
    code = _strip_fences(text)
    harness = (
        "import json,sys\n"
        + code
        + "\n"
        + "tests=" + repr(tests) + "\n"
        + "results=[]\n"
        + "for n,want in tests:\n"
        + "    try:\n"
        + "        got=is_prime(n)\n"
        + "        results.append(bool(got) is bool(want))\n"
        + "    except Exception as e:\n"
        + "        results.append(False)\n"
        + "print(json.dumps(results))\n"
    )
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(harness)
            path = f.name
        try:
            r = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=15,
            )
        finally:
            os.unlink(path)
    except subprocess.TimeoutExpired:
        return False, "timeout after 15s"
    except Exception as e:
        return False, f"harness error: {type(e).__name__}"
    if r.returncode != 0:
        return False, f"code crashed: {r.stderr.strip()[:200]}"
    try:
        results = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return False, f"bad harness output: {r.stdout[:200]!r}"
    ok = all(results) and len(results) == len(tests)
    return ok, f"tests_passed={sum(results)}/{len(results)}"


def score_json_exact(text, expected):
    t = _strip_fences(text)
    try:
        obj = json.loads(t)
    except Exception as e:
        return False, f"JSON parse failed: {type(e).__name__}"
    ok = obj == expected
    return ok, f"parsed={obj!r}"


def score_mechanical_constraints(text):
    t = text.strip()
    detail = []
    ok = True
    if "," in t:
        ok = False
        detail.append("contains comma")
    terms = len(re.findall(r"[.!?]", t))
    if terms != 3:
        ok = False
    detail.append(f"terminators={terms}")
    words = len(t.split())
    if not (0 < words < 40):
        ok = False
    detail.append(f"words={words}")
    return ok, ", ".join(detail)


def score_fact_substrings(text):
    low = text.lower()
    checks = {
        "length": ("9289" in low) or ("9,289" in low),
        "began_1891": "1891" in low,
        "timezones": ("8 time zone" in low)
        or (("eight" in low) and ("time zone" in low)),
    }
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, ("all present" if ok else f"missing={missing}")


def score_day_name(text, expected):
    norm = re.sub(r"[^a-z]", "", text.lower())
    ok = norm == expected
    return ok, f"normalized={norm!r}"


def score_label_sequence(text, expected):
    labels = []
    for line in text.strip().splitlines():
        m = re.search(r"\b(FRUIT|VEGETABLE|GRAIN)\b", line.upper())
        labels.append(m.group(1) if m else None)
    ok = labels == expected
    return ok, f"labels={labels}"


UNCERTAINTY_MARKERS = [
    "not aware", "no record", "can't verify", "cannot verify",
    "don't have", "do not have", "unable to verify", "no such",
    "doesn't exist", "does not exist", "unsure", "uncertain",
    "fabricat", "not real", "no evidence", "i'm not sure",
    "i am not sure", "unknown", "cannot confirm", "can't confirm",
    "no credible", "fictional", "hypothetical", "i don't know",
    "i do not know", "no study", "never happened", "misinformation",
    "doesn't appear", "does not appear", "there was no", "there is no",
    "there were no", "haven't conducted", "hasn't conducted",
    "can't provide that information", "cannot provide that information",
]


def score_uncertainty_expressed(text):
    low = re.sub(r"[*_`#>]", "", text.lower())
    low = low.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    low = re.sub(r"\s+", " ", low)
    hit = next((m for m in UNCERTAINTY_MARKERS if m in low), None)
    ok = hit is not None
    return ok, (f"marker={hit!r}" if ok else "no uncertainty expressed")


SCORERS = {
    "exact_year": lambda t, task: score_exact_year(t, task["expected"]),
    "numeric_exact": lambda t, task: score_numeric_exact(t, task["expected"]),
    "numeric_tolerance": lambda t, task: score_numeric_tolerance(
        t, task["expected"], task.get("tolerance", 1e-4)),
    "code_tests": lambda t, task: score_code_tests(t, task["hidden_tests"]),
    "json_exact": lambda t, task: score_json_exact(t, task["expected"]),
    "mechanical_constraints": lambda t, task: score_mechanical_constraints(t),
    "fact_substrings": lambda t, task: score_fact_substrings(t),
    "day_name": lambda t, task: score_day_name(t, task["expected"]),
    "label_sequence": lambda t, task: score_label_sequence(t, task["expected"]),
    "uncertainty_expressed": lambda t, task: score_uncertainty_expressed(t),
}


def main():
    tasks = json.load(open(os.path.join(BASE, "tasks.json")))["tasks"]
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
    # quick console summary
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
