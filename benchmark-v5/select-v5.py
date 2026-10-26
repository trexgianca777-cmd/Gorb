#!/usr/bin/env python3
"""select-v5.py — score the 120b screening and select kept tasks.

Keep rule (pre-registered): task is kept iff plain gpt-oss-120b FAILED
at least 2 of 3 screening reps. Writes tasks-v5-kept.json.
Also prints the full screening table for the report.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)

SAFE120 = "openai_gpt-oss-120b"
TASKS_JSON = os.environ.get("SELECT_TASKS_JSON", "tasks-v5-candidates.json")
SCREEN_SUB = os.environ.get("SELECT_SCREEN_SUB", "screen")
KEPT_OUT = os.environ.get("SELECT_KEPT_OUT", "tasks-v5-kept.json")
SCREEN = os.path.join(BASE, "results", SCREEN_SUB)


def read_cell(tid, rep):
    p = os.path.join(SCREEN, tid, f"rep{rep}", f"{SAFE120}.txt")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    _tj = TASKS_JSON
    if not os.path.isabs(_tj):
        _tj = os.path.join(BASE, _tj)
    tasks = json.load(open(_tj))["tasks"]
    kept, dropped = [], []
    print(f"{'TASK':22s} {'p/f per rep':12s} keep?")
    for t in tasks:
        tid = t["id"]
        res = []
        for rep in (1, 2, 3):
            txt = read_cell(tid, rep)
            if txt is None or txt.strip() == "NO-OUTPUT":
                res.append(None)
                continue
            try:
                ok, _ = score_v5.SCORERS[t["scorer"]](txt, t)
            except Exception:
                ok = False
            res.append(bool(ok))
        n_fail = sum(1 for r in res if r is False)
        n_none = sum(1 for r in res if r is None)
        keep = n_fail >= 2 and n_none == 0
        (kept if keep else dropped).append(tid)
        marks = "".join("P" if r else ("F" if r is False else "?") for r in res)
        print(f"{tid:22s} {marks:12s} {'KEEP' if keep else 'drop'}")
    with open(os.path.join(BASE, KEPT_OUT), "w") as f:
        json.dump({"tasks": [t for t in tasks if t["id"] in kept],
                   "kept_ids": kept, "dropped_ids": dropped}, f, indent=2)
    print(f"\nkept {len(kept)}/{len(tasks)}: {kept}")


if __name__ == "__main__":
    main()
