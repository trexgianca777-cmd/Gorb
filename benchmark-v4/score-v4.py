#!/usr/bin/env python3
"""Deterministic scorer + aggregator for the swarm capability benchmark v4.

Layout:
    tasks-v4.json
    results/raw/<mechanism>/<task>/rep<1..3>/<safe_model>.txt

Mechanisms: plain (gpt-oss-120b x3 reps), route (per-task routed model x3),
            revise (120b generator + mechanical verifier, <=2 revisions, x3).

Every scorer is mechanical (python string/code checks). No LLM-as-judge.

Conventions carried from score-v3.py: scorers return (ok, detail). Code
tasks run in a subprocess harness with a timeout.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "results", "raw")


def read_raw(mechanism, task_id, rep, safe_model):
    p = os.path.join(RAW, mechanism, task_id, f"rep{rep}", f"{safe_model}.txt")
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


def score_digits_strict(text, expected):
    digits = re.sub(r"\D", "", text)
    want = re.sub(r"\D", "", expected)
    ok = digits == want and len(digits) > 0
    return ok, f"digits={digits!r}"


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


def _deep_driver(code, tests_repr, func_name, unpack):
    call = f"{func_name}(*arg)" if unpack else f"{func_name}(arg)"
    return (
        "import json,sys\n" + code + "\n"
        + "tests=" + tests_repr + "\n"
        + "def norm(v):\n"
        + "    if isinstance(v,(list,tuple)):\n"
        + "        return [norm(x) for x in v]\n"
        + "    if isinstance(v,dict):\n"
        + "        return {k:norm(x) for k,x in v.items()}\n"
        + "    return v\n"
        + "results=[]\n"
        + "for arg,want in tests:\n"
        + "    try:\n"
        + f"        got=norm({call})\n"
        + "        results.append(got==norm(want))\n"
        + "    except Exception:\n"
        + "        results.append(False)\n"
        + "print(json.dumps(results))\n"
    )


def _check_banned(code, task):
    """Reject banned constructs/imports declared on the task."""
    if task.get("ban_eval") and EVAL_BAN.search(code):
        return "banned construct: eval/exec/ast used"
    for mod in task.get("ban_modules", []):
        if re.search(r"(?m)^\s*(import|from)\s+" + re.escape(mod) + r"\b", code):
            return f"banned import: {mod}"
    return None


def score_code_function_deep_tests(text, tests, func_name, task=None):
    code = _strip_fences(text)
    banned = _check_banned(code, task or {})
    if banned:
        return False, banned
    driver = _deep_driver(code, repr(tests), func_name, False)
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    ok = all(payload) and len(payload) == len(tests)
    return ok, f"tests_passed={sum(payload)}/{len(payload)}"


def score_code_function_deep_tests_args(text, tests, func_name, task=None):
    """Like deep tests, but each test arg is a list unpacked as *arg."""
    code = _strip_fences(text)
    banned = _check_banned(code, task or {})
    if banned:
        return False, banned
    driver = _deep_driver(code, repr(tests), func_name, True)
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    ok = all(payload) and len(payload) == len(tests)
    return ok, f"tests_passed={sum(payload)}/{len(payload)}"


def _sentences(text):
    return [s.strip() for s in re.split(r"[.!?]", text.strip()) if s.strip()]


def score_constraint_alpha(text, task):
    """Parameterized version of v3's alpha-sentences check.

    Task fields: n_sentences (int), starts (str of letters, one per
    sentence), unique_words (bool), word_counts ({word: exact_count}),
    banned_chars (list).
    """
    t = text.strip()
    detail = []
    ok = True
    n = task.get("n_sentences", 6)
    starts = task.get("starts", "abcdef")
    sents = _sentences(t)
    if len(sents) != n:
        ok = False
    detail.append(f"sentences={len(sents)}/{n}")
    for i, s in enumerate(sents[:n]):
        m = re.search(r"[a-zA-Z]", s)
        want = starts[i].lower() if i < len(starts) else "?"
        if not m or m.group(0).lower() != want:
            ok = False
            detail.append(f"sentence_{i+1}_starts_wrong")
    if task.get("unique_words"):
        words = re.findall(r"[a-z0-9]+", t.lower())
        seen, dups = set(), set()
        for w in words:
            if w in seen:
                dups.add(w)
            seen.add(w)
        if dups:
            ok = False
        detail.append(f"dup_words={sorted(dups) if dups else 0}")
    for w, cnt in task.get("word_counts", {}).items():
        nfound = len(re.findall(r"\b" + re.escape(w) + r"\b", t.lower()))
        if nfound != cnt:
            ok = False
        detail.append(f"count_{w}={nfound}/{cnt}")
    for ch in task.get("banned_chars", []):
        if ch in t:
            ok = False
            detail.append(f"contains {ch!r}")
    return ok, ", ".join(detail)


def score_constraint_paragraphs(text, task):
    """Parameterized version of v3's paragraph check.

    Task fields: n_paragraphs (int), sentences_per (list),
    first_words_distinct (bool), word_counts (dict), banned_chars (list).
    """
    t = text.strip()
    detail = []
    ok = True
    np_ = task.get("n_paragraphs", 3)
    paras = [p for p in re.split(r"\n\s*\n", t) if p.strip()]
    if len(paras) != np_:
        ok = False
    detail.append(f"paragraphs={len(paras)}/{np_}")
    want_counts = task.get("sentences_per", [2, 3, 2])
    counts = [len(_sentences(p)) for p in paras]
    if counts != want_counts:
        ok = False
    detail.append(f"sentences_per_para={counts}")
    if task.get("first_words_distinct"):
        firsts = []
        for p in paras:
            for s in _sentences(p):
                toks = re.findall(r"[a-z0-9]+", s.lower())
                if toks:
                    firsts.append(toks[0])
        if len(set(firsts)) != len(firsts) or len(firsts) != sum(want_counts):
            ok = False
        detail.append(f"first_words={len(firsts)},distinct={len(set(firsts))}")
    for w, cnt in task.get("word_counts", {}).items():
        nfound = len(re.findall(r"\b" + re.escape(w) + r"\b", t.lower()))
        if nfound != cnt:
            ok = False
        detail.append(f"count_{w}={nfound}/{cnt}")
    for ch in task.get("banned_chars", []):
        if ch in t:
            ok = False
            detail.append(f"contains {ch!r}")
    return ok, ", ".join(detail)


def score_constraint_list(text, task):
    """Bullet-list constraint check.

    Task fields: n_lines (int), line_prefix (str), odd_start (letter for
    lines 1,3,5...), even_start (letter for lines 2,4,6...), max_len (int),
    word_counts (dict).
    """
    t = text.strip()
    detail = []
    ok = True
    n = task.get("n_lines", 7)
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) != n:
        ok = False
    detail.append(f"lines={len(lines)}/{n}")
    pref = task.get("line_prefix", "- ")
    odd, even = task.get("odd_start", "A"), task.get("even_start", "B")
    maxlen = task.get("max_len", 40)
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith(pref):
            ok = False
            detail.append(f"line_{i+1}_no_prefix")
            continue
        rest = s[len(pref):].strip()
        m = re.search(r"[a-zA-Z]", rest)
        want = odd if i % 2 == 0 else even
        if not m or m.group(0).lower() != want.lower():
            ok = False
            detail.append(f"line_{i+1}_starts_wrong")
        if len(s) > maxlen:
            ok = False
            detail.append(f"line_{i+1}_too_long")
    for w, cnt in task.get("word_counts", {}).items():
        nfound = len(re.findall(r"\b" + re.escape(w) + r"\b", t.lower()))
        if nfound != cnt:
            ok = False
        detail.append(f"count_{w}={nfound}/{cnt}")
    return ok, ", ".join(detail)


SCORERS = {
    "numeric_tolerance": lambda t, task: score_numeric_tolerance(
        t, task["expected"], task.get("tolerance", 1e-4)),
    "token_strict": lambda t, task: score_token_strict(t, task["expected"]),
    "digits_strict": lambda t, task: score_digits_strict(t, task["expected"]),
    "code_function_numeric_tests": lambda t, task: score_code_function_numeric_tests(
        t, task["hidden_tests"], task["function"],
        task.get("tolerance", 1e-6), task.get("ban_eval", False)),
    "code_function_deep_tests": lambda t, task: score_code_function_deep_tests(
        t, task["hidden_tests"], task["function"], task),
    "code_function_deep_tests_args": lambda t, task: score_code_function_deep_tests_args(
        t, task["hidden_tests"], task["function"], task),
    "constraint_alpha": lambda t, task: score_constraint_alpha(t, task),
    "constraint_paragraphs": lambda t, task: score_constraint_paragraphs(t, task),
    "constraint_list": lambda t, task: score_constraint_list(t, task),
}


def score_all():
    """Score every cell: mechanism x task x rep -> bool. Returns dict."""
    tasks = json.load(open(os.path.join(BASE, "tasks-v4.json")))["tasks"]
    results = {}
    if os.path.isdir(RAW):
        for mech in sorted(os.listdir(RAW)):
            mechdir = os.path.join(RAW, mech)
            if not os.path.isdir(mechdir):
                continue
            results[mech] = {}
            for task in tasks:
                tid = task["id"]
                results[mech][tid] = {}
                tdir = os.path.join(mechdir, tid)
                if not os.path.isdir(tdir):
                    continue
                for repdir in sorted(os.listdir(tdir)):
                    if not repdir.startswith("rep"):
                        continue
                    rdir = os.path.join(tdir, repdir)
                    rep = repdir[3:]  # "rep1" -> "1"
                    for fn in sorted(os.listdir(rdir)):
                        if not fn.endswith(".txt") or fn == "model.txt":
                            continue
                        model = fn[:-4]
                        text = read_raw(mech, tid, rep, model)
                        if text is None:
                            results[mech][tid][(repdir, model)] = (
                                False, "no output file")
                            continue
                        try:
                            ok, detail = SCORERS[task["scorer"]](text, task)
                        except Exception as e:
                            ok, detail = False, \
                                f"scorer crashed: {type(e).__name__}: {e}"
                        results[mech][tid][(repdir, model)] = (bool(ok), detail)
    return results


def main():
    tasks = json.load(open(os.path.join(BASE, "tasks-v4.json")))["tasks"]
    results = score_all()
    out = os.path.join(BASE, "results", "scores.json")
    serial = {m: {tid: {f"{r}/{mod}": {"pass": ok, "detail": d}
                        for (r, mod), (ok, d) in cells.items()}
                  for tid, cells in tdict.items()}
              for m, tdict in results.items()}
    with open(out, "w") as f:
        json.dump(serial, f, indent=2)
    tids = [t["id"] for t in tasks]
    print(f"{'MECH':8s} {'MODEL':45s} " +
          " ".join(t[:2] for t in tids))
    agg = {}
    for mech, tdict in results.items():
        task_fracs = {}
        for task in tasks:
            tid = task["id"]
            cells = tdict.get(tid, {})
            passes = sum(1 for ok, _ in cells.values() if ok)
            total = len(cells)
            task_fracs[tid] = (passes, total)
        fracs = [p / n for p, n in task_fracs.values() if n > 0]
        agg[mech] = (sum(fracs) / len(fracs) if fracs else 0.0, task_fracs)
        row = []
        for task in tasks:
            p, n = task_fracs[task["id"]]
            row.append(f"{p}/{n}" if n else "-")
        models = sorted({m for tid in tdict for _, m in tdict[tid]})
        print(f"{mech:8s} {','.join(models)[:45]:45s} " + " ".join(row))
    print()
    for mech, (mean, _) in agg.items():
        print(f"{mech}: mean per-task pass rate = {mean:.3f}")
    return agg


if __name__ == "__main__":
    main()
