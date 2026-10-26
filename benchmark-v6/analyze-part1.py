#!/usr/bin/env python3
"""analyze-part1.py — paired comparison of each candidate vs baseline revise.

Reads results/part1/<mech>/<task>/rep1/meta.json. Final pass per run:
  sv -> meta['final_original_pass']; others -> last attempt's pass
  (falls back to verifying the saved answer file).
Sign test: wins = cand pass & baseline fail; losses = cand fail & baseline pass.
"""
import json
import math
import os
import sys

V6 = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(V6, "results", "part1")
TASKS = ["c1-expr-eval-3", "c10-sexpr", "l1-knights-6", "p3-unicode-json",
         "p8-bizdays", "p9-sexpr-let", "q3-zebra-5", "q8-mastermind",
         "r5-fifty-words", "r8-no-e", "w2-word-count", "w5-lines-words"]
MECHS = ["baseline", "ce", "mh", "kb", "ad", "sv"]


def final_pass(mech, task):
    mp = os.path.join(R, mech, task, "rep1", "meta.json")
    if not os.path.exists(mp):
        return None
    m = json.load(open(mp))
    if mech == "sv":
        return bool(m.get("final_original_pass"))
    atts = m.get("attempts", [])
    if atts:
        return bool(atts[-1].get("pass"))
    return None


def ncalls(mech, task):
    mp = os.path.join(R, mech, task, "rep1", "meta.json")
    if not os.path.exists(mp):
        return None
    return len(json.load(open(mp)).get("calls", []))


def tokchars(mech, task):
    mp = os.path.join(R, mech, task, "rep1", "meta.json")
    if not os.path.exists(mp):
        return None
    return sum(c.get("prompt_chars", 0) + c.get("completion_chars", 0)
               for c in json.load(open(mp)).get("calls", []))


def sign_p(wins, losses):
    n = wins + losses
    if n == 0:
        return 1.0
    # one-sided: P(X >= wins), X ~ Binomial(n, 0.5)
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def main():
    base = {t: final_pass("baseline", t) for t in TASKS}
    print("baseline passes:", sum(1 for v in base.values() if v),
          "/", sum(1 for v in base.values() if v is not None))
    print(f"{'mech':10} {'pass':>6} {'wins':>5} {'loss':>5} {'draw':>5} "
          f"{'p':>8} {'avg_calls':>9} {'avg_tok':>9}")
    for mech in MECHS[1:]:
        wins = losses = draws = 0
        details = []
        for t in TASKS:
            b, c = base[t], final_pass(mech, t)
            if b is None or c is None:
                details.append((t, "?"))
                continue
            if c and not b:
                wins += 1
                details.append((t, "WIN"))
            elif b and not c:
                losses += 1
                details.append((t, "LOSS"))
            else:
                draws += 1
                details.append((t, "draw"))
        p = sign_p(wins, losses)
        nc = [ncalls(mech, t) for t in TASKS]
        nc = [x for x in nc if x is not None]
        tk = [tokchars(mech, t) for t in TASKS]
        tk = [x for x in tk if x is not None]
        npass = sum(1 for t in TASKS if final_pass(mech, t))
        print(f"{mech:10} {npass:>4}/12 {wins:>5} {losses:>5} {draws:>5} "
              f"{p:>8.4f} {sum(nc)/len(nc):>9.2f} {sum(tk)/len(tk):>9.0f}")
        print("   ", " ".join(f"{t}:{s}" for t, s in details))


if __name__ == "__main__":
    main()
