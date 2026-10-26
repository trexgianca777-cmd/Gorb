#!/usr/bin/env python3
"""design-v5.py — builds tasks-v5-candidates.json for the cycle-1 screen.

Every ground truth is computed programmatically in this file (reference
implementations, brute-force solvers, Decimal arithmetic). Nothing is
hand-derived. verify-v5.py independently checks good-pass/bad-fail for
every task against score-v5.py.
"""
import json
import os
import random
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

BASE = os.path.dirname(os.path.abspath(__file__))
TASKS = []


def add(tid, family, prompt, scorer, **kw):
    t = {"id": tid, "family": family, "prompt": prompt, "scorer": scorer}
    t.update(kw)
    TASKS.append(t)


# ---------------------------------------------------------------------------
# Reference implementations (ground truth for code tasks)
# ---------------------------------------------------------------------------

def ref_eval(s):
    """Arithmetic: + - * / ** (right-assoc), parens, unary minus (Python-like:
    unary binds LESS tightly than **), whitespace ignored."""
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c.isdigit() or c == '.':
            j = i
            while j < n and (s[j].isdigit() or s[j] == '.'):
                j += 1
            toks.append(('NUM', float(s[i:j])))
            i = j
        elif c == '*' and i + 1 < n and s[i + 1] == '*':
            toks.append(('OP', '**')); i += 2
        elif c in '+-*/()':
            toks.append(('OP', c)); i += 1
        else:
            raise ValueError(f"bad char {c!r}")
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else (None, None)

    def next_():
        nonlocal pos
        t = toks[pos]; pos += 1
        return t

    def parse_expr():
        v = parse_term()
        while peek() == ('OP', '+') or peek() == ('OP', '-'):
            op = next_()[1]
            r = parse_term()
            v = v + r if op == '+' else v - r
        return v

    def parse_term():
        v = parse_factor()
        while peek()[1] in ('*', '/'):
            op = next_()[1]
            r = parse_factor()
            v = v * r if op == '*' else v / r
        return v

    def parse_factor():
        if peek() == ('OP', '-'):
            next_()
            return -parse_factor()
        if peek() == ('OP', '+'):
            next_()
            return parse_factor()
        return parse_power()

    def parse_power():
        base = parse_primary()
        if peek() == ('OP', '**'):
            next_()
            exp = parse_factor()  # right-assoc, unary allowed in exponent
            return base ** exp
        return base

    def parse_primary():
        t = next_()
        if t[0] == 'NUM':
            return t[1]
        if t == ('OP', '('):
            v = parse_expr()
            assert next_() == ('OP', ')'), "missing )"
            return v
        raise ValueError(f"unexpected {t}")
    v = parse_expr()
    assert pos == len(toks), "trailing tokens"
    return v


def ref_parse_csv_row(row):
    fields, cur, i, n = [], [], 0, len(row)
    in_q = False
    while i < n:
        c = row[i]
        if in_q:
            if c == '"':
                if i + 1 < n and row[i + 1] == '"':
                    cur.append('"'); i += 2
                else:
                    in_q = False; i += 1
            else:
                cur.append(c); i += 1
        else:
            if c == '"':
                in_q = True; i += 1
            elif c == ',':
                fields.append(''.join(cur)); cur = []; i += 1
            else:
                cur.append(c); i += 1
    fields.append(''.join(cur))
    return fields


def ref_parse_sjson(s):
    """Strict JSON parser, no json module. Returns Python value."""
    pos = 0
    n = len(s)

    def ws():
        nonlocal pos
        while pos < n and s[pos] in ' \t\n\r':
            pos += 1

    def parse():
        nonlocal pos
        ws()
        c = s[pos]
        if c == '{':
            return parse_obj()
        if c == '[':
            return parse_arr()
        if c == '"':
            return parse_str()
        if c == 't':
            assert s.startswith('true', pos); pos += 4
            return True
        if c == 'f':
            assert s.startswith('false', pos); pos += 5
            return False
        if c == 'n':
            assert s.startswith('null', pos); pos += 4
            return None
        return parse_num()

    def parse_obj():
        nonlocal pos
        assert s[pos] == '{'; pos += 1
        d = {}
        ws()
        if s[pos] == '}':
            pos += 1
            return d
        while True:
            ws()
            k = parse_str()
            ws()
            assert s[pos] == ':'; pos += 1
            d[k] = parse()
            ws()
            if s[pos] == ',':
                pos += 1
                continue
            assert s[pos] == '}'; pos += 1
            return d

    def parse_arr():
        nonlocal pos
        assert s[pos] == '['; pos += 1
        a = []
        ws()
        if s[pos] == ']':
            pos += 1
            return a
        while True:
            a.append(parse())
            ws()
            if s[pos] == ',':
                pos += 1
                continue
            assert s[pos] == ']'; pos += 1
            return a

    def parse_str():
        nonlocal pos
        assert s[pos] == '"'; pos += 1
        out = []
        while s[pos] != '"':
            c = s[pos]
            if c == '\\':
                pos += 1
                e = s[pos]
                out.append({'n': '\n', 't': '\t', 'r': '\r', 'b': '\b',
                            'f': '\f', '"': '"', '\\': '\\', '/': '/'}[e]
                           if e != 'u' else None)
                if e == 'u':
                    out[-1] = chr(int(s[pos + 1:pos + 5], 16))
                    pos += 4
                pos += 1
            else:
                out.append(c); pos += 1
        pos += 1
        return ''.join(out)

    def parse_num():
        nonlocal pos
        m = re.match(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', s[pos:])
        assert m
        tok = m.group(0)
        pos += len(tok)
        return float(tok) if any(c in tok for c in '.eE') else int(tok)

    v = parse()
    ws()
    assert pos == n, "trailing"
    return v


def ref_wildcard(s, pattern):
    # iterative DP; supports *, ?, [abc], [!abc], backslash escapes
    toks = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == '\\' and i + 1 < n:
            toks.append(('LIT', pattern[i + 1])); i += 2
        elif c == '*':
            toks.append(('STAR',)); i += 1
        elif c == '?':
            toks.append(('Q',)); i += 1
        elif c == '[':
            j = pattern.index(']', i + 1)
            cls = pattern[i + 1:j]
            neg = cls.startswith('!')
            if neg:
                cls = cls[1:]
            toks.append(('CLASS', neg, set(cls))); i = j + 1
        else:
            toks.append(('LIT', c)); i += 1
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def dp(ti, si):
        if ti == len(toks):
            return si == len(s)
        t = toks[ti]
        if t[0] == 'STAR':
            return any(dp(ti + 1, k) for k in range(si, len(s) + 1))
        if si >= len(s):
            return False
        if t[0] == 'Q':
            return dp(ti + 1, si + 1)
        if t[0] == 'LIT':
            return s[si] == t[1] and dp(ti + 1, si + 1)
        if t[0] == 'CLASS':
            _, neg, charset = t
            ok = (s[si] in charset)
            return (not ok if neg else ok) and dp(ti + 1, si + 1)
        return False
    return dp(0, 0)


def ref_base_to_int(s, base):
    if not (2 <= base <= 36):
        raise ValueError("bad base")
    s = s.strip()
    if not s:
        raise ValueError("empty")
    neg = False
    if s[0] in '+-':
        neg = s[0] == '-'; s = s[1:]
    if not s:
        raise ValueError("sign only")
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    v = 0
    for ch in s.lower():
        d = digits.find(ch)
        if d < 0 or d >= base:
            raise ValueError(f"bad digit {ch!r}")
        v = v * base + d
    return -v if neg else v


_ROMAN_VAL = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
_ROMAN_SUB = {'IV': 4, 'IX': 9, 'XL': 40, 'XC': 90, 'CD': 400, 'CM': 900}


def ref_roman_to_int(s):
    if not s or any(c not in _ROMAN_VAL for c in s):
        raise ValueError("bad chars")
    # validate canonical form: re-encode and compare
    v = 0; i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i:i + 2] in _ROMAN_SUB:
            v += _ROMAN_SUB[s[i:i + 2]]; i += 2
        else:
            # subtractive pair must be from the allowed set
            if i + 1 < len(s) and _ROMAN_VAL[s[i]] < _ROMAN_VAL[s[i + 1]]:
                raise ValueError("bad subtractive")
            v += _ROMAN_VAL[s[i]]; i += 1
    # canonical re-encode check (rejects IIII, VV, etc.)
    canon = ref_int_to_roman(v)
    if canon != s:
        raise ValueError("non-canonical")
    return v


def ref_int_to_roman(v):
    out = ""
    for val, sym in [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                     (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                     (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]:
        while v >= val:
            out += sym; v -= val
    return out


def _days_from_civil(y, m, d):
    # Howard Hinnant's algorithm; no datetime module.
    y -= m <= 2
    era = (y >= 0 and y or y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe


def _civil_from_days(z):
    # inverse of _days_from_civil above (same epoch: days since 0000-03-01)
    era = (z >= 0 and z or z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + (m <= 2), m, d)


def ref_add_days(ds, n):
    y, m, d = map(int, ds.split('-'))
    yy, mm, dd = _civil_from_days(_days_from_civil(y, m, d) + n)
    return f"{yy:04d}-{mm:02d}-{dd:02d}"


def ref_rle_decode(s):
    out, i, n = [], 0, len(s)
    while i < n:
        j = i
        while j < n and s[j].isdigit():
            j += 1
        assert j < n and j > i, "bad rle"
        out.append(s[j] * int(s[i:j]))
        i = j + 1
    return ''.join(out)


def ref_balanced(s):
    pairs = {')': '(', ']': '[', '}': '{', '>': '<'}
    opens = set(pairs.values())
    stack, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "'\"":
            q = c; i += 1
            while i < n and s[i] != q:
                i += 1
            i += 1  # skip closing quote (tests never have unterminated)
        elif c in opens:
            stack.append(c); i += 1
        elif c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
            i += 1
        else:
            i += 1
    return not stack


def ref_sexpr(s):
    toks = re.findall(r'\(|\)|[^\s()]+', s)
    pos = 0

    def parse():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            op = toks[pos]; pos += 1
            args = []
            while toks[pos] != ')':
                args.append(parse())
            pos += 1
            if op == '+': return sum(args)
            if op == '*':
                p = 1
                for a in args: p *= a
                return p
            if op == '-':
                return -args[0] if len(args) == 1 else args[0] - sum(args[1:])
            if op == '/':
                r = float(args[0])
                for a in args[1:]: r /= a
                return r
            raise ValueError(op)
        return float(t)
    v = parse()
    assert pos == len(toks)
    return v


_MORSE = {'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
          'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
          'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
          'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
          'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
          'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
          '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
          '9': '----.'}
_MORSE_REV = {v: k for k, v in _MORSE.items()}


def ref_morse_encode(text):
    return ' / '.join(' '.join(_MORSE[c] for c in w)
                      for w in text.upper().split(' '))


def ref_morse_decode(s):
    return ' '.join(''.join(_MORSE_REV[code] for code in w.split(' '))
                    for w in s.split(' / '))


def ref_caesar_decode(text, shift):
    out = []
    for c in text:
        if 'a' <= c <= 'z':
            out.append(chr((ord(c) - 97 - shift) % 26 + 97))
        elif 'A' <= c <= 'Z':
            out.append(chr((ord(c) - 65 - shift) % 26 + 65))
        else:
            out.append(c)
    return ''.join(out)


def ref_caesar_encode(text, shift):
    return ref_caesar_decode(text, -shift)


# ---------------------------------------------------------------------------
# CODE TASKS
# ---------------------------------------------------------------------------

EXPR_TESTS = [
    ("3*-2", -6.0), ("2**3**2", 512.0), ("-(2+3)*-2", 10.0),
    (" 4 + 2 * -3 ", -2.0), ("10/4", 2.5), ("2**-1", 0.5),
    ("(1+2)*(3- -1)", 12.0), ("--5", 5.0), ("-2**2", -4.0),
    ("3 * -(2 + -1)", -3.0),
]
assert all(abs(ref_eval(a) - w) < 1e-9 for a, w in EXPR_TESTS)
add("c1-expr-eval-3", "code",
    "Write a Python function named evaluate that takes one string argument: an arithmetic "
    "expression, and returns a float. The expression contains non-negative integers, the binary "
    "operators + - * / and ** (exponentiation), parentheses, and unary minus. Unary minus may "
    "appear at the start of the expression, right after '(', or right after another operator "
    "(including after **). Unary minus binds LESS tightly than **, as in Python: -2**2 is -4, "
    "not 4. ** is right-associative: 2**3**2 is 512. Whitespace may appear anywhere and must be "
    "ignored. Division is float division. Do NOT use eval, exec, or the ast module. Reply with "
    "ONLY the function code, no explanation.",
    "code_function_numeric_tests", function="evaluate",
    hidden_tests=EXPR_TESTS, tolerance=1e-6, ban_eval=True)

CSV_TESTS = [
    ("a,b,", ["a", "b", ""]),
    ('"a""b",c', ['a"b', 'c']),
    ('"a,b",c', ['a,b', 'c']),
    ('"",x', ['', 'x']),
    ('  a  ,b', ['  a  ', 'b']),
    ('"x","y","z"', ['x', 'y', 'z']),
]
assert all(ref_parse_csv_row(a) == w for a, w in CSV_TESTS)
add("c2-csv-2", "code",
    "Write a Python function named parse_csv_row that takes one string argument: a single row "
    "of comma-separated values, and returns a list of strings (one per field). Rules: fields "
    "are separated by commas; a field wrapped in double quotes may contain commas; inside a "
    "quoted field two consecutive double quotes represent one literal quote character; a "
    "trailing comma means a final empty field; unquoted fields keep their whitespace exactly. "
    "Reply with ONLY the function code, no explanation.",
    "code_function_deep_tests", function="parse_csv_row",
    hidden_tests=CSV_TESTS)

SJSON_DOCS = [
    ('{"a": 1, "b": [true, false, null], "c": {"d": "x\\"y"}}',
     {"a": 1, "b": [True, False, None], "c": {"d": 'x"y'}}),
    ('[1, [2, [3]], {"k": "v\\n"}]', [1, [2, [3]], {"k": "v\n"}]),
    ('{"empty": {}, "list": [], "s": "a\\\\b"}',
     {"empty": {}, "list": [], "s": "a\\b"}),
    ('{"n": -12.5, "t": true}', {"n": -12.5, "t": True}),
]
assert all(ref_parse_sjson(a) == w for a, w in SJSON_DOCS)
add("c3-sjson-2", "code",
    "Write a Python function named parse_sjson that takes one string argument: a simplified "
    "JSON document, and returns the parsed Python value (dicts, lists, strings, numbers, "
    "booleans, None). The document is always valid strict JSON: objects, arrays, double-quoted "
    "strings with escapes (\\\", \\\\, \\n, \\t, \\uXXXX), numbers, true/false/null, arbitrary "
    "nesting. Do NOT use the json module or eval. Reply with ONLY the function code.",
    "code_function_deep_tests", function="parse_sjson",
    hidden_tests=SJSON_DOCS, ban_modules=["json"])

WILD_TESTS = [
    (["hello", "h*o"], True), (["hello", "h?llo"], True),
    # per the prompt there are NO ranges: [a-z] is the literal set {'a','-','z'}
    (["hello", "h[a-z]llo"], False), (["hello", "h[!a-z]llo"], True),
    (["h-llo", "h[a-z]llo"], True),
    (["a*b", "a\\*b"], True), (["axb", "a\\*b"], False),
    (["abc", "a*c"], True), (["ac", "a*c"], True),
    (["abcdef", "a*f"], True), (["abc", "*"], True), (["", "*"], True),
    (["", "?"], False), (["a1b", "a[0-9]b"], False),
]
# note: [0-9] is a literal class of chars '0','-','9' in our reference
assert all(ref_wildcard(s, p) == w for (s, p), w in WILD_TESTS), \
    [((s, p), w, ref_wildcard(s, p)) for (s, p), w in WILD_TESTS
     if ref_wildcard(s, p) != w]
add("c4-wildcard-2", "code",
    "Write a Python function named wildcard_match that takes two string arguments (s, pattern) "
    "and returns True if s matches the pattern. Pattern syntax: * matches any sequence of "
    "characters (including empty); ? matches exactly one character; [abc] matches exactly one "
    "of the listed characters (there are NO ranges: [0-9] means the three characters '0', '-', "
    "'9'); [!abc] matches exactly one character NOT in the list; a backslash escapes the next "
    "character (\\* matches a literal asterisk). Reply with ONLY the function code.",
    "code_function_deep_tests_args", function="wildcard_match",
    hidden_tests=WILD_TESTS)

BASE_TESTS = [
    (["  -ff ", 16], -255), (["1Z", 36], 71), (["+101", 2], 5),
    (["z", 36], 35), (["0", 10], 0),
]
BASE_RAISES = [["19", 8], ["1", 1], ["", 10], ["+", 10], ["xyz", 10]]
for (a, b), w in BASE_TESTS:
    assert ref_base_to_int(a, b) == w
for a, b in BASE_RAISES:
    try:
        ref_base_to_int(a, b)
        raise AssertionError(f"should raise: {a!r} base {b}")
    except ValueError:
        pass
add("c5-base-convert-2", "code",
    "Write a Python function named base_to_int that takes a string s and an integer base (2 to "
    "36) and returns the integer value. Rules: strip leading/trailing whitespace; an optional "
    "leading + or - sets the sign; digits are 0-9 then a-z (case-insensitive). Raise ValueError "
    "if: base is outside 2..36, the string is empty after stripping, it is only a sign, or any "
    "digit is invalid for the base. Reply with ONLY the function code.",
    "code_function_raises_tests", function="base_to_int",
    hidden_tests=[{"args": a, "want": w} for a, w in
                  [([s, b], v) for (s, b), v in BASE_TESTS] +
                  [([s, b], "RAISES") for s, b in BASE_RAISES]])

ROMAN_TESTS = [
    (["MCMXCIV"], 1994), (["IX"], 9), (["XLII"], 42), (["MMXXVI"], 2026),
]
ROMAN_RAISES = [["IIII"], ["VV"], ["IL"], ["XM"], ["ABC"], [""], ["IIX"]]
for [a], w in ROMAN_TESTS:
    assert ref_roman_to_int(a) == w
for [a] in ROMAN_RAISES:
    try:
        ref_roman_to_int(a)
        raise AssertionError(f"should raise: {a!r}")
    except ValueError:
        pass
add("c6-roman-validate", "code",
    "Write a Python function named roman_to_int that takes a string of uppercase Roman numeral "
    "characters and returns its integer value. Standard subtractive notation applies "
    "(IV=4, IX=9, XL=40, XC=90, CD=400, CM=900). Raise ValueError for anything invalid: "
    "characters outside IVXLCDM, empty string, non-canonical forms (IIII, VV, IL, XM, IIX, "
    "etc. — only the six standard subtractive pairs are legal, and no symbol may repeat more "
    "than three times in a row). Reply with ONLY the function code.",
    "code_function_raises_tests", function="roman_to_int",
    hidden_tests=[{"args": a, "want": w} for a, w in
                  [(a, v) for a, v in ROMAN_TESTS] +
                  [(a, "RAISES") for a in ROMAN_RAISES]])

DATE_TESTS = [
    (["2024-02-28", 1], "2024-02-29"), (["2023-02-28", 1], "2023-03-01"),
    (["2026-12-31", 1], "2027-01-01"), (["2000-02-28", 2], "2000-03-01"),
    (["1900-02-28", 1], "1900-03-01"), (["2026-01-01", -1], "2025-12-31"),
    (["2024-03-01", -1], "2024-02-29"), (["2026-06-15", 200], "2027-01-01"),
]
for a, w in DATE_TESTS:
    assert ref_add_days(*a) == w, (a, ref_add_days(*a), w)
add("c7-date-add", "code",
    "Write a Python function named add_days that takes a date string in YYYY-MM-DD format and "
    "an integer n (positive or negative), and returns the date n days later as a YYYY-MM-DD "
    "string. Handle leap years correctly, including the century rules (2000 was a leap year, "
    "1900 was not). Do NOT use the datetime module. Reply with ONLY the function code.",
    "code_function_deep_tests_args", function="add_days",
    hidden_tests=DATE_TESTS, ban_modules=["datetime", "calendar"])

def ref_rle_encode(p):
    out, i = [], 0
    while i < len(p):
        j = i
        while j < len(p) and p[j] == p[i]:
            j += 1
        out.append(f"{j - i}{p[i]}")
        i = j
    return ''.join(out)


# RLE plaintexts are letters only (digits in plaintext would make the
# count/char format ambiguous).
_RLE_PLAINS = ["AAAB", "XYZ", "Q", "MMMMMMMMMM", "aabbbccccdddddd"]
RLE_TESTS = [([ref_rle_encode(p)], p) for p in _RLE_PLAINS]
for a, w in RLE_TESTS:
    assert ref_rle_decode(*a) == w, (a, w)
add("c8-rle-decode", "code",
    "Write a Python function named rle_decode that takes a run-length encoded string and "
    "returns the decoded string. Encoding format: each run is a decimal count (one or more "
    "digits) followed by the character to repeat, e.g. '3A12B1C' decodes to 'AAA' + 'B'*12 + "
    "'C'. Inputs contain letters only (no digits in the decoded text). Reply with ONLY the "
    "function code.",
    "code_function_deep_tests_args", function="rle_decode",
    hidden_tests=RLE_TESTS)

BRACKET_TESTS = [
    (["([{}])"], True), (["([)]"], False), (["(a['b']c)"], True),
    (['{"<"}'], True), (["((("], False), ([""], True),
    (["<{[()]}>"], True), (["([}]"], False), (["'('"], True),
]
for a, w in BRACKET_TESTS:
    assert ref_balanced(*a) == w, (a, w, ref_balanced(*a))
add("c9-brackets", "code",
    "Write a Python function named is_balanced that takes a string and returns True if all "
    "brackets are correctly balanced, else False. Bracket pairs: () [] {} <>. A bracket inside "
    "single or double quotes is ignored (quotes always come in pairs in the inputs). Other "
    "characters are ignored. Reply with ONLY the function code.",
    "code_function_deep_tests_args", function="is_balanced",
    hidden_tests=BRACKET_TESTS)

SEXPR_TESTS = [
    ("(+ 1 (* 2 3) (- 10 4))", 13.0),
    ("(* (+ 1 2) (+ 3 4))", 21.0),
    ("(- 5)", -5.0),
    ("(/ 7 2)", 3.5),
    ("(+ (* 2 3) (/ 9 3) (- 1))", 8.0),
    ("(- (* 2 5) 3 2)", 5.0),
]
for a, w in SEXPR_TESTS:
    assert abs(ref_sexpr(a) - w) < 1e-9, (a, ref_sexpr(a), w)
add("c10-sexpr", "code",
    "Write a Python function named seval that takes a string: an arithmetic expression in "
    "fully-parenthesized prefix notation, e.g. '(+ 1 (* 2 3) (- 10 4))'. Operators: + * - /. "
    "+ and * take one or more operands; - and / take one or more operands (unary minus for a "
    "single operand, left-associative otherwise); / is float division. Operands are integers "
    "or nested expressions, separated by whitespace. Return a float. Reply with ONLY the "
    "function code.",
    "code_function_numeric_tests", function="seval",
    hidden_tests=SEXPR_TESTS, tolerance=1e-9)

_MORSE_WORDS = ["HELLO WORLD", "SOS", "PYTHON 3", "QUICK BROWN FOX"]
MORSE_TESTS = [([ref_morse_encode(w)], w) for w in _MORSE_WORDS]
for a, w in MORSE_TESTS:
    assert ref_morse_decode(*a) == w, (a, w)
add("c11-morse", "code",
    "Write a Python function named morse_decode that takes a Morse code string and returns "
    "the decoded uppercase text. Letters within a word are separated by single spaces; words "
    "are separated by ' / '. Use standard ITU Morse for A-Z and 0-9. Reply with ONLY the "
    "function code.",
    "code_function_deep_tests_args", function="morse_decode",
    hidden_tests=MORSE_TESTS)

_CAESAR_PAIRS = [("Hello, World!", 3), ("Attack at Dawn", 13),
                 ("Zebra", -1), ("MixED CaSe 123!", 29), ("abc", 26)]
CAESAR_TESTS = [([ref_caesar_encode(p, s), s], p) for p, s in _CAESAR_PAIRS]
for a, w in CAESAR_TESTS:
    assert ref_caesar_decode(*a) == w, (a, w)
add("c12-caesar-2", "code",
    "Write a Python function named caesar_decode that takes a string text and an integer "
    "shift, and returns the text decoded by shifting each letter BACKWARD by shift positions "
    "in the alphabet (wrapping around). The shift may be negative or larger than 26. Preserve "
    "letter case; leave non-letters unchanged. Reply with ONLY the function code.",
    "code_function_deep_tests_args", function="caesar_decode",
    hidden_tests=CAESAR_TESTS)

# ---------------------------------------------------------------------------
# LOGIC TASKS (brute-forced unique solutions)
# ---------------------------------------------------------------------------

def _kk_statements():
    """Generate a 6-islander knights/knaves puzzle with a unique solution.
    Returns (prompt_lines, answer_string). Deterministic."""
    rng = random.Random(20261018)
    names = ['A', 'B', 'C', 'D', 'E', 'F']

    def stmt_text(kind, x, y=None):
        if kind == 0:
            return f"{x} is a knight"
        if kind == 1:
            return f"{x} is a knave"
        if kind == 2:
            return f"{x} and {y} are the same type"
        if kind == 3:
            return f"at least one of {x} and {y} is a knave"
        if kind == 4:
            return f"if {x} is a knight then {y} is a knave"
        if kind == 5:
            return f"exactly one of {x} and {y} is a knight"

    def truth_of(kind, x, y, assign):
        # assign: dict name -> True (knight)
        ax, ay = assign[x], assign.get(y, None)
        if kind == 0:
            return ax
        if kind == 1:
            return not ax
        if kind == 2:
            return ax == ay
        if kind == 3:
            return (not ax) or (not ay)
        if kind == 4:
            return (not ax) or (not ay)
        if kind == 5:
            return ax != ay

    for trial in range(5000):
        stmts = []
        for i, sp in enumerate(names):
            kind = rng.randrange(6)
            x = rng.choice(names)
            y = rng.choice([n for n in names if n != x]) \
                if kind >= 2 else None
            stmts.append((sp, kind, x, y))
        # derive speaker types from statement truth under a seed assignment
        seed = {n: rng.random() < 0.5 for n in names}
        types = {}
        ok = True
        for sp, kind, x, y in stmts:
            t = truth_of(kind, x, y, seed)
            types[sp] = t
        # check uniqueness over all 64 assignments
        sols = 0
        for mask in range(64):
            assign = {n: bool(mask & (1 << i)) for i, n in enumerate(names)}
            good = True
            for sp, kind, x, y in stmts:
                # speaker tells truth iff knight
                if truth_of(kind, x, y, assign) != assign[sp]:
                    good = False
                    break
            if good:
                sols += 1
                if sols > 1:
                    break
        if sols == 1:
            lines = [f"{sp} says: \"{stmt_text(kind, x, y)}.\""
                     for sp, kind, x, y in stmts]
            ans = ''.join('T' if types[n] else 'F' for n in names)
            return lines, ans, types
    raise RuntimeError("no unique knights puzzle found")


_KK_LINES, _KK_ANS, _ = _kk_statements()
add("l1-knights-6", "logic",
    "Six islanders — A, B, C, D, E, F — are each either a knight (always tells the truth) "
    "or a knave (always lies). Each makes one statement:\n" +
    "\n".join(_KK_LINES) +
    "\nThere is exactly one consistent assignment. Reply with ONLY a 6-letter string for "
    "A,B,C,D,E,F in order, using T for knight and F for knave (example: TFTFTF).",
    "token_strict", expected=_KK_ANS.lower())

def _schedule_5():
    """5 people / 5 days with a conditional trap. Brute-force unique solution."""
    import itertools
    people = ['Amy', 'Ben', 'Cara', 'Dan', 'Eve']
    init = {p: p[0] for p in people}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

    clue_sets = [
        [("Amy speaks before Ben.", lambda a: a.index('Amy') < a.index('Ben')),
         ("Cara speaks on Wednesday.", lambda a: a[2] == 'Cara'),
         ("Dan does not speak on Monday or Friday.",
          lambda a: a[0] != 'Dan' and a[4] != 'Dan'),
         ("If Eve speaks on Tuesday then Ben speaks on Thursday.",
          lambda a: (a[1] != 'Eve') or (a[3] == 'Ben')),
         ("Ben speaks after Dan.", lambda a: a.index('Ben') > a.index('Dan')),
         ("Amy does not speak on Friday.", lambda a: a[4] != 'Amy'),
         ("Amy speaks on Monday.", lambda a: a[0] == 'Amy'),
         ("Ben speaks before Eve.", lambda a: a.index('Ben') < a.index('Eve'))],
        [("Eve speaks before Cara.", lambda a: a.index('Eve') < a.index('Cara')),
         ("Ben speaks on Thursday.", lambda a: a[3] == 'Ben'),
         ("Amy does not speak on Monday.", lambda a: a[0] != 'Amy'),
         ("If Dan speaks on Friday then Amy speaks on Monday.",
          lambda a: (a[4] != 'Dan') or (a[0] == 'Amy')),
         ("Cara speaks after Ben.", lambda a: a.index('Cara') > a.index('Ben')),
         ("Dan speaks before Eve.", lambda a: a.index('Dan') < a.index('Eve'))],
    ]
    for clues in clue_sets:
        sols = []
        for perm in itertools.permutations(people):
            if all(f(perm) for _, f in clues):
                sols.append(perm)
                if len(sols) > 1:
                    break
        if len(sols) == 1:
            lines = [c for c, _ in clues]
            ans = ''.join(init[p] for p in sols[0])
            return lines, ans
    raise RuntimeError("no unique schedule found")


_SCH_LINES, _SCH_ANS = _schedule_5()
add("l2-schedule-5", "logic",
    "Five friends — Amy, Ben, Cara, Dan, and Eve — each give a talk on a different day: "
    "Monday, Tuesday, Wednesday, Thursday, or Friday, one talk per day.\nClues:\n" +
    "\n".join(f"- {c}" for c in _SCH_LINES) +
    "\nThere is exactly one valid schedule. Reply with ONLY a 5-letter string: the first "
    "initial of who speaks on Monday, Tuesday, Wednesday, Thursday, Friday, in order "
    "(example: ADBEC).",
    "token_strict", expected=_SCH_ANS.lower())


def _zebra_4():
    """4 houses, unique fish-owner. Brute force."""
    import itertools
    colors = ['red', 'green', 'blue', 'yellow']
    pets = ['cat', 'dog', 'bird', 'fish']
    drinks = ['tea', 'coffee', 'milk', 'juice']
    clue_sets = [
        [("The red house is immediately left of the green house.",
          lambda h: h['color'].index('red') + 1 == h['color'].index('green')),
         ("The dog owner drinks coffee.",
          lambda h: h['drink'][h['pet'].index('dog')] == 'coffee'),
         ("The tea drinker owns the bird.",
          lambda h: h['pet'][h['drink'].index('tea')] == 'bird'),
         ("The blue house is house 2.",
          lambda h: h['color'][1] == 'blue'),
         ("The milk drinker lives next to the cat owner.",
          lambda h: abs(h['drink'].index('milk') - h['pet'].index('cat')) == 1),
         ("The yellow house owner drinks juice.",
          lambda h: h['drink'][h['color'].index('yellow')] == 'juice')],
    ]
    for clues in clue_sets:
        sols = []
        for c in itertools.permutations(colors):
            for p in itertools.permutations(pets):
                for d in itertools.permutations(drinks):
                    h = {'color': c, 'pet': p, 'drink': d}
                    if all(f(h) for _, f in clues):
                        sols.append(h)
                        if len(sols) > 3:
                            break
                    if len(sols) > 3:
                        break
                if len(sols) > 3:
                    break
            if len(sols) > 3:
                break
        # the asked question (fish house) must be uniquely determined,
        # even if the full arrangement is not
        fish_houses = {h['pet'].index('fish') + 1 for h in sols}
        if len(fish_houses) == 1 and sols:
            h = sols[0]
            lines = [c for c, _ in clues]
            return lines, str(next(iter(fish_houses))), h
    raise RuntimeError("no unique zebra found")


_ZEBRA_LINES, _ZEBRA_ANS, _ = _zebra_4()
add("l3-zebra-4", "logic",
    "Four houses stand in a row, numbered 1, 2, 3, 4 from left to right. Each house has a "
    "color (red, green, blue, yellow), a pet (cat, dog, bird, fish), and a drink (tea, coffee, "
    "milk, juice) — each value used exactly once.\nClues:\n" +
    "\n".join(f"- {c}" for c in _ZEBRA_LINES) +
    "\nThere is exactly one valid arrangement. Which house number (1-4) keeps the fish? "
    "Reply with ONLY the digit.",
    "digits_strict", expected=_ZEBRA_ANS)

# l4: exactly-one puzzle, verified by enumeration in the builder
_L4_N = [n for n in range(1, 5) if n % 2 == 1 and
         sum([n % 2 == 0, n in (2, 3, 5, 7, 11), n > 10]) == 1]
assert _L4_N == [3], _L4_N
add("l4-exactly-one", "logic",
    "N is an odd integer with 0 < N < 5. Exactly one of these three statements is true: "
    "(1) N is even. (2) N is prime. (3) N > 10. What is N? Reply with ONLY the digit.",
    "digits_strict", expected="3")

add("l5-tournament", "logic",
    "Four teams — A, B, C, D — play a round-robin (each pair meets once, no draws). "
    "Results: A beat B. C beat D. B beat C. D beat A. A beat C. D lost to B. "
    "Ties in the final standings are broken by head-to-head result. Which team finished "
    "first? Reply with ONLY the letter.",
    "token_strict", expected="a")
# records: A 2-1 (B,C wins; D loss), B 2-1 (C,D wins; A loss), C 1-2, D 1-2.
# head-to-head A beat B -> A first. verified above by hand; double-check in verify.


def _seating():
    import itertools
    people = ['A', 'B', 'C', 'D', 'E']
    clues = [
        ("C sits in chair 3.", lambda a: a[2] == 'C'),
        ("A sits immediately left of B.",
         lambda a: any(a[i] == 'A' and a[i + 1] == 'B' for i in range(4))),
        ("D sits somewhere left of E.", lambda a: a.index('D') < a.index('E')),
        ("B does not sit in chair 5.", lambda a: a[4] != 'B'),
        ("E does not sit in chair 1.", lambda a: a[0] != 'E'),
    ]
    sols = [p for p in itertools.permutations(people)
            if all(f(p) for _, f in clues)]
    assert len(sols) == 1, sols
    return [c for c, _ in clues], ''.join(sols[0])


_SEAT_LINES, _SEAT_ANS = _seating()
add("l6-seating", "logic",
    "Five chairs in a row, numbered 1 to 5 from left to right. Five people — A, B, C, D, E — "
    "sit one per chair.\nClues:\n" +
    "\n".join(f"- {c}" for c in _SEAT_LINES) +
    "\nThere is exactly one valid seating. Reply with ONLY a 5-letter string: who sits in "
    "chairs 1,2,3,4,5 in order (example: EABCD).",
    "token_strict", expected=_SEAT_ANS.lower())


def _liar_search():
    """Search small liar/truth-teller statement sets for a unique solution."""
    rng = random.Random(777)
    names = ['A', 'B', 'C']

    def text(kind, x, y):
        if kind == 0:
            return f"{x} is lying"
        if kind == 1:
            return f"{x} is telling the truth"
        if kind == 2:
            return f"{x} and {y} are both lying"

    def truth(kind, x, y, a):
        ax, ay = a[x], a.get(y)
        if kind == 0:
            return not ax
        if kind == 1:
            return ax
        return (not ax) and (not ay)

    for trial in range(20000):
        stmts = []
        for sp in names:
            kind = rng.randrange(3)
            x = rng.choice(names)
            y = rng.choice([n for n in names if n != x]) if kind == 2 else None
            stmts.append((sp, kind, x, y))
        sols = []
        for mask in range(8):
            a = {n: bool(mask & (1 << i)) for i, n in enumerate(names)}
            if all(truth(k, x, y, a) == a[sp] for sp, k, x, y in stmts):
                sols.append(a)
                if len(sols) > 1:
                    break
        if len(sols) == 1:
            a = sols[0]
            lines = [f"{sp} says: \"{text(k, x, y)}.\""
                     for sp, k, x, y in stmts]
            ans = ''.join('T' if a[n] else 'F' for n in names)
            return lines, ans
    raise RuntimeError("no unique liar puzzle")


_LIAR_LINES, _LIAR_ANS = _liar_search()
add("l7-liar-chain", "logic",
    "Three people — A, B, C — are each either a truth-teller (every statement they make is "
    "true) or a liar (every statement they make is false).\n" +
    "\n".join(_LIAR_LINES) +
    "\nThere is exactly one consistent assignment. Reply with ONLY a 3-letter string for "
    "A,B,C in order, T for truth-teller and F for liar (example: TFT).",
    "token_strict", expected=_LIAR_ANS.lower())

add("l8-syllogism", "logic",
    "Consider these premises: All Zorks are Morks. No Morks are Norks. Some Norks are Parks. "
    "Which ONE of the following must be true?\n(A) Some Zorks are Parks.\n(B) No Zorks are "
    "Norks.\n(C) All Parks are Norks.\nReply with ONLY the letter.",
    "token_strict", expected="b")
# (B): Zorks ⊆ Morks, Morks ∩ Norks = ∅ → Zorks ∩ Norks = ∅ ✓ forced.
# (A): a Zork could be a non-Nork Park — not forced. (C): Parks may extend beyond Norks.

# ---------------------------------------------------------------------------
# ARITHMETIC TRAPS (Decimal ground truth)
# ---------------------------------------------------------------------------

def _money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# a1: $85/hr x 12.5h labor, $230 expenses, 20% discount on LABOR only,
# then 8.25% tax on the discounted subtotal. Total?
_a1_labor = Decimal("85") * Decimal("12.5")
_a1_disc = _a1_labor * Decimal("0.80")
_a1_sub = _a1_disc + Decimal("230")
_a1_total = _money(_a1_sub * Decimal("1.0825"))
assert _a1_total == Decimal("1169.10"), _a1_total
add("a1-fee-order", "arithmetic",
    "A consultant bills $85 per hour and works 12.5 hours. Expenses are $230. The client "
    "receives a 20% discount on the labor charge only (not on expenses). Then 8.25% sales tax "
    "is applied to the discounted subtotal. What is the final total in dollars? Round to the "
    "nearest cent. Reply with ONLY the number.",
    "numeric_decimal", expected="1169.10")

# a2: $240 pre-tax bill, 8% tax, 18% tip calculated on the PRE-TAX amount.
_a2_total = _money(Decimal("240") * Decimal("1.08") + Decimal("240") * Decimal("0.18"))
assert _a2_total == Decimal("302.40"), _a2_total
add("a2-tip-pretax", "arithmetic",
    "A restaurant bill is $240 before tax. Tax is 8% of the bill. The tip is 18%, calculated "
    "on the pre-tax bill amount (not including tax). What is the total paid? Reply with ONLY "
    "the number.",
    "numeric_decimal", expected="302.40")

# a3: price up 200%, then down 60%. Net change vs original?
_a3 = _money(Decimal("3") * Decimal("0.4") * 100 - 100)
assert _a3 == Decimal("20.00"), _a3
add("a3-percent-trap", "arithmetic",
    "A stock price first increases by 200%, then decreases by 60%. What is the net percent "
    "change relative to the original price? Reply with ONLY the number (e.g. 25 for +25%).",
    "numeric_decimal", expected="20")

# a4: 60 mi at 30 mph, 60 mi back at 60 mph. Average speed?
_a4 = _money(Decimal("120") / (Decimal("60") / Decimal("30") +
                               Decimal("60") / Decimal("60")))
assert _a4 == Decimal("40.00"), _a4
add("a4-harmonic", "arithmetic",
    "A driver travels 60 miles at 30 mph, then returns the same 60 miles at 60 mph. What is "
    "the average speed for the whole trip in mph? Reply with ONLY the number.",
    "numeric_decimal", expected="40")

# a5: buy-2-get-1-free, $4.50 each, need 17. Cost?
_a5_sets, _a5_rem = divmod(17, 3)
_a5_paid = _money(Decimal(_a5_sets * 2 + _a5_rem) * Decimal("4.50"))
assert _a5_paid == Decimal("54.00"), _a5_paid
add("a5-bogo", "arithmetic",
    "A store runs buy-2-get-1-free on $4.50 items. You need exactly 17 items. What is the "
    "lowest total cost in dollars? Reply with ONLY the number.",
    "numeric_decimal", expected="54.00")

# a6: $1000 at 5% nominal compounded quarterly for 3 years.
_a6 = _money(Decimal("1000") * (Decimal("1") + Decimal("0.05") / 4) ** 12)
assert _a6 == Decimal("1160.75"), _a6
add("a6-compound", "arithmetic",
    "$1000 is invested at a 5% annual rate compounded quarterly for 3 years. What is the "
    "final amount in dollars, to the nearest cent? Reply with ONLY the number.",
    "numeric_decimal", expected="1160.75")

# ---------------------------------------------------------------------------
# ADVERSARIAL INSTRUCTION-FOLLOWING
# ---------------------------------------------------------------------------

add("w1-double-constraint", "writing",
    "Write exactly 4 sentences. Sentence 1 must start with the letter G, sentence 2 with O, "
    "sentence 3 with L, sentence 4 with D. Every sentence must end with the word 'done' "
    "(followed by its terminal period). Do not use the word 'done' anywhere else. Reply with "
    "ONLY the 4 sentences.",
    "constraint_alpha", n_sentences=4, starts="gold",
    word_counts={"done": 4})

add("w2-word-count", "writing",
    "Write exactly 5 sentences. Each sentence must contain exactly 6 words. Reply with ONLY "
    "the 5 sentences.",
    "constraint_words", n_sentences=5, words_per_sentence=6)

add("w3-acrostic", "writing",
    "Write exactly 4 sentences about the sea. The first letters of the four sentences must "
    "spell MARS (sentence 1 starts with M, sentence 2 with A, sentence 3 with R, sentence 4 "
    "with S). The last letters of the four sentences (the final letter before each terminal "
    "period) must spell SEEN (sentence 1 ends with ...s., sentence 2 with ...e., sentence 3 "
    "with ...e., sentence 4 with ...n.). Reply with ONLY the 4 sentences.",
    "constraint_acrostic", n_sentences=4, first_spell="mars", last_spell="seen")

add("w4-comma-exact", "writing",
    "Write exactly 3 sentences. Each sentence must contain exactly 2 commas. Reply with ONLY "
    "the 3 sentences.",
    "constraint_commas", n_sentences=3, commas_per_sentence=2)

add("w5-lines-words", "writing",
    "Write exactly 6 lines. Odd-numbered lines (1, 3, 5) must start with '- ' (dash, space). "
    "Even-numbered lines (2, 4, 6) must start with '* ' (asterisk, space). After the bullet "
    "marker, each line must contain exactly 4 words. Reply with ONLY the 6 lines.",
    "constraint_list_alt", n_lines=6, odd_prefix="- ", even_prefix="* ",
    words_per_line=4)

add("w6-n-words", "writing",
    "Write a single paragraph of exactly 41 words about deserts. Reply with ONLY the "
    "paragraph.",
    "constraint_words", n_sentences=None, total_words=41)

# ---------------------------------------------------------------------------
# COUNTING / LONG-CONTEXT
# ---------------------------------------------------------------------------

def _build_x1():
    rng = random.Random(4242)
    filler = [
        "The inspection team arrived before dawn.", "Coolant pressure held steady.",
        "A junior engineer logged the valve readings.", "The shift supervisor signed off.",
        "Backup generators were tested at noon.", "Radiation badges were collected.",
        "The control room stayed quiet through the night.", "A pump seal was replaced.",
        "Turbine vibration remained within tolerance.", "The safety drill ran long.",
        "New gaskets were installed on the east loop.", "The logbook was updated twice.",
        "An inspector asked about the welds.", "The night crew took over at six.",
        "Fuel rod alignment was verified.", "A sensor was recalibrated.",
        "The containment doors were cycled.", "Waste heat vented normally.",
        "The duty officer filed the report.", "A crane lifted the shield plug.",
    ]
    target = "reactor"
    decoys = ["reactors", "prereactor"]
    n_target = 14
    # sprinkle targets and decoys into filler sentences
    words = []
    placed = 0
    for s in filler:
        toks = s.split(' ')
        # randomly capitalize the target sometimes
        if placed < n_target and rng.random() < 0.75:
            pos = rng.randrange(len(toks))
            w = "Reactor" if rng.random() < 0.4 else "reactor"
            toks.insert(pos, w)
            placed += 1
        if rng.random() < 0.3:
            pos = rng.randrange(len(toks))
            toks.insert(pos, rng.choice(decoys))
        words.extend(toks)
    # top up remaining targets
    while placed < n_target:
        pos = rng.randrange(len(words))
        words.insert(pos, "reactor" if rng.random() < 0.6 else "Reactor")
        placed += 1
    passage = ' '.join(words)
    # ground truth: exact word match, case-insensitive
    truth = len(re.findall(r'\breactor\b', passage, flags=re.IGNORECASE))
    assert truth == n_target, (truth, n_target)
    # sanity: decoys must NOT match
    assert len(re.findall(r'\breactor\b', 'reactors prereactor',
                          flags=re.IGNORECASE)) == 0
    return passage, str(truth)


_X1_PASSAGE, _X1_ANS = _build_x1()
add("x1-count-word", "counting",
    "Read the passage below, then answer the question. Count carefully.\n\n" + _X1_PASSAGE +
    "\n\nQuestion: how many times does the word 'reactor' appear in the passage above? "
    "Count exact matches of the word, case-insensitive. Do NOT count 'reactors' or "
    "'prereactor'. Reply with ONLY the number.",
    "digits_strict", expected=_X1_ANS)


def _build_x2():
    rng = random.Random(99)
    regions = ["North", "South", "East", "West", "Central"]
    # gross max != net max by construction
    gross = [82, 64, 91, 55, 70]
    cost = [30, 20, 55, 18, 40]
    net = [g - c for g, c in zip(gross, cost)]
    # East has highest gross (91) but net 36; North net 52 wins
    assert max(range(5), key=lambda i: gross[i]) == 2
    best = max(range(5), key=lambda i: net[i])
    assert best == 0
    lines = ["Regional results (all figures in $ millions):"]
    for r, g, c, n in zip(regions, gross, cost, net):
        lines.append(f"{r}: gross revenue {g}, operating cost {c}, net {n}.")
    lines.append("The East region posted the highest gross revenue at 91, a company record.")
    return "\n".join(lines), regions[best]


_X2_TEXT, _X2_ANS = _build_x2()
add("x2-salient-wrong", "counting",
    _X2_TEXT + "\n\nQuestion: which region had the highest NET revenue? Reply with ONLY the "
    "region name.",
    "token_strict", expected=_X2_ANS.lower())


def _build_x3():
    rng = random.Random(31337)
    vals = [round(rng.uniform(10, 999), 2) for _ in range(40)]
    vals = list(dict.fromkeys(vals))  # dedupe, keep order
    while len(vals) < 40:
        v = round(rng.uniform(10, 999), 2)
        if v not in vals:
            vals.append(v)
    ranked = sorted(vals, reverse=True)
    third = ranked[2]
    # embed in prose with the max value mentioned saliently early
    words = [f"The sensor logged {ranked[0]:.2f} at startup, a record high."]
    rest = vals.copy()
    rng.shuffle(rest)
    words.append("Subsequent readings: " + ", ".join(f"{v:.2f}" for v in rest) + ".")
    return " ".join(words), f"{third:.2f}"


_X3_TEXT, _X3_ANS = _build_x3()
add("x3-third-highest", "counting",
    _X3_TEXT + "\n\nQuestion: what was the third-highest reading? Reply with ONLY the number.",
    "numeric_decimal", expected=_X3_ANS)


def _build_x4():
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]
    # (signups, cost): trap = highest signups (Sat) has worse ratio than Wed
    data = [(120, 40), (200, 60), (150, 30), (90, 45), (110, 55),
            (300, 150), (80, 20)]
    ratios = [s / c for s, c in data]
    best = max(range(7), key=lambda i: ratios[i])
    assert max(range(7), key=lambda i: data[i][0]) == 5  # Saturday most signups
    assert best == 2  # Wednesday best ratio 5.0
    lines = ["Daily ad campaign results:"]
    for d, (s, c) in zip(days, data):
        lines.append(f"{d}: {s} signups, ${c} spend.")
    return "\n".join(lines), days[best]


_X4_TEXT, _X4_ANS = _build_x4()
add("x4-ratio-trap", "counting",
    _X4_TEXT + "\n\nQuestion: which day had the highest signups-per-dollar ratio? Reply with "
    "ONLY the day name.",
    "token_strict", expected=_X4_ANS.lower())

# ---------------------------------------------------------------------------
# NEGATION / ORDER TRAPS
# ---------------------------------------------------------------------------

add("n1-not-true", "negation",
    "A box contains red and blue balls. Consider these statements:\n"
    "(A) There are more red balls than blue balls.\n(B) There are 10 balls in total.\n"
    "(C) If you remove 2 red balls, blue balls would outnumber red balls.\n"
    "(D) There are 6 red balls.\n"
    "Exactly one of the four statements is FALSE. Which one? Reply with ONLY the letter.",
    "token_strict", expected="c")
# D: 6 red; B: total 10 -> 4 blue. A: 6>4 true. C: 4 red vs 4 blue -> false.
# exactly one false ✓ (A,B,D true).


def _build_n2():
    ev = [
        ("A", "March 3, 2026", date(2026, 3, 3)),
        ("B", "3/4/2026", date(2026, 3, 4)),
        ("C", "the Ides of March, 2026", date(2026, 3, 15)),
        ("D", "St. Patrick's Day, 2026", date(2026, 3, 17)),
        ("E", "the first Monday of March 2026", date(2026, 3, 2)),
        ("F", "March 10, 2026", date(2026, 3, 10)),
    ]
    # verify the tricky ones programmatically
    assert date(2026, 3, 1).weekday() == 6  # March 1 2026 is a Sunday
    assert ev[4][2].weekday() == 0  # first Monday = Mar 2
    ordered = sorted(ev, key=lambda x: x[2])
    ans = ''.join(e[0] for e in ordered)
    lines = [f"Event {e}: {d}" for e, d, _ in ev]
    return lines, ans


_N2_LINES, _N2_ANS = _build_n2()
add("n2-chronology", "negation",
    "Six historical events, each with a date:\n" + "\n".join(_N2_LINES) +
    "\nList the events in chronological order (earliest first). Reply with ONLY the six "
    "letters in order (example: EABFCD).",
    "token_strict", expected=_N2_ANS.lower())

add("n3-except", "negation",
    "A train travels 120 miles in 2 hours at constant speed. All of the following are true "
    "EXCEPT:\n(A) Its average speed is 60 mph.\n(B) In 30 minutes it travels 30 miles.\n"
    "(C) In 5 hours it would travel 300 miles.\n(D) Its speed is 99 feet per second.\n"
    "Reply with ONLY the letter.",
    "token_strict", expected="d")
# 60 mph = 60*5280/3600 = 88 ft/s, not 99. A,B,C true.

add("n4-odd-one-out", "negation",
    "Five numbers: 121, 143, 169, 187, 209. Four of them share a property that the fifth "
    "lacks. Which number does NOT belong? Reply with ONLY the number.",
    "digits_strict", expected="169")
# 121=11*11, 143=11*13, 187=11*17, 209=11*19 all divisible by 11; 169=13*13 not.

# ---------------------------------------------------------------------------
# SELF-REFERENTIAL
# ---------------------------------------------------------------------------

_S1_SENT = ("In this very sentence count the occurrences of the letter e "
            "and report the total")
_S1_COUNT = _S1_SENT.lower().count('e')
add("s1-count-letter", "selfref",
    "Consider this sentence: \"" + _S1_SENT + ".\" How many times does the letter 'e' "
    "appear in that sentence (case-insensitive, counting every 'e' including the one in "
    "'the' and 'sentence')? Reply with ONLY the number.",
    "digits_strict", expected=str(_S1_COUNT))

add("s2-seven-words", "selfref",
    "Reply with exactly 7 words. The 4th word must be 'exactly'. Reply with ONLY the 7 "
    "words.",
    "constraint_words", n_sentences=1, words_per_sentence=7,
    required_words={4: "exactly"})

# ---------------------------------------------------------------------------
# Write the candidate file
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    out = os.path.join(BASE, "tasks-v5-candidates.json")
    with open(out, "w") as f:
        json.dump({"tasks": TASKS}, f, indent=2)
    fams = {}
    for t in TASKS:
        fams[t["family"]] = fams.get(t["family"], 0) + 1
    print(f"wrote {len(TASKS)} candidates -> {out}")
    print("families:", fams)
