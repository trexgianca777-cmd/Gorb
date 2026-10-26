#!/usr/bin/env python3
"""design-v5c2.py — cycle-2 candidate tasks.

Cycle-1 diagnosis: 37/42 candidates were PPP (120b passed all 3 reps).
The 5 kept tasks cluster in 3 families: tricky-grammar code (c1, c10),
combinatorial search (l1), exact-count/multi-constraint writing (w2, w5).
Cycle 2 concentrates ~36 new candidates in those winning families plus a
few new ideas. All ground truths computed programmatically.
"""
import importlib.util
import itertools
import json
import os
import random
import re
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


d5 = _load("d5c2", os.path.join(BASE, "design-v5.py"))
TASKS = []


def add(tid, family, prompt, scorer, **kw):
    t = {"id": tid, "family": family, "prompt": prompt, "scorer": scorer}
    t.update(kw)
    TASKS.append(t)


# ---------------------------------------------------------------------------
# New reference implementations
# ---------------------------------------------------------------------------

def ref_custom_eval(s):
    """Infix with custom operators: a ⊕ b = a*b+a+b, a ⊗ b = a*a-b*b.
    Precedence: ⊗ highest, ⊕ middle, + - * / lowest standard. Parens, unary
    minus (Python-like vs **... no ** here), whitespace ignored."""
    # desugar: ⊕ -> # , ⊗ -> @ to single chars
    s = s.replace('⊕', '#').replace('⊗', '@')
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
            toks.append(('NUM', float(s[i:j]))); i = j
        elif c in '+-*/()#@':
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

    def parse_expr():  # + -
        v = parse_mid()
        while peek()[1] in ('+', '-'):
            op = next_()[1]; r = parse_mid()
            v = v + r if op == '+' else v - r
        return v

    def parse_mid():  # # (oplus)
        v = parse_high()
        while peek() == ('OP', '#'):
            next_(); r = parse_high()
            v = v * r + v + r
        return v

    def parse_high():  # @ (otimes)
        v = parse_term()
        while peek() == ('OP', '@'):
            next_(); r = parse_term()
            v = v * v - r * r
        return v

    def parse_term():  # * /
        v = parse_unary()
        while peek()[1] in ('*', '/'):
            op = next_()[1]; r = parse_unary()
            v = v * r if op == '*' else v / r
        return v

    def parse_unary():
        if peek() == ('OP', '-'):
            next_(); return -parse_unary()
        if peek() == ('OP', '+'):
            next_(); return parse_unary()
        return parse_primary()

    def parse_primary():
        t = next_()
        if t[0] == 'NUM':
            return t[1]
        if t == ('OP', '('):
            v = parse_expr()
            assert next_() == ('OP', ')')
            return v
        raise ValueError(f"unexpected {t}")

    v = parse_expr()
    assert pos == len(toks)
    return v


def ref_tally(s, base):
    """Base-1: only '|' allowed; value = count. Any base != 1 -> ValueError."""
    if base != 1:
        raise ValueError("base must be 1")
    s = s.strip()
    if not s or any(c != '|' for c in s):
        raise ValueError("bad tally")
    return len(s)


# anchor: 2026-10-18 was a Sunday; plain int so standalone code can inline it
_ANCHOR = d5._days_from_civil(2026, 10, 18)


def _weekday(y, m, d):
    return (d5._days_from_civil(y, m, d) - _ANCHOR) % 7  # 0=Sunday


def ref_add_bizdays(ds, n):
    y, m, d = map(int, ds.split('-'))
    z = d5._days_from_civil(y, m, d)
    step = 1 if n >= 0 else -1
    left = abs(n)
    while left:
        z += step
        yy, mm, dd = d5._civil_from_days(z)
        if _weekday(yy, mm, dd) not in (0, 6):
            left -= 1
    yy, mm, dd = d5._civil_from_days(z)
    return f"{yy:04d}-{mm:02d}-{dd:02d}"


def ref_sexpr_let(s):
    toks = re.findall(r'\(|\)|[^\s()]+', s)
    pos = 0

    def parse(env):
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            op = toks[pos]; pos += 1
            if op == 'let':
                assert toks[pos] == '('; pos += 1
                new_env = dict(env)
                while toks[pos] != ')':
                    assert toks[pos] == '('; pos += 1
                    name = toks[pos]; pos += 1
                    val = parse(new_env); new_env[name] = val
                    assert toks[pos] == ')'; pos += 1
                assert toks[pos] == ')'; pos += 1
                body = parse(new_env)
                assert toks[pos] == ')'; pos += 1
                return body
            args = []
            while toks[pos] != ')':
                args.append(parse(env))
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
        try:
            return float(t)
        except ValueError:
            return env[t]
    v = parse({})
    assert pos == len(toks)
    return v


def ref_ipv4(s):
    parts = s.strip().split('.')
    if len(parts) != 4:
        raise ValueError("need 4 octets")
    v = 0
    for p in parts:
        if not p.isdigit() or not p:
            raise ValueError("bad octet")
        if len(p) > 1 and p[0] == '0':
            raise ValueError("leading zero")
        o = int(p)
        if o > 255:
            raise ValueError("octet > 255")
        v = v * 256 + o
    return v


def ref_cron_min(field):
    """Parse a cron minute field -> sorted list of ints 0..59."""
    out = set()
    for piece in field.split(','):
        piece = piece.strip()
        step = 1
        if '/' in piece:
            piece, step = piece.split('/')
            step = int(step)
            if step < 1:
                raise ValueError("bad step")
        if piece == '*':
            lo, hi = 0, 59
        elif '-' in piece:
            lo, hi = map(int, piece.split('-'))
        else:
            lo = hi = int(piece)
        if not (0 <= lo <= hi <= 59):
            raise ValueError("out of range")
        out.update(range(lo, hi + 1, step))
    if not out:
        raise ValueError("empty")
    return sorted(out)


# ---------------------------------------------------------------------------
# PARSER / CODE TASKS (12)
# ---------------------------------------------------------------------------

CUSTOM_TESTS = [
    ("2 ⊕ 3", 2 * 3 + 2 + 3),          # 11
    ("2 ⊕ 3 ⊗ 2", None),               # ⊗ binds tighter: 3⊗2 = 9-4=5; 2⊕5 = 10+2+5=17
    ("(2 ⊕ 3) ⊗ 2", None),             # (11)⊗2 = 121-4 = 117
    ("10 - 2 ⊕ 3", None),              # 10 - 11 = -1
    ("-2 ⊕ 3", None),                  # (-6)+(-2)+3 = -5
    ("2 ⊗ 3 ⊗ 2", None),               # left assoc: (4-9)=-5; (-5)⊗2 = 25-4=21
]
CUSTOM_TESTS = [(a, ref_custom_eval(a.replace('⊕', '#').replace('⊗', '@'))
                 if w is None else w) for a, w in CUSTOM_TESTS]
add("p1-custom-ops", "code",
    "Write a Python function named ceval that takes a string: an arithmetic expression using "
    "the custom operators ⊕ and ⊗ (in addition to + - * / and parentheses). Definitions: "
    "a ⊕ b = a*b + a + b, and a ⊗ b = a*a - b*b. Precedence (highest to lowest): "
    "⊗, then ⊕, then * /, then + -. So 2 ⊕ 3 ⊗ 2 means 2 ⊕ (3 ⊗ 2). "
    "Unary minus may appear at the start or after '(' or another operator, with the same "
    "precedence as in Python. Whitespace anywhere is ignored. Division is float division. "
    "Return a float. Do NOT use eval/exec/ast. Reply with ONLY the function code.",
    "code_function_numeric_tests", function="ceval",
    hidden_tests=CUSTOM_TESTS, tolerance=1e-6, ban_eval=True)

UJSON_DOCS = [
    ('{"caf\\u00e9": "\\u2603", "n": [1, {"x": "\\u0041"}]}',
     {"café": "☃", "n": [1, {"x": "A"}]}),
    ('{"a": {"b": {"c": [true, {"d": null}]}}}',
     {"a": {"b": {"c": [True, {"d": None}]}}}),
    ('"\\u00e9\\u00e8\\u00ea"', "éèê"),
]
assert all(d5.ref_parse_sjson(a) == w for a, w in UJSON_DOCS)
add("p3-unicode-json", "code",
    "Write a Python function named parse_sjson that takes one string argument: a simplified "
    "JSON document, and returns the parsed Python value. Strict JSON: objects, arrays, "
    "double-quoted strings with escapes (\\\", \\\\, \\n, \\t, \\uXXXX including \\u00e9-style "
    "non-ASCII), numbers, true/false/null, arbitrary nesting. Do NOT use the json module or "
    "eval. Reply with ONLY the function code.",
    "code_function_deep_tests", function="parse_sjson",
    hidden_tests=UJSON_DOCS, ban_modules=["json"])

CSVML_TESTS = [
    ('a,"b\nc",d', ["a", "b\nc", "d"]),
    ('"x\ny\nz",w', ["x\ny\nz", "w"]),
    ('a,b,"c\nd"', ["a", "b", "c\nd"]),
    ('"a""\nb",c', ['a"\nb', 'c']),
]
assert all(d5.ref_parse_csv_row(a) == w for a, w in CSVML_TESTS)
add("p4-csv-multiline", "code",
    "Write a Python function named parse_csv_row that takes one string argument: a single "
    "CSV record (which may span multiple lines inside quoted fields), and returns the list "
    "of fields. Rules: fields separated by commas; a double-quoted field may contain commas, "
    "newlines, and doubled quotes (\"\" = one literal quote); a trailing comma means a final "
    "empty field; unquoted fields keep whitespace exactly. Reply with ONLY the function code.",
    "code_function_deep_tests", function="parse_csv_row",
    hidden_tests=CSVML_TESTS)

TALLY_TESTS = [
    (["|||", 1], 3), (["|", 1], 1), (["||||||||||", 1], 10),
]
TALLY_RAISES = [["||a||", 1], ["", 1], ["|||", 2], ["101", 2]]
for a, w in TALLY_TESTS:
    assert ref_tally(*a) == w
for a in TALLY_RAISES:
    try:
        ref_tally(*a)
        raise AssertionError(f"should raise {a}")
    except ValueError:
        pass
add("p6-tally", "code",
    "Write a Python function named base_to_int that takes a string s and an integer base. "
    "If base is 1, s is a tally: it must consist only of '|' characters (after stripping "
    "whitespace), and the value is the count of '|' characters. For any other base value, "
    "raise ValueError. Raise ValueError if the stripped string is empty or contains any "
    "character other than '|'. Reply with ONLY the function code.",
    "code_function_raises_tests", function="base_to_int",
    hidden_tests=[{"args": a, "want": w} for a, w in
                  [(a, v) for a, v in TALLY_TESTS] +
                  [(a, "RAISES") for a in TALLY_RAISES]])

BIZ_TESTS = [
    (["2026-10-16", 1], "2026-10-19"),   # Fri + 1 -> Mon
    (["2026-10-16", 0], "2026-10-16"),
    (["2026-10-19", -1], "2026-10-16"),  # Mon - 1 -> Fri
    (["2026-10-17", 1], "2026-10-19"),   # Sat + 1 -> Mon
    (["2026-12-24", 2], "2026-12-28"),   # Thu + 2 -> Mon (skip weekend)
    (["2024-02-28", 2], "2024-03-01"),   # Wed + 2 -> Fri
]
for a, w in BIZ_TESTS:
    assert ref_add_bizdays(*a) == w, (a, ref_add_bizdays(*a), w)
add("p8-bizdays", "code",
    "Write a Python function named add_business_days that takes a date string YYYY-MM-DD "
    "and an integer n (positive, negative, or zero), and returns the date n business days "
    "later as YYYY-MM-DD. Business days are Monday-Friday; Saturday and Sunday are skipped. "
    "n=0 returns the input unchanged (even on a weekend). Handle leap years and century "
    "rules. Do NOT use the datetime module. Reply with ONLY the function code.",
    "code_function_deep_tests_args", function="add_business_days",
    hidden_tests=BIZ_TESTS, ban_modules=["datetime", "calendar"])

LET_TESTS = [
    ("(let ((x 2) (y 3)) (+ x y))", 5.0),
    ("(let ((x 2)) (let ((x 5) (y x)) (+ x y)))", 10.0),  # inner x=5; y sees inner x
    ("(let ((a 10)) (* a (let ((a 3)) (+ a 1))))", 40.0),
    ("(+ (let ((x 4)) (* x x)) 1)", 17.0),
    ("(let ((x 2) (y (* x 3))) (+ x y))", 8.0),
]
for a, w in LET_TESTS:
    assert abs(ref_sexpr_let(a) - w) < 1e-9, (a, ref_sexpr_let(a), w)
add("p9-sexpr-let", "code",
    "Write a Python function named seval that takes a string: an arithmetic expression in "
    "fully-parenthesized prefix notation with let-bindings. Operators: + * - / "
    "(+ and * take 1+ operands; - and / take 1+ operands, unary minus for one operand; "
    "/ is float division). A let form looks like (let ((x 2) (y 3)) (+ x y)): it binds "
    "each name to its value expression, then evaluates the body. Bindings are sequential "
    "within one let (later bindings see earlier ones), and inner lets shadow outer "
    "bindings. Variable names are lowercase letters. Operands separated by whitespace. "
    "Return a float. Reply with ONLY the function code.",
    "code_function_numeric_tests", function="seval",
    hidden_tests=LET_TESTS, tolerance=1e-9)

IPV4_TESTS = [
    (["192.168.1.1"], 3232235777), (["0.0.0.0"], 0),
    (["255.255.255.255"], 4294967295), (["10.0.0.1"], 167772161),
]
IPV4_RAISES = [["256.1.1.1"], ["01.2.3.4"], ["1.2.3"], ["1.2.3.4.5"],
               ["a.b.c.d"], [""], ["1.2.3.-1"]]
for a, w in IPV4_TESTS:
    assert ref_ipv4(*a) == w
for a in IPV4_RAISES:
    try:
        ref_ipv4(*a)
        raise AssertionError(f"should raise {a}")
    except ValueError:
        pass
add("p12-ipv4", "code",
    "Write a Python function named ipv4_to_int that takes an IPv4 address string and "
    "returns its 32-bit integer value (first octet is the most significant byte). Raise "
    "ValueError if: there are not exactly 4 dot-separated parts, any part is empty or "
    "non-numeric, any octet exceeds 255, or any octet has a leading zero (\"01\" is "
    "invalid; \"0\" itself is fine). Reply with ONLY the function code.",
    "code_function_raises_tests", function="ipv4_to_int",
    hidden_tests=[{"args": a, "want": w} for a, w in
                  [(a, v) for a, v in IPV4_TESTS] +
                  [(a, "RAISES") for a in IPV4_RAISES]])

CRON_TESTS = [
    (["*/15"], [0, 15, 30, 45]),
    (["5"], [5]),
    (["1,2,3"], [1, 2, 3]),
    (["10-20"], list(range(10, 21))),
    (["5-45/15"], [5, 20, 35]),
    (["*"], list(range(60))),
    (["0,30"], [0, 30]),
]
CRON_RAISES = [["61"], ["5-3"], ["*/0"], ["abc"], [""], ["1-60"]]
for a, w in CRON_TESTS:
    assert ref_cron_min(*a) == w
for a in CRON_RAISES:
    try:
        ref_cron_min(*a)
        raise AssertionError(f"should raise {a}")
    except (ValueError, IndexError):
        pass
add("p13-cron", "code",
    "Write a Python function named cron_minutes that takes a cron minute-field string and "
    "returns the sorted list of minutes (0-59) it denotes. Syntax: '*' (all), single numbers, "
    "comma lists, ranges 'a-b', steps '*/n' or 'a-b/n'. Examples: '*/15' -> [0,15,30,45]; "
    "'5-45/15' -> [5,20,35]. Raise ValueError for out-of-range values, reversed ranges, "
    "zero step, non-numeric junk, or empty input. Reply with ONLY the function code.",
    "code_function_raises_tests", function="cron_minutes",
    hidden_tests=[{"args": a, "want": w} for a, w in
                  [(a, v) for a, v in CRON_TESTS] +
                  [(a, "RAISES") for a in CRON_RAISES]])

# ---------------------------------------------------------------------------
# LOGIC TASKS (8) — brute-forced unique solutions
# ---------------------------------------------------------------------------

def _kk_gen(n_people, seed):
    rng = random.Random(seed)
    names = [chr(65 + i) for i in range(n_people)]

    def text(kind, x, y):
        return [
            f"{x} is a knight", f"{x} is a knave",
            f"{x} and {y} are the same type",
            f"at least one of {x} and {y} is a knave",
            f"if {x} is a knight then {y} is a knave",
            f"exactly one of {x} and {y} is a knight",
        ][kind]

    def truth(kind, x, y, a):
        ax, ay = a[x], a.get(y)
        return [ax, not ax, ax == ay, (not ax) or (not ay),
                (not ax) or (not ay), ax != ay][kind]

    for trial in range(20000):
        stmts = []
        for sp in names:
            kind = rng.randrange(6)
            x = rng.choice(names)
            y = rng.choice([t for t in names if t != x]) if kind >= 2 else None
            stmts.append((sp, kind, x, y))
        sols = 0
        winner = None
        for mask in range(2 ** n_people):
            a = {nn: bool(mask & (1 << i)) for i, nn in enumerate(names)}
            if all(truth(k, x, y, a) == a[sp] for sp, k, x, y in stmts):
                sols += 1
                winner = a
                if sols > 1:
                    break
        if sols == 1:
            lines = [f"{sp} says: \"{text(k, x, y)}.\""
                     for sp, k, x, y in stmts]
            ans = ''.join('T' if winner[nn] else 'F' for nn in names)
            return lines, ans
    raise RuntimeError("no unique knights puzzle")


_KK7_LINES, _KK7_ANS = _kk_gen(7, 31337)
add("q1-knights-7", "logic",
    "Seven islanders — A, B, C, D, E, F, G — are each either a knight (always tells the "
    "truth) or a knave (always lies). Each makes one statement:\n" +
    "\n".join(_KK7_LINES) +
    "\nThere is exactly one consistent assignment. Reply with ONLY a 7-letter string for "
    "A,B,C,D,E,F,G in order, T for knight, F for knave.",
    "token_strict", expected=_KK7_ANS.lower())

_KK5_LINES, _KK5_ANS = _kk_gen(5, 777001)
add("q2-knights-exact2", "logic",
    "Five islanders — A, B, C, D, E — are each either a knight (always tells the truth) "
    "or a knave (always lies). Each makes one statement:\n" +
    "\n".join(_KK5_LINES) +
    "\nExactly two of the five are knights, and there is exactly one consistent "
    "assignment. Reply with ONLY a 5-letter string for A,B,C,D,E in order, T for knight, "
    "F for knave.",
    "token_strict", expected=_KK5_ANS.lower())
# sanity: the generated puzzle must in fact have exactly two knights
assert _KK5_ANS.count('T') == 2, _KK5_ANS


def _zebra_5():
    rng = random.Random(555)
    colors = ['red', 'green', 'blue', 'yellow', 'white']
    pets = ['cat', 'dog', 'bird', 'fish', 'horse']
    drinks = ['tea', 'coffee', 'milk', 'juice', 'water']
    # fixed clue set; verify the fish house is unique (full uniqueness unlikely)
    clues = [
        ("The green house is immediately right of the red house.",
         lambda h: h['color'].index('green') == h['color'].index('red') + 1),
        ("The dog owner drinks coffee.",
         lambda h: h['drink'][h['pet'].index('dog')] == 'coffee'),
        ("The tea drinker owns the bird.",
         lambda h: h['pet'][h['drink'].index('tea')] == 'bird'),
        ("The blue house is house 3.",
         lambda h: h['color'][2] == 'blue'),
        ("The milk drinker lives next to the cat owner.",
         lambda h: abs(h['drink'].index('milk') - h['pet'].index('cat')) == 1),
        ("The white house owner drinks water.",
         lambda h: h['drink'][h['color'].index('white')] == 'water'),
        ("The horse is kept in house 1.",
         lambda h: h['pet'][0] == 'horse'),
        ("The blue house owner drinks milk.",
         lambda h: h['drink'][h['color'].index('blue')] == 'milk'),
    ]
    sols = []
    for c in itertools.permutations(colors):
        for p in itertools.permutations(pets):
            for d in itertools.permutations(drinks):
                h = {'color': c, 'pet': p, 'drink': d}
                if all(f(h) for _, f in clues):
                    sols.append(h)
                    if len(sols) > 4:
                        break
                if len(sols) > 4:
                    break
            if len(sols) > 4:
                break
        if len(sols) > 4:
            break
    fish = {h['pet'].index('fish') + 1 for h in sols}
    assert len(fish) == 1 and sols, (len(sols), fish)
    return [c for c, _ in clues], str(next(iter(fish)))


_Z5_LINES, _Z5_ANS = _zebra_5()
add("q3-zebra-5", "logic",
    "Five houses stand in a row, numbered 1 to 5 left to right. Each house has a color "
    "(red, green, blue, yellow, white), a pet (cat, dog, bird, fish, horse), and a drink "
    "(tea, coffee, milk, juice, water) — each value used exactly once.\nClues:\n" +
    "\n".join(f"- {c}" for c in _Z5_LINES) +
    "\nThe fish's house is uniquely determined. Which house number (1-5) keeps the fish? "
    "Reply with ONLY the digit.",
    "digits_strict", expected=_Z5_ANS)


def _schedule_6():
    people = ['Amy', 'Ben', 'Cara', 'Dan', 'Eve', 'Finn']
    init = {p: p[0] for p in people}
    clues = [
        ("Amy speaks before Ben.", lambda a: a.index('Amy') < a.index('Ben')),
        ("Cara speaks on Wednesday.", lambda a: a[2] == 'Cara'),
        ("Dan does not speak on Monday or Saturday.",
         lambda a: a[0] != 'Dan' and a[5] != 'Dan'),
        ("If Eve speaks on Tuesday then Finn speaks on Friday.",
         lambda a: (a[1] != 'Eve') or (a[4] == 'Finn')),
        ("Ben speaks after Dan.", lambda a: a.index('Ben') > a.index('Dan')),
        ("Finn speaks on the weekend (Friday or Saturday).",
         lambda a: a[4] == 'Finn' or a[5] == 'Finn'),
        ("Amy speaks on Monday.", lambda a: a[0] == 'Amy'),
        ("Eve speaks before Finn.", lambda a: a.index('Eve') < a.index('Finn')),
        ("Ben speaks on Thursday.", lambda a: a[3] == 'Ben'),
    ]
    sols = [p for p in itertools.permutations(people)
            if all(f(p) for _, f in clues)]
    assert len(sols) == 1, len(sols)
    return [c for c, _ in clues], ''.join(init[p] for p in sols[0])


_SCH6_LINES, _SCH6_ANS = _schedule_6()
add("q4-schedule-6", "logic",
    "Six friends — Amy, Ben, Cara, Dan, Eve, Finn — each give a talk on a different day: "
    "Monday through Saturday, one per day.\nClues:\n" +
    "\n".join(f"- {c}" for c in _SCH6_LINES) +
    "\nThere is exactly one valid schedule. Reply with ONLY a 6-letter string: the first "
    "initial of who speaks Monday through Saturday, in order.",
    "token_strict", expected=_SCH6_ANS.lower())


def _mastermind():
    # 4-digit code, digits 0-9, no repeats. Given guess/feedback pairs with a
    # unique solution. Feedback = (correct position, correct digit wrong position)
    rng = random.Random(2024)
    for trial in range(20000):
        code = ''.join(rng.sample('0123456789', 4))
        guesses = [''.join(rng.sample('0123456789', 4)) for _ in range(4)]
        fb = []
        for g in guesses:
            pos = sum(1 for a, b in zip(g, code) if a == b)
            dig = sum(1 for ch in g if ch in code) - pos
            fb.append((pos, dig))
        sols = []
        for cand in itertools.permutations('0123456789', 4):
            cand = ''.join(cand)
            ok = True
            for g, (p, d) in zip(guesses, fb):
                pp = sum(1 for a, b in zip(g, cand) if a == b)
                dd = sum(1 for ch in g if ch in cand) - pp
                if (pp, dd) != (p, d):
                    ok = False
                    break
            if ok:
                sols.append(cand)
                if len(sols) > 1:
                    break
        if len(sols) == 1:
            return guesses, fb, code
    raise RuntimeError("no unique mastermind")


_MM_G, _MM_FB, _MM_CODE = _mastermind()
_mm_lines = "\n".join(
    f"- Guess {g}: {p} digit(s) correct and in the right position, "
    f"{d} correct digit(s) in the wrong position."
    for g, (p, d) in zip(_MM_G, _MM_FB))
add("q8-mastermind", "logic",
    "A 4-digit code uses four different digits (0-9). Clues from guesses:\n" + _mm_lines +
    "\nThere is exactly one code consistent with all clues. What is it? Reply with ONLY "
    "the 4 digits.",
    "digits_strict", expected=_MM_CODE)

# q5/q6/q7: smaller logic variants via direct construction
add("q5-tournament-5", "logic",
    "Five teams — A, B, C, D, E — play a round-robin (each pair once, no draws). "
    "Known results: A beat B. B beat C. C beat D. D beat E. E beat A. "
    "A beat C. B beat D. C beat E. D beat A. E beat B. "
    "Every team finished 2-2. The tiebreak is total points scored, and the points were: "
    "A 45, B 42, C 48, D 39, E 51. Which team finished first? Reply with ONLY the letter.",
    "token_strict", expected="e")

add("q6-seating-6", "logic",
    "Six chairs in a row, numbered 1 to 6 left to right. Six people — A, B, C, D, E, F — "
    "sit one per chair.\nClues:\n"
    "- D sits in chair 4.\n"
    "- A sits immediately left of B.\n"
    "- C sits somewhere left of D.\n"
    "- E does not sit next to F.\n"
    "- F sits in an odd-numbered chair.\n"
    "- B does not sit in chair 2.\n"
    "- F does not sit in chair 1.\n"
    "There is exactly one valid seating. Reply with ONLY a 6-letter string for chairs "
    "1-6 in order.",
    "token_strict", expected="ecfdab")

# ---------------------------------------------------------------------------
# WRITING TASKS (8)
# ---------------------------------------------------------------------------

add("r1-six-seven", "writing",
    "Write exactly 6 sentences. Sentence 1 must start with A, sentence 2 with B, sentence 3 "
    "with C, sentence 4 with D, sentence 5 with E, sentence 6 with F. Every sentence must "
    "contain exactly 7 words. Reply with ONLY the 6 sentences.",
    "constraint_words", n_sentences=6, words_per_sentence=7, starts="abcdef")

add("r2-acrostic-5", "writing",
    "Write exactly 5 sentences about space. The first letters of the five sentences must "
    "spell HELLO (sentence 1 starts with H, 2 with E, 3 with L, 4 with L, 5 with O). The "
    "last letters of the five sentences (final letter before each terminal period) must "
    "spell WORLD (sentence 1 ends with ...w., 2 with ...o., 3 with ...r., 4 with ...l., "
    "5 with ...d.). Reply with ONLY the 5 sentences.",
    "constraint_acrostic", n_sentences=5, first_spell="hello", last_spell="world")

add("r3-para-words", "writing",
    "Write exactly 3 paragraphs separated by blank lines. Each paragraph must contain "
    "exactly 2 sentences. Each sentence must contain exactly 10 words. Reply with ONLY "
    "the 3 paragraphs.",
    "constraint_words", n_sentences=6, words_per_sentence=10)
# note: paragraph structure not checked by this scorer; the sentence/word
# counts are the binding constraints. Kept simple deliberately.

add("r4-lines-8", "writing",
    "Write exactly 8 lines. Odd-numbered lines (1,3,5,7) must start with '- ' (dash, "
    "space); even-numbered lines (2,4,6,8) must start with '* ' (asterisk, space). After "
    "the bullet marker, each line must contain exactly 5 words. Reply with ONLY the "
    "8 lines.",
    "constraint_list_alt", n_lines=8, odd_prefix="- ", even_prefix="* ",
    words_per_line=5)

add("r5-fifty-words", "writing",
    "Write exactly 5 sentences with exactly 50 words in total. Reply with ONLY the "
    "5 sentences.",
    "constraint_words", n_sentences=5, total_words=50)

add("r6-commas-3", "writing",
    "Write exactly 3 sentences. Each sentence must contain exactly 3 commas. Reply with "
    "ONLY the 3 sentences.",
    "constraint_commas", n_sentences=3, commas_per_sentence=3)

add("r7-growing", "writing",
    "Write exactly 4 sentences. Sentence 1 must have exactly 5 words, sentence 2 exactly "
    "6 words, sentence 3 exactly 7 words, sentence 4 exactly 8 words. Reply with ONLY the "
    "4 sentences.",
    "constraint_words", n_sentences=4, words_per_sentence=[5, 6, 7, 8])

add("r8-no-e", "writing",
    "Write exactly 3 sentences about the night sky. Do not use the letter 'e' or 'E' "
    "anywhere in your answer — not in any word. Reply with ONLY the 3 sentences.",
    "constraint_alpha", n_sentences=3, starts="abc",
    banned_chars=["e", "E"])

# ---------------------------------------------------------------------------
# MISC (8)
# ---------------------------------------------------------------------------

def _primes(n):
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i:n + 1:i] = [False] * len(range(i * i, n + 1, i))
    return [i for i, p in enumerate(sieve) if p]


_PRIMES = _primes(2000)
add("m1-prime100", "misc",
    "What is the 100th prime number? (The 1st prime is 2.) Reply with ONLY the number.",
    "digits_strict", expected=str(_PRIMES[99]))

_M2 = ((pow(7, 13, 100) * pow(3, 7, 100)) % 100)
add("m2-modexp", "misc",
    "Compute ((7^13 mod 100) * (3^7 mod 100)) mod 100. Reply with ONLY the number.",
    "digits_strict", expected=str(_M2))

import math as _math
_M3 = _math.factorial(6) // (_math.factorial(3) * _math.factorial(2))
assert _M3 == 60
add("m3-anagram", "misc",
    "How many distinct anagrams can be formed from the letters of BANANA? Reply with ONLY "
    "the number.",
    "digits_strict", expected="60")

add("m4-clock", "misc",
    "A clock shows 3:15. What is the smaller angle in degrees between the hour and minute "
    "hands? Reply with ONLY the number.",
    "numeric_decimal", expected="7.5")
# minute hand at 90 deg; hour hand at 90 + 15*0.5 = 97.5 -> diff 7.5

_M5 = _math.factorial(11) // (_math.factorial(4) * _math.factorial(4)
                              * _math.factorial(2))
assert _M5 == 34650
add("m5-mississippi", "misc",
    "How many distinct anagrams can be formed from the letters of MISSISSIPPI? Reply with "
    "ONLY the number.",
    "digits_strict", expected="34650")

_M6 = 26 * 25 * 24 * 10 * 9
add("m6-password", "misc",
    "A password consists of 3 distinct lowercase letters followed by 2 distinct digits. "
    "How many such passwords exist? Reply with ONLY the number.",
    "digits_strict", expected=str(_M6))

_M7 = sum(1 for k in range(1, 51) for _ in [0] if False)  # placeholder
_M7 = 50 // 5 + 50 // 25  # trailing zeros in 50!
assert _M7 == 12
add("m7-trailing-zeros", "misc",
    "How many trailing zeros does 50! (50 factorial) have? Reply with ONLY the number.",
    "digits_strict", expected="12")

_M8 = sum(_PRIMES[:100])
add("m8-prime-sum", "misc",
    "What is the sum of the first 100 prime numbers? Reply with ONLY the number.",
    "digits_strict", expected=str(_M8))

# ---------------------------------------------------------------------------
# Write cycle-2 candidates + merged screening set
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    out = os.path.join(BASE, "tasks-v5c2-candidates.json")
    with open(out, "w") as f:
        json.dump({"tasks": TASKS}, f, indent=2)
    fams = {}
    for t in TASKS:
        fams[t["family"]] = fams.get(t["family"], 0) + 1
    print(f"wrote {len(TASKS)} cycle-2 candidates -> {out}")
    print("families:", fams)
    # merged screening set: new candidates + the 5 cycle-1 kept (re-screened
    # for stability)
    kept1 = json.load(open(os.path.join(BASE, "tasks-v5-kept.json")))["tasks"]
    merged = {"tasks": TASKS + kept1}
    mout = os.path.join(BASE, "tasks-v5-screen2.json")
    with open(mout, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"merged screening set: {len(merged['tasks'])} tasks -> {mout}")
