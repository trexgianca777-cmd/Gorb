#!/usr/bin/env python3
"""analyze-v4.py — paired statistical analysis of benchmark v4 results.

Reads results/scores.json (from score-v4.py). For each mechanism pair
(route vs plain, revise vs plain): per-task win/loss/tie counts and a
one-sided binomial sign test (H0: mechanism no better than plain 120b).

Writes results/analysis.json and prints a markdown table for REPORT.md.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def sign_test_p(wins, losses):
    """One-sided p-value: P(X >= wins) for X ~ Binomial(wins+losses, 0.5)."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def main():
    scores = json.load(open(os.path.join(HERE, "results", "scores.json")))
    tasks = json.load(open(os.path.join(HERE, "tasks-v4.json")))["tasks"]
    tids = [t["id"] for t in tasks]

    # per-task fractions per mechanism
    frac = {}
    for mech, tdict in scores.items():
        frac[mech] = {}
        for tid in tids:
            cells = tdict.get(tid, {})
            passes = sum(1 for r in cells.values() if r["pass"])
            frac[mech][tid] = (passes, len(cells))

    out = {"per_task": {}, "mechanism_means": {}, "comparisons": {}}
    for mech in frac:
        fs = [p / n for p, n in frac[mech].values() if n > 0]
        out["mechanism_means"][mech] = sum(fs) / len(fs) if fs else 0.0

    for tid in tids:
        row = {m: f"{p}/{n}" if n else "missing"
               for m, d in frac.items() for p, n in [d[tid]]}
        # instability: reps disagree (some pass, some fail) within a mechanism
        unstable = [m for m, d in frac.items()
                    if 0 < d[tid][0] < d[tid][1]]
        row["unstable"] = unstable
        out["per_task"][tid] = row

    for challenger in ("route", "revise"):
        wins = losses = ties = 0
        detail = []
        for tid in tids:
            cp, cn = frac.get(challenger, {}).get(tid, (0, 0))
            pp, pn = frac.get("plain", {}).get(tid, (0, 0))
            if cn == 0 or pn == 0:
                detail.append((tid, "missing-data"))
                continue
            cf, pf = cp / cn, pp / pn
            if cf > pf:
                wins += 1
                detail.append((tid, f"win {cp}/{cn} vs {pp}/{pn}"))
            elif cf < pf:
                losses += 1
                detail.append((tid, f"loss {cp}/{cn} vs {pp}/{pn}"))
            else:
                ties += 1
                detail.append((tid, f"tie {cp}/{cn}"))
        p = sign_test_p(wins, losses)
        out["comparisons"][challenger] = {
            "wins": wins, "losses": losses, "ties": ties,
            "sign_test_p_one_sided": p,
            "detail": detail,
        }

    with open(os.path.join(HERE, "results", "analysis.json"), "w") as f:
        json.dump(out, f, indent=2)

    # markdown
    lines = ["| Task | plain | route | revise | unstable |",
             "|------|-------|-------|--------|----------|"]
    for tid in tids:
        r = out["per_task"][tid]
        lines.append(f"| {tid} | {r.get('plain', '-')} | {r.get('route', '-')} "
                     f"| {r.get('revise', '-')} | "
                     f"{','.join(r['unstable']) or 'no'} |")
    lines.append("")
    for mech, mean in out["mechanism_means"].items():
        lines.append(f"- {mech}: mean per-task pass rate = {mean:.3f}")
    lines.append("")
    for ch, c in out["comparisons"].items():
        lines.append(
            f"- {ch} vs plain: {c['wins']}W / {c['losses']}L / {c['ties']}T, "
            f"sign-test p (one-sided) = {c['sign_test_p_one_sided']:.3f}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
