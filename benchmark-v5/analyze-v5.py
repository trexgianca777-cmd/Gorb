#!/usr/bin/env python3
"""analyze-v5.py — aggregate cycle-1 results and render the verdict.

Win criteria (pre-registered):
  1. mechanism mean per-task pass rate > plain mean per-task pass rate, AND
  2. mechanism's failed-task set is a STRICT SUBSET of plain's failed-task
     set (fixes >= 1 task plain failed, breaks 0 tasks plain passed), AND
  3. paired sign test on per-task pass rates vs plain is significant
     (one-sided p < 0.05).
A task "fails" for a mechanism if its pass rate < 0.5.
"""
import importlib.util
import json
import math
import os

BASE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)

RAW = os.path.join(BASE, "results", os.environ.get("ANALYZE_RAW_SUB", "raw"))
KEPT_JSON_A = os.environ.get("ANALYZE_KEPT_JSON", "tasks-v5-kept.json")


def sign_test_p(wins, losses):
    n = wins + losses
    if n == 0:
        return 1.0
    # one-sided: P(X >= wins) under p=0.5
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def main():
    kept = json.load(open(os.path.join(BASE, KEPT_JSON_A)))
    tasks = kept["tasks"]
    tids = kept["kept_ids"]
    mechs = sorted(os.listdir(RAW)) if os.path.isdir(RAW) else []
    rates = {}  # mech -> {tid: pass_rate}
    for mech in mechs:
        rates[mech] = {}
        for t in tasks:
            tid = t["id"]
            cells = []
            tdir = os.path.join(RAW, mech, tid)
            if os.path.isdir(tdir):
                for repdir in sorted(os.listdir(tdir)):
                    if not repdir.startswith("rep"):
                        continue
                    rdir = os.path.join(tdir, repdir)
                    for fn in sorted(os.listdir(rdir)):
                        if not fn.endswith(".txt") or fn == "model.txt":
                            continue
                        with open(os.path.join(rdir, fn),
                                  encoding="utf-8",
                                  errors="replace") as f:
                            txt = f.read()
                        if txt.strip() == "NO-OUTPUT":
                            cells.append(False)
                            continue
                        try:
                            ok, _ = score_v5.SCORERS[t["scorer"]](txt, t)
                        except Exception:
                            ok = False
                        cells.append(bool(ok))
            rates[mech][tid] = (sum(cells) / len(cells)) if cells else None
    print(f"{'MECH':10s} " + " ".join(f"{t[:4]:>6s}" for t in tids))
    means = {}
    for mech in mechs:
        row = []
        vals = []
        for tid in tids:
            r = rates[mech][tid]
            if r is None:
                row.append("   -  ")
            else:
                row.append(f"{r:>6.2f}")
                vals.append(r)
        means[mech] = sum(vals) / len(vals) if vals else 0.0
        print(f"{mech:10s} " + " ".join(row) + f"  mean={means[mech]:.3f}")
    print()
    plain = rates.get("plain", {})
    plain_fail = {tid for tid in tids
                  if plain.get(tid) is not None and plain[tid] < 0.5}
    for mech in mechs:
        if mech == "plain":
            continue
        m = rates[mech]
        wins = sum(1 for tid in tids
                   if m.get(tid) is not None and plain.get(tid) is not None
                   and m[tid] > plain[tid])
        losses = sum(1 for tid in tids
                     if m.get(tid) is not None and plain.get(tid) is not None
                     and m[tid] < plain[tid])
        m_fail = {tid for tid in tids
                  if m.get(tid) is not None and m[tid] < 0.5}
        fixes = plain_fail - m_fail
        breaks = m_fail - plain_fail
        p = sign_test_p(wins, losses)
        strict_subset = len(fixes) >= 1 and len(breaks) == 0
        win = means[mech] > means.get("plain", 0) and strict_subset and p < 0.05
        print(f"{mech}: wins={wins} losses={losses} p={p:.4f} "
              f"fixes={sorted(fixes)} breaks={sorted(breaks)} "
              f"strict_subset={strict_subset} -> {'WIN' if win else 'no win'}")
    out = os.path.join(BASE, "results", os.environ.get("ANALYZE_OUT", "analysis-v5.json"))
    with open(out, "w") as f:
        json.dump({"rates": rates, "means": means}, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
