#!/usr/bin/env python3
"""mech-v6.py — revise-loop improvement candidates and feedback-style variants.

Baseline: v5 run_revise (terse detail, <=2 revisions, answer-repeat thrash-guard).
Candidates (each a full revise loop unless noted):
  ce  counterexample-rich failure detail (first failing input/output/expected
      triple for code tasks; pinpointed failing unit for constraint tasks;
      no leakage for single-answer tasks)
  mh  multi-hypothesis: 2 distinct fix framings per round (minimal patch vs
      rewrite), verify both, keep the better. <=2 rounds (<=5 calls).
  kb  keep-best: identical loop to baseline, but final = best attempt by
      progress score instead of last answer.
  ad  adaptive budget + divergence: up to 4 revisions; continue while the
      fail detail keeps changing; on identical detail, one divergence-nudge
      attempt then stop.
  sv  strict verifier: revision guided by original verifier + extra hidden
      edge tests; final judged by the ORIGINAL scorer only.

Feedback styles for the novelty study (full loops, <=2 revisions, differ
only in the revision prompt):
  style_terse, style_ce, style_socratic, style_diverge

Usage:
  python3 mech-v6.py --mech baseline|ce|mh|kb|ad|sv|style_terse|style_ce|style_socratic|style_diverge \
      --task <tid> --rep <n> --outdir <dir>
Writes openai_gpt-oss-120b.txt (final answer) and meta.json (attempt log with
per-call token chars).

Env: MECH_KEPT_JSON selects the kept-task file (default tasks-v5-kept.json);
FREELLMAPI_API_KEY must be in the environment.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time

V5 = os.path.expanduser("~/workspace/hackathon/swarmzero-staging/benchmark-v5")
BASE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "mech_v5", os.path.join(V5, "mech-v5.py"))
mech_v5 = importlib.util.module_from_spec(_spec)
_old_argv = sys.argv
sys.argv = ["mech-v5-stub"]
try:
    _spec.loader.exec_module(mech_v5)
except SystemExit:
    pass
finally:
    sys.argv = _old_argv

load_task = mech_v5.load_task
call_model = mech_v5.call_model
verify = mech_v5.verify
norm_answer = mech_v5.norm_answer
score_v5 = mech_v5.score_v5
REVISE_TEMPLATE = mech_v5.REVISE_TEMPLATE

SINGLE_ANSWER = {"token_strict", "digits_strict", "numeric_tolerance",
                 "numeric_decimal"}
CODE_SCORERS = {"code_function_numeric_tests", "code_function_deep_tests",
                "code_function_deep_tests_args", "code_function_raises_tests"}


# ------------------------------------------------------------ progress

def progress_score(task, answer, detail):
    """0..1 progress estimate from a fail detail. Crashes/timeouts -> 0."""
    if not answer or not answer.strip():
        return 0.0
    d = detail or ""
    if re.search(r"crash|timeout|no output|scorer crashed|banned", d, re.I):
        return 0.0
    pairs = re.findall(r"(\w+)=(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", d)
    vals = []
    for _, a, b in pairs:
        try:
            a, b = float(a), float(b)
        except ValueError:
            continue
        if b > 0:
            vals.append(min(a, b) / max(a, b) if max(a, b) > 0 else 0.0)
    if vals:
        return sum(vals) / len(vals)
    return 0.0


# ------------------------------------------------- counterexample detail

def _strip_fences(text):
    return score_v5._strip_fences(text)


def _run_harness(driver):
    return score_v5._run_harness(driver)


def _first_failing_case(task, answer):
    """Return (input_repr, want_repr, got_repr) for the first failing hidden
    test, or None. Never reveals anything beyond one test case."""
    code = _strip_fences(answer)
    if score_v5._check_banned(code, task or {}):
        return None
    fn = task["function"]
    tests = task["hidden_tests"]
    sc = task["scorer"]
    cases = []
    if sc == "code_function_deep_tests":
        for arg, want in tests:
            cases.append(((arg,), want, False))
    elif sc == "code_function_deep_tests_args":
        for args, want in tests:
            cases.append((tuple(args), want, True))
    elif sc == "code_function_numeric_tests":
        for arg, want in tests:
            cases.append(((arg,), want, False))
    elif sc == "code_function_raises_tests":
        for tc in tests:
            cases.append((tuple(tc["args"]), tc["want"], True))
    else:
        return None
    driver = (
        "import json\n" + code + "\n"
        + "cases=" + repr([(c[0], c[1]) for c in cases]) + "\n"
        + "unpacks=" + repr([c[2] for c in cases]) + "\n"
        + "wants=" + repr([c[1] for c in cases]) + "\n"
        + "out=[]\n"
        + "for (args, want), unp in zip(cases, unpacks):\n"
        + "    try:\n"
        + f"        got={fn}(*args) if unp else {fn}(args[0])\n"
        + "    except Exception as e:\n"
        + "        out.append('EXC:'+type(e).__name__+': '+str(e)[:200])\n"
        + "    else:\n"
        + "        out.append(repr(got)[:300])\n"
        + "print(json.dumps(out))\n"
    )
    ok_run, payload = _run_harness(driver)
    if not ok_run or not isinstance(payload, list):
        return None
    for (args, want, _unp), got in zip(cases, payload):
        bad = False
        if isinstance(got, str) and got.startswith("EXC:"):
            bad = True
        elif want == "RAISES":
            bad = not (isinstance(got, str) and got.startswith("EXC:"))
        else:
            try:
                bad = not _norm_eq(got, want)
            except Exception:
                bad = True
        if bad:
            inp = repr(args[0] if len(args) == 1 else args)[:300]
            return inp, repr(want)[:300], str(got)[:300]
    return None


def _norm_eq(got_repr, want):
    """Loose equality between a repr'd got and the want value."""
    import ast
    try:
        got = ast.literal_eval(got_repr)
    except Exception:
        return got_repr == repr(want)
    if isinstance(want, float) and isinstance(got, (int, float)):
        return abs(float(got) - want) < 1e-6
    return got == want


def _pinpoint_constraint(detail):
    """Turn terse aggregate detail into pinpointed failing units."""
    notes = []
    for unit, a, b in re.findall(r"(\w+)=(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", detail or ""):
        try:
            fa, fb = float(a), float(b)
        except ValueError:
            continue
        if fa != fb:
            notes.append(f"{unit}: got {a}, need exactly {b}")
    for m in re.findall(r"sentence_(\d+)_starts_wrong", detail or ""):
        notes.append(f"sentence {m} starts with the wrong letter")
    for m in re.findall(r"line_(\d+)_prefix_wrong", detail or ""):
        notes.append(f"line {m} has the wrong bullet prefix")
    m = re.search(r"first='([^']*)' last='([^']*)'", detail or "")
    return notes


def enrich_detail(task, answer, terse_detail):
    """Counterexample-grade failure detail without leaking the answer."""
    sc = task["scorer"]
    if sc in CODE_SCORERS:
        triple = _first_failing_case(task, answer)
        if triple:
            inp, want, got = triple
            return (
                f"Counterexample — your code failed this hidden test:\n"
                f"  input:    {inp}\n"
                f"  expected: {want}\n"
                f"  your code produced: {got}\n"
                f"Full check: {terse_detail}")
        return terse_detail  # crash etc.: traceback already in detail
    if sc.startswith("constraint_"):
        notes = _pinpoint_constraint(terse_detail)
        if notes:
            return ("Exact violations:\n  - " + "\n  - ".join(notes)
                    + f"\nFull check: {terse_detail}")
        return terse_detail
    # single-answer scorers: revealing more would leak the answer
    return terse_detail + " Your answer is incorrect; re-derive it from scratch."


CE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "{detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Fix the exact failure shown above. Follow the original instructions exactly. "
    "Do not repeat your previous answer unchanged."
)

SOCRATIC_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Before rewriting, answer this in one sentence: what assumption in your "
    "previous answer is most likely wrong, given the failure detail? Then "
    "produce the corrected answer following the original instructions exactly."
)

DIVERGE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Do not try to patch your previous answer. Try a fundamentally different "
    "approach to the problem, then produce the corrected answer following the "
    "original instructions exactly."
)

MH_TEMPLATES = {
    "minimal": (
        "{prompt}\n\nYour previous answer FAILED the automated check.\n"
        "Failure detail: {detail}\nYour previous answer was:\n{answer}\n\n"
        "Make the SMALLEST targeted change that fixes the exact failure "
        "described above. Follow the original instructions exactly."),
    "rewrite": (
        "{prompt}\n\nYour previous answer FAILED the automated check.\n"
        "Failure detail: {detail}\nYour previous answer was:\n{answer}\n\n"
        "Set your previous approach aside and REWRITE the solution from "
        "scratch using a different internal strategy that avoids this "
        "failure class. Follow the original instructions exactly."),
}

AD_DIVERGE_TEMPLATE = (
    "{prompt}\n\nYour last two attempts FAILED in exactly the same way.\n"
    "Failure detail: {detail}\n\n"
    "Incremental patching is not working. Try a fundamentally different "
    "approach to the problem, then produce the corrected answer following "
    "the original instructions exactly."
)


# ------------------------------------------------------------- runners

def _tracked_call(prompt, calls):
    a = call_model(prompt)
    calls.append({"prompt_chars": len(prompt), "completion_chars": len(a)})
    time.sleep(2)
    return a


def run_baseline(task):
    """v5 revise, verbatim, with token tracking."""
    calls, attempts, seen = [], [], set()
    prompt, answer = task["prompt"], None
    for n in range(3):
        answer = _tracked_call(prompt, calls)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "pass": passed, "detail": detail,
                         "repeated": repeated})
        if passed or repeated:
            break
        if n < 2:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
    return answer, {"mechanism": "baseline", "attempts": attempts,
                    "calls": calls}


def run_ce(task):
    calls, attempts, seen = [], [], set()
    prompt, answer = task["prompt"], None
    for n in range(3):
        answer = _tracked_call(prompt, calls)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "pass": passed, "detail": detail,
                         "repeated": repeated})
        if passed or repeated:
            break
        if n < 2:
            rich = enrich_detail(task, answer, detail)
            prompt = CE_TEMPLATE.format(
                prompt=task["prompt"], detail=rich,
                answer=answer.strip()[:4000])
    return answer, {"mechanism": "ce", "attempts": attempts, "calls": calls}


def run_mh(task):
    """Multi-hypothesis: 2 framings per round, keep the better."""
    calls, attempts = [], []
    answer = _tracked_call(task["prompt"], calls)
    passed, detail = verify(task, answer)
    attempts.append({"attempt": 1, "pass": passed, "detail": detail,
                     "framing": "initial"})
    if passed:
        return answer, {"mechanism": "mh", "attempts": attempts, "calls": calls}
    best, best_prog = answer, progress_score(task, answer, detail)
    for rnd in range(2):
        cands = []
        for name, tmpl in MH_TEMPLATES.items():
            p = tmpl.format(prompt=task["prompt"], detail=detail,
                            answer=best.strip()[:4000])
            a = _tracked_call(p, calls)
            ok, d = verify(task, a)
            cands.append((a, ok, d, name))
            attempts.append({"attempt": len(attempts) + 1, "pass": ok,
                             "detail": d, "framing": name})
            if ok:
                return a, {"mechanism": "mh", "attempts": attempts,
                           "calls": calls}
        # keep the better candidate by progress
        scored = [(progress_score(task, a, d), a, d) for a, ok, d, _ in cands]
        scored.sort(reverse=True)
        prog, a, d = scored[0][0], scored[0][1], scored[0][2]
        if prog > best_prog:
            best, best_prog, detail = a, prog, d
        # else: keep previous best and its detail; next round retries
    return best, {"mechanism": "mh", "attempts": attempts, "calls": calls}


def run_kb(task):
    """Keep-best: baseline loop, final = best attempt by progress."""
    calls, attempts, seen = [], [], set()
    prompt = task["prompt"]
    scored = []
    for n in range(3):
        answer = _tracked_call(prompt, calls)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        prog = 1.0 if passed else progress_score(task, answer, detail)
        scored.append((prog, answer))
        attempts.append({"attempt": n + 1, "pass": passed, "detail": detail,
                         "repeated": repeated, "progress": prog})
        if passed or repeated:
            break
        if n < 2:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1], {"mechanism": "kb", "attempts": attempts,
                          "calls": calls}


def _norm_detail(d):
    return re.sub(r"\s+", " ", (d or "").strip().lower())


def run_ad(task, max_rounds=4):
    """Adaptive: continue while fail detail changes; on repeat, one
    divergence nudge then stop."""
    calls, attempts = [], []
    prompt, prev_detail = task["prompt"], None
    answer = _tracked_call(prompt, calls)
    for n in range(1 + max_rounds):
        passed, detail = verify(task, answer)
        attempts.append({"attempt": n + 1, "pass": passed, "detail": detail})
        if passed:
            break
        if _norm_detail(detail) == _norm_detail(prev_detail) and prev_detail:
            # stuck: one divergence attempt, then stop
            p = AD_DIVERGE_TEMPLATE.format(prompt=task["prompt"], detail=detail)
            answer = _tracked_call(p, calls)
            passed2, detail2 = verify(task, answer)
            attempts.append({"attempt": n + 2, "pass": passed2,
                             "detail": detail2, "diverged": True})
            break
        prev_detail = detail
        if n < max_rounds:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
            answer = _tracked_call(prompt, calls)
    return answer, {"mechanism": "ad", "attempts": attempts, "calls": calls}


# Strict-verifier extra edge tests (used to GUIDE revision only;
# final pass/fail always uses the original scorer).
STRICT_EXTRA = {
    "c1-expr-eval-3": [("--5", 5.0), ("(-3)**2", 9.0), ("2**-2", 0.25)],
    "c10-sexpr": [("(- 5)", -5.0), ("(/ 1 2)", 0.5), ("(+ (* 2 3) (/ 10 4))", 8.5)],
    "p3-unicode-json": [("{'e': 'AB'}".replace("'", '"'), {"e": "AB"}),
                        ("[1, 2.5, -3]", [1, 2.5, -3]),
                        ('{"a": "\\n"}', {"a": "\n"})],
    "p8-bizdays": [((("2026-10-17", 1),), "2026-10-19"),
                   ((("2026-10-18", -1),), "2026-10-16"),
                   ((("2024-02-28", 2),), "2024-03-01")],
    "p9-sexpr-let": [("(let ((x 1)) (let ((y x)) (+ x y)))", 2.0),
                     ("(- 5)", -5.0), ("(/ 7 2)", 3.5)],
}


def _strict_verify(task, answer):
    """Original scorer AND extra edge tests must all pass."""
    ok, detail = verify(task, answer)
    if not ok:
        return False, detail
    extra = STRICT_EXTRA.get(task["id"])
    if not extra:
        return ok, detail
    code = _strip_fences(answer)
    fn = task["function"]
    sc = task["scorer"]
    if sc == "code_function_deep_tests_args":
        tests = [[list(a[0]), w] for a, w in extra]
    elif sc == "code_function_raises_tests":
        tests = [{"args": list(a[0]), "want": w} for a, w in extra]
    else:
        tests = [[a[0] if isinstance(a, tuple) else a, w] for a, w in extra]
        # normalize: extra entries are (input, want); for args-style wrap
    if sc == "code_function_deep_tests_args":
        driver_tests = tests  # already [[args], want]
    else:
        driver_tests = tests
    # reuse the task's own scorer machinery on the augmented test list
    aug = dict(task)
    aug["hidden_tests"] = task["hidden_tests"] + driver_tests
    try:
        ok2, detail2 = score_v5.SCORERS[sc](answer, aug)
    except Exception as e:
        return False, detail + f" | strict harness crashed: {e}"
    if ok2:
        return True, detail
    return False, detail + " | strict edge tests failed"


def run_sv(task):
    calls, attempts, seen = [], [], set()
    prompt, answer = task["prompt"], None
    for n in range(3):
        answer = _tracked_call(prompt, calls)
        passed, _ = _strict_verify(task, answer)
        # report detail from the ORIGINAL scorer for comparability
        _, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "strict_pass": passed,
                         "pass": passed, "detail": detail,
                         "repeated": repeated})
        if passed or repeated:
            break
        if n < 2:
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
    # final judged by ORIGINAL scorer
    ok, detail = verify(task, answer)
    return answer, {"mechanism": "sv", "attempts": attempts, "calls": calls,
                    "final_original_pass": ok, "final_original_detail": detail}


# ------------------------------------------------- feedback-style loops

STYLE_TEMPLATES = {
    "style_terse": REVISE_TEMPLATE,
    "style_ce": CE_TEMPLATE,
    "style_socratic": SOCRATIC_TEMPLATE,
    "style_diverge": DIVERGE_TEMPLATE,
}


def run_style(task, style):
    tmpl = STYLE_TEMPLATES[style]
    calls, attempts, seen = [], [], set()
    prompt, answer = task["prompt"], None
    for n in range(3):
        answer = _tracked_call(prompt, calls)
        passed, detail = verify(task, answer)
        key = norm_answer(answer)
        repeated = key in seen
        seen.add(key)
        attempts.append({"attempt": n + 1, "pass": passed, "detail": detail,
                         "repeated": repeated})
        if passed or repeated:
            break
        if n < 2:
            rich = enrich_detail(task, answer, detail) if style == "style_ce" else detail
            prompt = tmpl.format(prompt=task["prompt"], detail=rich,
                                 answer=answer.strip()[:4000])
    return answer, {"mechanism": style, "attempts": attempts, "calls": calls}


RUNNERS = {
    "baseline": run_baseline,
    "ce": run_ce,
    "mh": run_mh,
    "kb": run_kb,
    "ad": run_ad,
    "sv": run_sv,
    "style_terse": lambda t: run_style(t, "style_terse"),
    "style_ce": lambda t: run_style(t, "style_ce"),
    "style_socratic": lambda t: run_style(t, "style_socratic"),
    "style_diverge": lambda t: run_style(t, "style_diverge"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mech", required=True, choices=list(RUNNERS))
    ap.add_argument("--task", required=True)
    ap.add_argument("--rep", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    task = load_task(args.task)
    final, meta = RUNNERS[args.mech](task)
    meta.update({"task": args.task, "rep": args.rep})
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, "openai_gpt-oss-120b.txt"), "w") as f:
        f.write(final or "NO-OUTPUT")
    with open(os.path.join(args.outdir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    if args.mech == "sv":
        passed, detail = meta["final_original_pass"], meta["final_original_detail"]
    else:
        passed, detail = verify(task, final)
    toks = sum(c["prompt_chars"] + c["completion_chars"] for c in meta["calls"])
    print(json.dumps({"task": args.task, "rep": args.rep, "mech": args.mech,
                      "final_pass": passed, "detail": detail,
                      "calls": len(meta["calls"]), "tok_chars": toks}))


if __name__ == "__main__":
    main()
