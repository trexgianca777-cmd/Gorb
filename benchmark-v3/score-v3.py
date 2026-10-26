#!/usr/bin/env python3
"""Deterministic scorer for the swarm capability benchmark v3.

Reads tasks-v3.json + results/raw/<task>/<safe_model>.txt, writes
results/scores.json. No LLM-as-judge anywhere.

Conventions match score-v2.py: scorers return (ok, detail). Code tasks run
in a subprocess harness with a timeout.
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


def score_numeric_tolerance(text, expected, tol):
    nums = _numbers(text)
    ok = any(abs(n - expected) <= tol for n in nums)
    return ok, f"numbers_found={nums}"


def score_token_strict(text, expected):
    norm = re.sub(r"[^a-z]", "", text.lower())
    ok = norm == expected
    return ok, f"normalized={norm!r}"


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


EVAL_BAN = re.compile(r"\beval\s*\(|\bexec\s*\(|\bast\.")


def score_code_function_numeric_tests(text, tests, func_name, tol, ban_eval):
    code = _strip_fences(text)
    if ban_eval and EVAL_BAN.search(code):
        return False, "banned construct: eval/exec/ast used"
    driver = (
        "import json,sys\n" + code + "\n"
        + "tests=" + repr(tests) + "\n"
        + "results=[]\n"
        + "for arg,want in tests:\n"
        + "    try:\n"
        + f"        got=float({func_name}(arg))\n"
        + "        results.append(abs(got-float(want))<=" + repr(tol) + ")\n"
        + "    except Exception:\n"
        + "        results.append(False)\n"
        + "print(json.dumps(results))\n"
    )
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    ok = all(payload) and len(payload) == len(tests)
    return ok, f"tests_passed={sum(payload)}/{len(payload)}"


def _norm_deep(v):
    if isinstance(v, (list, tuple)):
        return [_norm_deep(x) for x in v]
    return v


def score_code_function_deep_tests(text, tests, func_name):
    code = _strip_fences(text)
    driver = (
        "import json,sys\n" + code + "\n"
        + "tests=" + repr(tests) + "\n"
        + "def norm(v):\n"
        + "    return [norm(x) for x in v] if isinstance(v,(list,tuple)) else v\n"
        + "results=[]\n"
        + "for arg,want in tests:\n"
        + "    try:\n"
        + f"        got=norm({func_name}(arg))\n"
        + "        results.append(got==norm(want))\n"
        + "    except Exception:\n"
        + "        results.append(False)\n"
        + "print(json.dumps(results))\n"
    )
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    ok = all(payload) and len(payload) == len(tests)
    return ok, f"tests_passed={sum(payload)}/{len(payload)}"


def _sentences(text):
    return [s.strip() for s in re.split(r"[.!?]", text.strip()) if s.strip()]


def score_constraint_alpha_sentences(text):
    t = text.strip()
    detail = []
    ok = True
    sents = _sentences(t)
    if len(sents) != 6:
        ok = False
    detail.append(f"sentences={len(sents)}")
    for i, s in enumerate(sents[:6]):
        m = re.search(r"[a-zA-Z]", s)
        want = "abcdef"[i]
        if not m or m.group(0).lower() != want:
            ok = False
            detail.append(f"sentence_{i+1}_starts_wrong")
    detail.append("starts=A-F" if ok else "starts=wrong")
    words = re.findall(r"[a-z0-9]+", t.lower())
    seen = set()
    dups = set()
    for w in words:
        if w in seen:
            dups.add(w)
        seen.add(w)
    if dups:
        ok = False
    detail.append(f"dup_words={sorted(dups) if dups else 0}")
    n42 = len(re.findall(r"\b42\b", t))
    if n42 != 1:
        ok = False
    detail.append(f"count_42={n42}")
    if "," in t:
        ok = False
        detail.append("contains comma")
    return ok, ", ".join(detail)


def score_constraint_paragraphs(text):
    t = text.strip()
    detail = []
    ok = True
    paras = [p for p in re.split(r"\n\s*\n", t) if p.strip()]
    if len(paras) != 3:
        ok = False
    detail.append(f"paragraphs={len(paras)}")
    counts = [len(_sentences(p)) for p in paras]
    if counts != [2, 3, 2]:
        ok = False
    detail.append(f"sentences_per_para={counts}")
    finals = []
    for p in paras:
        for s in _sentences(p):
            toks = re.findall(r"[a-z0-9]+", s.lower())
            if toks:
                finals.append(toks[-1])
    if len(set(finals)) != len(finals) or len(finals) != 7:
        ok = False
    detail.append(f"final_words={len(finals)},distinct={len(set(finals))}")
    reds = len(re.findall(r"\bred\b", t.lower()))
    if reds != 3:
        ok = False
    detail.append(f"red_count={reds}")
    if "!" in t:
        ok = False
        detail.append("contains '!'")
    return ok, ", ".join(detail)


SCORERS = {
    "numeric_tolerance": lambda t, task: score_numeric_tolerance(
        t, task["expected"], task.get("tolerance", 1e-4)),
    "token_strict": lambda t, task: score_token_strict(t, task["expected"]),
    "code_function_numeric_tests": lambda t, task: score_code_function_numeric_tests(
        t, task["hidden_tests"], task["function"],
        task.get("tolerance", 1e-6), task.get("ban_eval", False)),
    "code_function_deep_tests": lambda t, task: score_code_function_deep_tests(
        t, task["hidden_tests"], task["function"]),
    "constraint_alpha_sentences": lambda t, task: score_constraint_alpha_sentences(t),
    "constraint_paragraphs": lambda t, task: score_constraint_paragraphs(t),
}


def main():
    tasks = json.load(open(os.path.join(BASE, "tasks-v3.json")))["tasks"]
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
