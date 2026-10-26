#!/usr/bin/env python3
"""score-v5.py — scorer library for benchmark v5 (cycle 1+).

Reuses the full v4 mechanical scorer set and adds:
  numeric_decimal          exact Decimal comparison (money arithmetic)
  code_function_raises_tests  tests where some cases must raise ValueError
  constraint_words         per-sentence / total word counts, required words
  constraint_acrostic      first/last letters of sentences spell words
  constraint_commas        exact comma count per sentence
  constraint_list_alt      alternating bullet prefixes per line
"""
import os
import re
import sys
from decimal import Decimal, InvalidOperation

import importlib.util as _ilu

BASE = os.path.dirname(os.path.abspath(__file__))
V4 = os.path.join(os.path.dirname(BASE), "benchmark-v4")


def _load_v4():
    spec = _ilu.spec_from_file_location(
        "score_v4_mod", os.path.join(V4, "score-v4.py"))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_v4 = _load_v4()
score_numeric_tolerance = _v4.score_numeric_tolerance
score_token_strict = _v4.score_token_strict
score_digits_strict = _v4.score_digits_strict
score_code_function_numeric_tests = _v4.score_code_function_numeric_tests
score_code_function_deep_tests = _v4.score_code_function_deep_tests
score_code_function_deep_tests_args = _v4.score_code_function_deep_tests_args
score_constraint_alpha = _v4.score_constraint_alpha
score_constraint_paragraphs = _v4.score_constraint_paragraphs
score_constraint_list = _v4.score_constraint_list
_strip_fences = _v4._strip_fences
_check_banned = _v4._check_banned
_run_harness = _v4._run_harness
_sentences = _v4._sentences
_deep_driver = _v4._deep_driver


def score_numeric_decimal(text, expected):
    """Any number token in the text must Decimal-equal the expected string."""
    want = Decimal(expected)
    toks = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    found = []
    for t in toks:
        try:
            found.append(Decimal(t.replace(",", "")))
        except InvalidOperation:
            pass
    ok = any(v == want for v in found)
    return ok, f"numbers_found={[str(v) for v in found]}, want={want}"


def score_code_function_raises_tests(text, tests, func_name, task=None):
    """Tests: list of {"args": [...], "want": value | "RAISES"}.

    For RAISES cases the function must raise ValueError (any exception whose
    type name contains 'Error' counts, to tolerate custom messages; bare
    crashes on non-RAISES cases fail)."""
    code = _strip_fences(text)
    banned = _check_banned(code, task or {})
    if banned:
        return False, banned
    driver = (
        "import json\n" + code + "\n"
        + "tests=" + repr(tests) + "\n"
        + "results=[]\n"
        + "for tc in tests:\n"
        + "    args, want = tc['args'], tc['want']\n"
        + "    try:\n"
        + f"        got={func_name}(*args)\n"
        + "    except Exception as e:\n"
        + "        results.append('RAISED:'+type(e).__name__ if want=='RAISES' else 'CRASH')\n"
        + "    else:\n"
        + "        results.append(got==want if want!='RAISES' else 'NORAISE')\n"
        + "print(json.dumps(results))\n"
    )
    ok_run, payload = _run_harness(driver)
    if not ok_run:
        return False, payload
    good = 0
    for tc, r in zip(tests, payload):
        if tc["want"] == "RAISES":
            if isinstance(r, str) and r.startswith("RAISED:"):
                good += 1
        elif r is True:
            good += 1
    ok = good == len(tests) and len(payload) == len(tests)
    return ok, f"tests_passed={good}/{len(tests)}"


def score_constraint_words(text, task):
    """Word-count constraints.

    Task fields: n_sentences (int or None), words_per_sentence (int, list, or
    None), total_words (int or None), required_words ({1-based pos: word}),
    starts (str of letters, one per sentence, optional).
    """
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_sentences")
    if n is not None:
        sents = _sentences(t)
        if len(sents) != n:
            ok = False
        detail.append(f"sentences={len(sents)}/{n}")
    else:
        sents = _sentences(t) or [t]
    wps = task.get("words_per_sentence")
    if wps is not None:
        if isinstance(wps, int):
            wps = [wps] * len(sents)
        for i, s in enumerate(sents):
            nw = len(re.findall(r"[a-z0-9]+", s.lower()))
            want = wps[i] if i < len(wps) else wps[-1]
            if nw != want:
                ok = False
            detail.append(f"sent_{i+1}_words={nw}/{want}")
    tw = task.get("total_words")
    if tw is not None:
        nw = len(re.findall(r"[a-z0-9]+", t.lower()))
        if nw != tw:
            ok = False
        detail.append(f"total_words={nw}/{tw}")
    for pos, word in task.get("required_words", {}).items():
        pos = int(pos)  # JSON object keys arrive as strings
        toks = re.findall(r"[a-z0-9]+", t.lower())
        got = toks[pos - 1] if 0 < pos <= len(toks) else None
        if got != word.lower():
            ok = False
        detail.append(f"word_{pos}={got!r}/{word!r}")
    starts = task.get("starts")
    if starts:
        for i, s in enumerate(sents):
            m = re.search(r"[a-zA-Z]", s)
            want = starts[i].lower() if i < len(starts) else "?"
            if not m or m.group(0).lower() != want:
                ok = False
                detail.append(f"sentence_{i+1}_starts_wrong")
    return ok, ", ".join(detail)


def score_constraint_acrostic(text, task):
    """First letters of sentences spell first_spell; last letters (final
    alpha char before terminal punctuation) spell last_spell."""
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_sentences", 4)
    sents = _sentences(t)
    if len(sents) != n:
        ok = False
    detail.append(f"sentences={len(sents)}/{n}")
    first = "".join(re.search(r"[a-zA-Z]", s).group(0).lower()
                    for s in sents if re.search(r"[a-zA-Z]", s))
    lasts = []
    for s in sents:
        m = re.findall(r"[a-zA-Z]", s)
        lasts.append(m[-1].lower() if m else "?")
    last = "".join(lasts)
    if first != task.get("first_spell", ""):
        ok = False
    if last != task.get("last_spell", ""):
        ok = False
    detail.append(f"first={first!r} last={last!r}")
    return ok, ", ".join(detail)


def score_constraint_commas(text, task):
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_sentences", 3)
    k = task.get("commas_per_sentence", 2)
    sents = _sentences(t)
    if len(sents) != n:
        ok = False
    detail.append(f"sentences={len(sents)}/{n}")
    for i, s in enumerate(sents):
        nc = s.count(",")
        if nc != k:
            ok = False
        detail.append(f"sent_{i+1}_commas={nc}/{k}")
    return ok, ", ".join(detail)


def score_constraint_list_alt(text, task):
    """Alternating bullet prefixes: odd lines start with odd_prefix,
    even lines with even_prefix; words_per_line counted after the marker."""
    t = text.strip()
    detail, ok = [], True
    n = task.get("n_lines", 6)
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) != n:
        ok = False
    detail.append(f"lines={len(lines)}/{n}")
    op, ep = task.get("odd_prefix", "- "), task.get("even_prefix", "* ")
    wpl = task.get("words_per_line")
    for i, ln in enumerate(lines):
        s = ln.strip()
        want = op if i % 2 == 0 else ep
        if not s.startswith(want):
            ok = False
            detail.append(f"line_{i+1}_prefix_wrong")
            continue
        if wpl is not None:
            nw = len(re.findall(r"[a-z0-9]+", s[len(want):].lower()))
            if nw != wpl:
                ok = False
            detail.append(f"line_{i+1}_words={nw}/{wpl}")
    return ok, ", ".join(detail)


SCORERS = {
    "numeric_tolerance": lambda t, task: score_numeric_tolerance(
        t, task["expected"], task.get("tolerance", 1e-4)),
    "numeric_decimal": lambda t, task: score_numeric_decimal(
        t, task["expected"]),
    "token_strict": lambda t, task: score_token_strict(t, task["expected"]),
    "digits_strict": lambda t, task: score_digits_strict(t, task["expected"]),
    "code_function_numeric_tests": lambda t, task: score_code_function_numeric_tests(
        t, task["hidden_tests"], task["function"],
        task.get("tolerance", 1e-6), task.get("ban_eval", False)),
    "code_function_deep_tests": lambda t, task: score_code_function_deep_tests(
        t, task["hidden_tests"], task["function"], task),
    "code_function_deep_tests_args": lambda t, task: score_code_function_deep_tests_args(
        t, task["hidden_tests"], task["function"], task),
    "code_function_raises_tests": lambda t, task: score_code_function_raises_tests(
        t, task["hidden_tests"], task["function"], task),
    "constraint_alpha": lambda t, task: score_constraint_alpha(t, task),
    "constraint_paragraphs": lambda t, task: score_constraint_paragraphs(t, task),
    "constraint_list": lambda t, task: score_constraint_list(t, task),
    "constraint_list_alt": lambda t, task: score_constraint_list_alt(t, task),
    "constraint_words": lambda t, task: score_constraint_words(t, task),
    "constraint_acrostic": lambda t, task: score_constraint_acrostic(t, task),
    "constraint_commas": lambda t, task: score_constraint_commas(t, task),
}
