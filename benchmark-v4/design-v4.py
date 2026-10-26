#!/usr/bin/env python3
"""design-v4.py — build tasks-v4.json with independently computed ground
truth, then verify every task: reference-good answer passes, plausible-bad
answer fails. Aborts (nonzero) if any check fails.

Ground-truth paths are independent of the scorers: brute force for logic,
datetime for temporal, eval/json/fnmatch/int for code tests, regex/token
counts for long-context.
"""
import datetime
import fnmatch
import importlib.util
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "sv4", os.path.join(HERE, "score-v4.py"))
sv4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv4)
SCORERS = sv4.SCORERS

# ---------------------------------------------------------------- reference
# implementations (these are the "good" answers for code tasks)

REF_EVAL = '''
def evaluate(expr):
    s = expr.replace(' ', '')
    pos = 0
    def parse_expr():
        nonlocal pos
        v = parse_term()
        while pos < len(s) and s[pos] in '+-':
            op = s[pos]; pos += 1
            r = parse_term()
            v = v + r if op == '+' else v - r
        return v
    def parse_term():
        nonlocal pos
        v = parse_power()
        while pos < len(s) and s[pos] in '*/' and not s.startswith('**', pos):
            op = s[pos]; pos += 1
            r = parse_power()
            v = v * r if op == '*' else v / r
        return v
    def parse_power():
        nonlocal pos
        base = parse_unary()
        if s.startswith('**', pos):
            pos += 2
            return base ** parse_power()
        return base
    def parse_unary():
        nonlocal pos
        if pos < len(s) and s[pos] == '-':
            pos += 1
            return -parse_unary()
        if pos < len(s) and s[pos] == '+':
            pos += 1
            return parse_unary()
        return parse_atom()
    def parse_atom():
        nonlocal pos
        if s[pos] == '(':
            pos += 1
            v = parse_expr()
            pos += 1
            return v
        start = pos
        while pos < len(s) and (s[pos].isdigit() or s[pos] == '.'):
            pos += 1
        return float(s[start:pos])
    return float(parse_expr())
'''

REF_SJSON = '''
def parse_sjson(s):
    pos = 0
    def skip():
        nonlocal pos
        while pos < len(s) and s[pos] in ' \\t\\n\\r':
            pos += 1
    def parse_value():
        nonlocal pos
        skip()
        c = s[pos]
        if c == '"': return parse_string()
        if c == '{': return parse_object()
        if c == '[': return parse_array()
        if c == 't': pos += 4; return True
        if c == 'f': pos += 5; return False
        if c == 'n': pos += 4; return None
        return parse_number()
    def parse_string():
        nonlocal pos
        pos += 1
        out = []
        while s[pos] != '"':
            if s[pos] == '\\\\':
                pos += 1
                out.append('"' if s[pos] == '"' else '\\\\')
                pos += 1
            else:
                out.append(s[pos]); pos += 1
        pos += 1
        return ''.join(out)
    def parse_number():
        nonlocal pos
        start = pos
        if s[pos] == '-': pos += 1
        while pos < len(s) and s[pos].isdigit(): pos += 1
        return int(s[start:pos])
    def parse_array():
        nonlocal pos
        pos += 1
        arr = []
        skip()
        if s[pos] == ']': pos += 1; return arr
        while True:
            arr.append(parse_value())
            skip()
            if s[pos] == ',': pos += 1; continue
            pos += 1
            return arr
    def parse_object():
        nonlocal pos
        pos += 1
        obj = {}
        skip()
        if s[pos] == '}': pos += 1; return obj
        while True:
            skip()
            k = parse_string()
            skip(); pos += 1
            obj[k] = parse_value()
            skip()
            if s[pos] == ',': pos += 1; continue
            pos += 1
            return obj
    return parse_value()
'''

REF_WILD = '''
def wildcard_match(s, pattern):
    m, n = len(s), len(pattern)
    dp = [[False]*(n+1) for _ in range(m+1)]
    dp[0][0] = True
    for j in range(1, n+1):
        if pattern[j-1] == '*':
            dp[0][j] = dp[0][j-1]
    for i in range(1, m+1):
        for j in range(1, n+1):
            if pattern[j-1] == '*':
                dp[i][j] = dp[i][j-1] or dp[i-1][j]
            elif pattern[j-1] == '?' or pattern[j-1] == s[i-1]:
                dp[i][j] = dp[i-1][j-1]
    return dp[m][n]
'''

REF_BASE = '''
def base_to_int(s, base):
    if not isinstance(base, int) or not 2 <= base <= 36:
        raise ValueError('bad base')
    if not s:
        raise ValueError('empty')
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    v = 0
    for ch in s.lower():
        d = digits.find(ch)
        if d < 0 or d >= base:
            raise ValueError('bad digit')
        v = v * base + d
    return v
'''

REF_CAESAR = '''
def caesar_decode(text, shift):
    out = []
    for ch in text:
        if 'a' <= ch <= 'z':
            out.append(chr((ord(ch) - 97 - shift) % 26 + 97))
        elif 'A' <= ch <= 'Z':
            out.append(chr((ord(ch) - 65 - shift) % 26 + 65))
        else:
            out.append(ch)
    return ''.join(out)
'''

REF_ROMAN = '''
def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        v = vals[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total
'''

# plausible-bad implementations (must FAIL the scorer)
BAD_EVAL = 'def evaluate(e):\n    return float(eval(e))\n'  # banned construct
BAD_SJSON = '''
def parse_sjson(s):
    s = s.strip()
    if s.startswith('"'):
        return s[1:-1]
    if s.startswith('['):
        return [parse_sjson(x) for x in s[1:-1].split(',')]
    if s == 'true': return True
    if s == 'false': return False
    if s == 'null': return None
    return int(s)
'''
BAD_WILD = '''
def wildcard_match(s, pattern):
    import re
    rx = pattern.replace('*', '.*').replace('?', '.')
    return re.fullmatch(rx, s) is not None
'''
BAD_BASE = 'def base_to_int(s, base):\n    return int(s)\n'
BAD_CAESAR = '''
def caesar_decode(text, shift):
    out = []
    for ch in text:
        if 'a' <= ch <= 'z':
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        elif 'A' <= ch <= 'Z':
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return ''.join(out)
'''
BAD_ROMAN = '''
def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    return sum(vals[ch] for ch in s)
'''

# ---------------------------------------------------------------- ground truth

# --- 01: expression evaluator with power + double unary (ground truth: eval)
T01_TESTS = [
    '2+3*4', '2**3', '2**3**2', '--3+5', '5--3', '(-3)**2',
    '2*(3+4*(5-2))', '7/2', ' 2 ** 3 ', '-(2+3)*2', '4/2/2', '3+-2',
]
T01_WANT = [float(eval(e)) for e in T01_TESTS]
assert T01_WANT == [14.0, 8.0, 512.0, 8.0, 8.0, 9.0, 30.0, 3.5, 8.0, -10.0,
                    1.0, 1.0], T01_WANT

# --- 02: simplified JSON (ground truth: json.loads)
T02_INPUTS = [
    '{"a": 1}',
    '[1, 2, 3]',
    '{"a": [1, {"b": null}]}',
    '"hello \\"world\\""',
    '{"t": true, "f": false}',
    '[-12, 0]',
    '[]',
    '{}',
    '"a\\\\b"',
    '[1,[2,[3]]]',
]
T02_WANT = [json.loads(x) for x in T02_INPUTS]

# --- 03: wildcard matching (ground truth: fnmatch.fnmatchcase)
T03_TESTS = [
    ("hello", "h*o", True), ("hello", "h?llo", True), ("hello", "*", True),
    ("", "*", True), ("", "?", False), ("abc", "a*c", True),
    ("abc", "a?c", True), ("abc", "a*d", False), ("abbbc", "a*c", True),
    ("abc", "**", True), ("abc", "a**c", True), ("abcdef", "a*f", True),
    ("axc", "a.c", False), ("", "", True),
]
for s, p, want in T03_TESTS:
    got = fnmatch.fnmatchcase(s, p)
    assert got == want, (s, p, got, want)

# --- 04: base conversion (ground truth: int(s, base))
T04_TESTS = [
    ("ff", 16), ("FF", 16), ("101", 2), ("z", 36), ("10", 8), ("0", 10),
    ("1a", 16), ("ZZ", 36), ("100", 2), ("abc", 16),
]
T04_WANT = [int(s, b) for s, b in T04_TESTS]

# --- 05: knights/knaves-5 (ground truth: brute force)
# A: "B is a knave."  B: "C is a knave."  C: "D and E are the same type."
# D: "A is telling the truth."  E: "B is lying."
def kk5_holds(a):  # a: dict name->True=knight
    A, B, C, D, E = (a[x] for x in "ABCDE")
    claims = {
        "A": (not B),                 # B is a knave
        "B": (not C),                 # C is a knave
        "C": (D == E),                # D and E same type
        "D": A,                       # A is telling the truth
        "E": (not B),                 # B is lying  (B knight => claim true)
    }
    # knight's claim must be true, knave's claim must be false
    return all(a[k] == claims[k] for k in "ABCDE")

kk5_solutions = [a for bits in itertools.product([False, True], repeat=5)
                 for a in [dict(zip("ABCDE", bits))] if kk5_holds(a)]
assert len(kk5_solutions) == 1, kk5_solutions
kk5_sol = kk5_solutions[0]
kk5_knaves = [k for k in "ABCDE" if not kk5_sol[k]]
assert len(kk5_knaves) == 1, kk5_knaves  # exactly one knave for letter answer
T05_EXPECTED = kk5_knaves[0].lower()  # "b"

# --- 06: scheduling trap 2 (ground truth: brute force)
# Amy, Ben, Cara, Dan, Eve over Mon..Fri.
# Hard: Amy before Ben; Cara not Monday; Dan = day after Cara; Eve after Dan.
# Conditional: "If Cara speaks Tuesday then Dan speaks Thursday."
#   (contradicts Dan=Cara+1, so the Cara=Tue branch is impossible)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
def sched2_ok(p):  # p: name -> day index
    if not (p["Amy"] < p["Ben"]):
        return False
    if p["Cara"] == 0:
        return False
    if p["Dan"] != p["Cara"] + 1:
        return False
    if not (p["Eve"] > p["Dan"]):
        return False
    if len(set(p.values())) != 5:
        return False
    # conditional: Cara==Tue -> Dan==Thu; the consequent contradicts the hard
    # constraint, so Cara==Tue must be impossible in any valid schedule
    if p["Cara"] == 1 and p["Dan"] != 3:
        return False
    return True

names6 = ["Amy", "Ben", "Cara", "Dan", "Eve"]
sched2_solutions = [dict(zip(names6, perm))
                    for perm in itertools.permutations(range(5))
                    if sched2_ok(dict(zip(names6, perm)))]
assert len(sched2_solutions) == 1, sched2_solutions
sol6 = sched2_solutions[0]
# verify the trap: the conditional branch is truly impossible under hard rules
hard_only = [dict(zip(names6, perm)) for perm in itertools.permutations(range(5))
             if sched2_ok(dict(zip(names6, perm))) or True]
# (conditional only ever fires on Cara==Tue; check no hard-valid schedule has it)
def hard6(p):
    return (p["Amy"] < p["Ben"] and p["Cara"] != 0
            and p["Dan"] == p["Cara"] + 1 and p["Eve"] > p["Dan"]
            and len(set(p.values())) == 5)
cara_tue_possible = any(hard6(dict(zip(names6, perm))) and
                        dict(zip(names6, perm))["Cara"] == 1
                        for perm in itertools.permutations(range(5)))
assert cara_tue_possible, "trap broken: Cara=Tue must be reachable a priori"
T06_EXPECTED = [n for n in names6 if sol6[n] == 4][0].lower()  # Friday speaker

# --- 07: zebra-lite (ground truth: brute force)
# Houses 1,2,3. colors {red,green,blue}, pets {cat,dog,bird},
# drinks {tea,coffee,milk}. Clues:
# 1. green immediately right of red; 2. cat owner drinks tea;
# 3. dog owner in house 2; 4. bird owner drinks milk; 5. house 1 is blue;
# 6. tea drinker not in house 1.
def zebra_ok(color, pet, drink):
    if color[1] != "blue":
        return False
    if not any(color[i] == "red" and color[i + 1] == "green" for i in (1, 2)):
        return False
    if pet[2] != "dog":
        return False
    for i in (1, 2, 3):
        if pet[i] == "cat" and drink[i] != "tea":
            return False
        if pet[i] == "bird" and drink[i] != "milk":
            return False
    if drink[1] == "tea":
        return False
    return True

zebra_solutions = []
for colors in itertools.permutations(["red", "green", "blue"]):
    for pets in itertools.permutations(["cat", "dog", "bird"]):
        for drinks in itertools.permutations(["tea", "coffee", "milk"]):
            c = {1: colors[0], 2: colors[1], 3: colors[2]}
            p = {1: pets[0], 2: pets[1], 3: pets[2]}
            d = {1: drinks[0], 2: drinks[1], 3: drinks[2]}
            if zebra_ok(c, p, d):
                zebra_solutions.append((c, p, d))
assert len(zebra_solutions) == 1, zebra_solutions
zc, zp, zd = zebra_solutions[0]
coffee_house = [i for i in (1, 2, 3) if zd[i] == "coffee"][0]
T07_EXPECTED = zp[coffee_house]  # pet of the coffee drinker

# --- 08: arithmetic double trap (independent hand computation)
# fee 85*12.5=1062.50; discounted fee 850.00; expenses 230;
# pre-discount total 1292.50; fee 5% of pre-discount = 64.625
T08_EXPECTED = round(850.00 + 230 + 64.625, 2)
assert T08_EXPECTED == 1144.62 or T08_EXPECTED == 1144.63, T08_EXPECTED
# trap answers (must NOT pass): discount-on-everything, fee-on-discounted
T08_TRAP1 = round(1292.50 * 0.80 + 64.625, 2)   # 1098.62/1098.63
T08_TRAP2 = round((850.00 + 230) * 1.05, 2)     # 1134.0
assert abs(T08_TRAP1 - 1144.625) > 0.05 and abs(T08_TRAP2 - 1144.625) > 0.05

# --- 12: long-context conflicting figures (fresh domain)
T12_PASSAGE = """---
HALCYON BREWING — Q3 SUMMARY

Halcyon Brewing Co. posted Q3 revenue of $8.2 million, its strongest quarter of the year.

The taproom division set a company record: the Halcyon Brewing taproom division posted Q3 revenue of $8.7 million, up 14% on three new locations, while distribution costs rose $400,000 on the Denver expansion and taproom headcount reached 210.

Packaging posted Q3 revenue of $3.1 million. Merchandise added $900,000.
---

Question: What was the Halcyon Brewing taproom division's Q3 revenue, in millions of dollars? Answer with ONLY the number."""

# --- 13: long-context exact count (ground truth: token count)
T13_PASSAGE = """Engineers at the Halden site completed the annual inspection of the primary reactor on Tuesday. The secondary reactor will remain offline until the new coolant pumps arrive. A reactor scram test is scheduled for next month, and every reactor operator must re-certify before the test. The report notes that the reactor vessel shows no unusual wear; two reactors of the same design operate in Finland, and the oldest reactors in the fleet date to the 1980s. During the outage, the reactor containment was repainted. Critics argue the reactor program costs too much, while supporters point out that each reactor displaces a coal plant. The next reactor refueling begins in June.

Question: How many times does the word "reactor" appear in the passage above? Count exact matches only: "reactors" and "reactor's" do not count. Answer with ONLY the number."""
T13_TOKENS = re.findall(r"[A-Za-z']+", T13_PASSAGE.split("\n\nQuestion:")[0])
T13_EXPECTED = sum(1 for t in T13_TOKENS if t == "reactor")
assert T13_EXPECTED > 3, T13_EXPECTED  # nontrivial count

# --- 14: temporal (ground truth: datetime)
treaty = datetime.date(2026, 3, 14)
embargo = treaty + datetime.timedelta(days=41)
assert embargo == datetime.date(2026, 4, 24), embargo
d = embargo + datetime.timedelta(days=1)
while d.weekday() != 0:  # first Monday strictly after embargo begins
    d += datetime.timedelta(days=1)
T14_EXPECTED = d.strftime("%Y%m%d")
assert T14_EXPECTED == "20260427", T14_EXPECTED

# --- 15: caesar (ground truth: reference impl executed here)
_ns15 = {}
exec(REF_CAESAR, _ns15)
T15_TESTS = [
    ("Khoor", 3), ("Ebiil", 23), ("ABC xyz", 1), ("Hello, World!", 0),
    ("Mjqqt", -5), ("", 5), ("123", 4), ("Z", 1), ("b", 27), ("Hello", -1),
]
T15_WANT = [_ns15["caesar_decode"](t, s) for t, s in T15_TESTS]
assert T15_WANT[0] == "Hello" and T15_WANT[8] == "a" and T15_WANT[9] == "Ifmmp"

# --- 16: roman (ground truth: reference impl executed here)
_ns16 = {}
exec(REF_ROMAN, _ns16)
T16_TESTS = ['III', 'IV', 'IX', 'LVIII', 'MCMXCIV', 'XLIV', 'MMMCMXCIX',
             'CD', 'CM', 'D', 'XIV', 'MMXXVI']
T16_WANT = [_ns16["roman_to_int"](x) for x in T16_TESTS]
assert T16_WANT == [3, 4, 9, 58, 1994, 44, 3999, 400, 900, 500, 14, 2026]

# --- 09/10/11: constructed good answers (must pass scorer)
T09_GOOD = ("Zebras wandered slowly. Yesterday seven bells rang. "
            "Xylophones echoed nowhere. Winter froze the lake. "
            "Vultures circled patiently.")
T09_BAD = ("Zebras wandered slowly. Yesterday seven bells rang slowly. "
           "Xylophones echoed nowhere. Winter froze the lake. "
           "Vultures circled patiently.")  # 'slowly' repeated

T10_GOOD = ("Morning frost covered blue roofs. Children raced toward blue "
            "buses. Drivers honked through icy streets.\n\n"
            "Teachers unlocked blue doors. Students filed into blue hallways. "
            "Lessons began without delay.")
T10_BAD = ("Morning frost covered blue roofs. Morning joggers passed blue "
           "buses. Drivers honked through icy streets.\n\n"
           "Teachers unlocked blue doors. Students filed into blue hallways. "
           "Lessons began without delay.")  # first word 'morning' repeated

T11_GOOD = ("- Apples ripen early.\n"
            "- Bananas bruise fast.\n"
            "- Ants march onward.\n"
            "- Bees hum loudly.\n"
            "- All tasks are done.\n"
            "- Birds sing sweetly.\n"
            "- Autumn fades gently.")
T11_BAD = ("- Apples ripen early.\n"
           "- Bananas bruise fast.\n"
           "- Ants march onward.\n"
           "- Bees hum loudly.\n"
           "- All tasks are done.\n"
           "- Birds sing sweetly when done.\n"
           "- Autumn fades gently.")  # 'done' twice

# ---------------------------------------------------------------- task build

TASKS = [
    {
        "id": "01-code-evaluator-2",
        "surface": "Hard code — expression parser, ** power, double unary, no eval",
        "prompt": (
            "Write a Python function named evaluate that takes one string argument: "
            "an arithmetic expression. The expression contains non-negative integers and "
            "the operators +, -, *, /, ** (power), and parentheses. Power is right-associative: "
            "2**3**2 means 2**(3**2). The - operator may also be unary (negation): it can appear "
            "at the start of the expression, immediately after another operator, or immediately "
            "after an opening parenthesis; two unary minuses in a row are allowed (--3 equals 3). "
            "Division is float division. Whitespace may appear anywhere and must be ignored. "
            "Return the numeric result as a float. Do NOT use eval(), exec(), or the ast module. "
            "Respond with ONLY the code, no explanation and no markdown fences."
        ),
        "scorer": "code_function_numeric_tests",
        "function": "evaluate",
        "tolerance": 1e-6,
        "ban_eval": True,
        "expected": "all 12 hidden tests pass",
        "hidden_tests": [[e, w] for e, w in zip(T01_TESTS, T01_WANT)],
        "notes": ("Fresh traps vs v3: right-assoc ** (2**3**2=512), double unary --3, "
                  "5--3, 3+-2. Expected values verified against Python eval as ground truth."),
        "good": REF_EVAL, "bad": BAD_EVAL,
    },
    {
        "id": "02-code-sjson",
        "surface": "Hard code — simplified JSON parser, escapes + nesting, no json module",
        "prompt": (
            "Write a Python function named parse_sjson that takes one string argument: a "
            "simplified JSON document. It must parse and return the corresponding Python object: "
            "double-quoted strings (supporting the \\\" and \\\\ escapes), integers (optionally "
            "negative), the literals true, false, null (mapping to True, False, None), arrays, and "
            "objects; arrays and objects may nest arbitrarily; whitespace between tokens must be "
            "ignored. Do NOT use the json module, eval(), exec(), or the ast module. "
            "Respond with ONLY the code, no explanation and no markdown fences."
        ),
        "scorer": "code_function_deep_tests",
        "function": "parse_sjson",
        "ban_eval": True,
        "ban_modules": ["json"],
        "expected": "all 10 hidden tests pass",
        "hidden_tests": [[x, w] for x, w in zip(T02_INPUTS, T02_WANT)],
        "notes": ("Expected values verified against json.loads as ground truth. "
                  "Traps: escaped quotes, nested null, negative ints, deep nesting. "
                  "import json is mechanically rejected."),
        "good": REF_SJSON, "bad": BAD_SJSON,
    },
    {
        "id": "03-code-wildcard",
        "surface": "Hard code — glob matcher, * and ?, literal dots",
        "prompt": (
            "Write a Python function named wildcard_match that takes two string arguments "
            "(s, pattern) and returns True if s matches pattern, else False. In the pattern, "
            "'*' matches any sequence of characters (including the empty sequence) and '?' "
            "matches exactly one character; every other character matches itself literally. "
            "Respond with ONLY the code, no explanation and no markdown fences."
        ),
        "scorer": "code_function_deep_tests_args",
        "function": "wildcard_match",
        "expected": "all 14 hidden tests pass",
        "hidden_tests": [[[s, p], w] for s, p, w in T03_TESTS],
        "notes": ("Expected values verified against fnmatch.fnmatchcase. Trap: ('axc','a.c') "
                  "is False — regex-naive conversions that turn '.' into 'any char' fail it."),
        "good": REF_WILD, "bad": BAD_WILD,
    },
    {
        "id": "04-code-base-convert",
        "surface": "Hard code — base 2-36 conversion, case-insensitive digits",
        "prompt": (
            "Write a Python function named base_to_int that takes a string s and an integer "
            "base (2 to 36) and returns the integer value of s interpreted in that base. "
            "Digits may be 0-9 and a-z in either case. Raise a ValueError for any invalid "
            "input (bad digit, bad base, empty string). "
            "Respond with ONLY the code, no explanation and no markdown fences."
        ),
        "scorer": "code_function_deep_tests_args",
        "function": "base_to_int",
        "expected": "all 10 hidden tests pass",
        "hidden_tests": [[[s, b], w] for (s, b), w in
                          zip(T04_TESTS, T04_WANT)],
        "notes": ("Expected values verified against int(s, base). Traps: uppercase digits, "
                  "base 36, int(s) ignoring the base."),
        "good": REF_BASE, "bad": BAD_BASE,
    },
    {
        "id": "05-knights-knaves-5",
        "surface": "Hard reasoning — 5-speaker knights/knaves, unique solution",
        "prompt": (
            'Five islanders — A, B, C, D, E — are each either a knight (always tells the truth) '
            'or a knave (always lies). A says: "B is a knave." B says: "C is a knave." '
            'C says: "D and E are the same type." D says: "A is telling the truth." '
            'E says: "B is lying." Which one is the knave? '
            "Answer with ONLY the letter: A, B, C, D, or E."
        ),
        "scorer": "token_strict",
        "expected": T05_EXPECTED,
        "notes": ("Verified by brute force over all 32 assignments: unique full solution "
                  f"{kk5_sol}; exactly one knave. E's statement self-references B's truthfulness."),
        "good": T05_EXPECTED.upper(), "bad": "a",
    },
    {
        "id": "06-scheduling-trap-2",
        "surface": "Hard reasoning — scheduling with a self-contradicting conditional",
        "prompt": (
            "Five friends — Amy, Ben, Cara, Dan, and Eve — each give a talk on a different day: "
            "Monday, Tuesday, Wednesday, Thursday, or Friday. Amy speaks before Ben. "
            "Cara does not speak on Monday. Dan speaks the day after Cara. Eve speaks after Dan. "
            "If Cara speaks on Tuesday, then Dan speaks on Thursday. "
            "Who speaks on Friday? Answer with ONLY the first name."
        ),
        "scorer": "token_strict",
        "expected": T06_EXPECTED,
        "notes": ("Verified by brute force over all 120 assignments: unique solution "
                  f"{sol6}. The conditional's consequent contradicts the hard constraint "
                  "Dan=Cara+1, so the Cara=Tue branch is impossible — verified reachable a "
                  "priori, impossible jointly."),
        "good": T06_EXPECTED.capitalize(), "bad": "Amy",
    },
    {
        "id": "07-zebra-lite",
        "surface": "Hard reasoning — 3-house zebra puzzle, unique solution",
        "prompt": (
            "Three houses stand in a row, numbered 1, 2, 3. Each house has a color "
            "(red, green, blue), a pet (cat, dog, bird), and a drink (tea, coffee, milk); "
            "each color, pet, and drink is used exactly once.\n"
            "Clues:\n"
            "1. The green house is immediately to the right of the red house.\n"
            "2. The cat owner drinks tea.\n"
            "3. The dog owner lives in house 2.\n"
            "4. The bird owner drinks milk.\n"
            "5. House 1 is blue.\n"
            "6. The tea drinker does not live in house 1.\n"
            "Which pet does the coffee drinker own? Answer with ONLY the pet name."
        ),
        "scorer": "token_strict",
        "expected": T07_EXPECTED,
        "notes": ("Verified by brute force over all 6^3 assignments: unique solution. "
                  "Clue 6 disambiguates the two solutions clue 1-5 leave."),
        "good": T07_EXPECTED, "bad": "cat",
    },
    {
        "id": "08-arithmetic-traps-2",
        "surface": "Multi-step arithmetic — discount scope + fee base traps",
        "prompt": (
            "A consultant bills $85 per hour and works 12.5 hours. Expenses are $230. "
            "The client receives a 20% discount on the consulting fee only (not on expenses). "
            "A 5% processing fee is added afterward, computed on the pre-discount total. "
            "What is the final total, in dollars? Round to the nearest cent. "
            "Answer with ONLY the number."
        ),
        "scorer": "numeric_tolerance",
        "expected": T08_EXPECTED,
        "tolerance": 0.015,  # 0.01 was defeated by float error: |1144.63-1144.62| = 0.0100000000002
        "notes": (f"Labor 85*12.5=1062.50; discounted fee 850.00; pre-discount total 1292.50; "
                  f"fee 5% of 1292.50=64.625; total 1144.625 -> {T08_EXPECTED}. "
                  f"Trap 1 (discount on everything): {T08_TRAP1}. Trap 2 (fee on discounted): "
                  f"{T08_TRAP2}. Both traps cleanly separated by tolerance 0.01."),
        "good": str(T08_EXPECTED), "bad": str(T08_TRAP1),
    },
    {
        "id": "09-adversarial-alpha-2",
        "surface": "Adversarial instruction-following — reverse alphabet, global uniqueness",
        "prompt": (
            "Write exactly 5 sentences. Sentence 1 must start with the letter Z, sentence 2 "
            "with Y, sentence 3 with X, sentence 4 with W, and sentence 5 with V. "
            "No word may appear more than once anywhere in your entire response "
            "(case-insensitive). The word \"seven\" must appear exactly once in the whole "
            "response. Do not use any semicolons or commas. Answer with only the 5 sentences."
        ),
        "scorer": "constraint_alpha",
        "n_sentences": 5,
        "starts": "zyxwv",
        "unique_words": True,
        "word_counts": {"seven": 1},
        "banned_chars": [";", ","],
        "expected": "5 sentences Z-Y-X-W-V, unique words, 'seven' x1, no ; or ,",
        "notes": "Satisfiability proven by construction; the bad answer repeats 'slowly'.",
        "good": T09_GOOD, "bad": T09_BAD,
    },
    {
        "id": "10-adversarial-paragraphs-2",
        "surface": "Adversarial instruction-following — distinct first words + exact count",
        "prompt": (
            "Write exactly 2 paragraphs, separated by a blank line. Each paragraph must "
            "contain exactly 3 sentences. No two sentences in your response may begin with "
            "the same word. The word \"blue\" must appear exactly 4 times in the whole "
            "response. Do not use any question marks. Answer with only the 2 paragraphs."
        ),
        "scorer": "constraint_paragraphs",
        "n_paragraphs": 2,
        "sentences_per": [3, 3],
        "first_words_distinct": True,
        "word_counts": {"blue": 4},
        "banned_chars": ["?"],
        "expected": "2 paragraphs 3/3, distinct first words, 'blue' x4, no '?'",
        "notes": ("Satisfiability proven by construction; first-word distinctness is the "
                  "sneaky constraint. Bad answer repeats first word 'morning'."),
        "good": T10_GOOD, "bad": T10_BAD,
    },
    {
        "id": "11-adversarial-list",
        "surface": "Adversarial instruction-following — alternating line starts + length cap",
        "prompt": (
            "Write exactly 7 lines. Each line must start with \"- \" (a dash and a space). "
            "Lines 1, 3, 5, and 7 must each begin with a word starting with the letter A; "
            "lines 2, 4, and 6 must each begin with a word starting with the letter B. "
            "No line may be longer than 40 characters. The word \"done\" must appear exactly "
            "once in the whole response. Answer with only the 7 lines."
        ),
        "scorer": "constraint_list",
        "n_lines": 7,
        "line_prefix": "- ",
        "odd_start": "A",
        "even_start": "B",
        "max_len": 40,
        "word_counts": {"done": 1},
        "expected": "7 lines, A/B alternation, <=40 chars, 'done' x1",
        "notes": "Satisfiability proven by construction; bad answer has 'done' twice.",
        "good": T11_GOOD, "bad": T11_BAD,
    },
    {
        "id": "12-longctx-conflicting-2",
        "surface": "Long-context precision — near-duplicate figures, only one matches",
        "prompt": T12_PASSAGE,
        "scorer": "numeric_tolerance",
        "expected": 8.7,
        "tolerance": 0.05,
        "notes": ("Correct: taproom division Q2 figure $8.7M (buried mid-paragraph). Distractor: "
                  "company-wide $8.2M (prominent standalone sentence). Tolerance 0.05 cleanly "
                  "separates them."),
        "good": "8.7", "bad": "8.2",
    },
    {
        "id": "13-longctx-count",
        "surface": "Long-context precision — exact word count with near-miss distractors",
        "prompt": T13_PASSAGE,
        "scorer": "numeric_tolerance",
        "expected": T13_EXPECTED,
        "tolerance": 0.5,
        "notes": (f"Ground truth: {T13_EXPECTED} exact 'reactor' tokens (letter-tokenized; "
                  "'reactors' and possessives excluded). Distractor answers: naive substring "
                  "counts or inclusion of plurals."),
        "good": str(T13_EXPECTED), "bad": str(T13_EXPECTED + 2),
    },
    {
        "id": "14-temporal",
        "surface": "Temporal reasoning — date arithmetic with weekday constraint",
        "prompt": (
            "A treaty was signed on 2026-03-14. An embargo began 41 days after the treaty "
            "was signed. A summit opened on the first Monday strictly after the embargo "
            "began. On what date did the summit open? Answer with ONLY the date in "
            "YYYY-MM-DD format."
        ),
        "scorer": "digits_strict",
        "expected": T14_EXPECTED,
        "notes": ("Ground truth via datetime: embargo 2026-04-24 (Friday); first Monday after "
                  "is 2026-04-27. Trap: answering the embargo date, or the Monday of the "
                  "embargo week."),
        "good": "2026-04-27", "bad": "2026-04-24",
    },
    {
        "id": "15-code-caesar",
        "surface": "Hard code — Caesar decode, backward shift, wrap + negative",
        "prompt": (
            "Write a Python function named caesar_decode that takes a string text and an "
            "integer shift, and returns text with every letter shifted BACKWARD by shift "
            "positions in the alphabet (wrapping around, so 'B' shifted back by 1 becomes 'A' "
            "and 'A' becomes 'Z'). Preserve uppercase/lowercase; leave non-letters unchanged; "
            "handle any integer shift (including negative and larger than 26). "
            "Respond with ONLY the code, no explanation and no markdown fences."
        ),
        "scorer": "code_function_deep_tests_args",
        "function": "caesar_decode",
        "expected": "all 10 hidden tests pass",
        "hidden_tests": [[[t, s], w] for (t, s), w in zip(T15_TESTS, T15_WANT)],
        "notes": ("Expected values verified against an independent reference implementation. "
                  "Traps: forward-vs-backward (the classic error), shift 23 == -3, shift 27, "
                  "negative shift, empty string."),
        "good": REF_CAESAR, "bad": BAD_CAESAR,
    },
    {
        "id": "16-code-roman",
        "surface": "Hard code — Roman numerals, subtractive notation",
        "prompt": (
            "Write a Python function named roman_to_int that takes a string of uppercase "
            "Roman numeral characters (I, V, X, L, C, D, M) and returns its integer value, "
            "applying standard subtractive notation (IV=4, IX=9, XL=40, XC=90, CD=400, CM=900). "
            "Respond with ONLY the code, no explanation and no markdown fences."
        ),
        "scorer": "code_function_deep_tests",
        "function": "roman_to_int",
        "expected": "all 12 hidden tests pass",
        "hidden_tests": [[x, w] for x, w in zip(T16_TESTS, T16_WANT)],
        "notes": ("Expected values are standard. Trap: summing values without subtractive "
                  "notation (IV->6, MCMXCIV wrong)."),
        "good": REF_ROMAN, "bad": BAD_ROMAN,
    },
]

assert len(TASKS) == 16, len(TASKS)

# ---------------------------------------------------------------- verify
def main():
    doc = {
        "benchmark": "swarm-capability-probe-v4",
        "created": "2026-10-18",
        "notes": ("Adversarial suite v4. v3 (8 tasks) found no mechanism beating plain "
                  "gpt-oss-120b but n=8 made nothing significant and run-to-run variance was "
                  "large. v4 doubles the tasks (16), runs every task 3x per mechanism, and "
                  "tests three mechanisms: plain 120b baseline, per-task best routing "
                  "(code tasks -> nemotron-super, from v3 evidence), and the revise loop with "
                  "120b as generator. All scorers mechanical, no LLM-as-judge. Every task "
                  "verified: reference-good passes, plausible-bad fails."),
        "tasks": [{k: v for k, v in t.items() if k not in ("good", "bad")}
                  for t in TASKS],
    }
    with open(os.path.join(HERE, "tasks-v4.json"), "w") as f:
        json.dump(doc, f, indent=2)

    fails = []
    for t in TASKS:
        scorer = SCORERS[t["scorer"]]
        good_ok, good_detail = scorer(t["good"], t)
        bad_ok, bad_detail = scorer(t["bad"], t)
        status = "OK " if (good_ok and not bad_ok) else "FAIL"
        if not (good_ok and not bad_ok):
            fails.append(t["id"])
        print(f"[{status}] {t['id']}: good={'PASS' if good_ok else 'FAIL'} "
              f"({good_detail[:80]}) bad={'PASS' if bad_ok else 'FAIL'} "
              f"({bad_detail[:80]})")
    if fails:
        print(f"\nVERIFY FAILED for: {fails}")
        sys.exit(1)
    print(f"\nAll {len(TASKS)} tasks verified: good passes, bad fails.")

if __name__ == "__main__":
    main()
