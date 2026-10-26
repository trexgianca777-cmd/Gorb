#!/usr/bin/env python3
"""build-router-v5.py — same-distribution routing map.

For each kept task, compare 120b screening passes vs 20b screening passes
(same task distribution, same 3-rep protocol). Route to 20b iff it strictly
beat 120b; ties and 120b-wins stay on 120b. Writes router-v5.json.
"""
import importlib.util
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)


def passes(sub, tid, safe):
    t = next(x for x in TASKS if x["id"] == tid)
    n = 0
    for rep in (1, 2, 3):
        p = os.path.join(BASE, "results", sub, tid, f"rep{rep}", f"{safe}.txt")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            txt = f.read()
        if txt.strip() == "NO-OUTPUT":
            continue
        try:
            ok, _ = score_v5.SCORERS[t["scorer"]](txt, t)
        except Exception:
            ok = False
        n += 1 if ok else 0
    return n


KEPT_JSON = os.environ.get("ROUTER_KEPT_JSON", "tasks-v5-kept.json")
SCREEN_A = os.environ.get("ROUTER_SCREEN_A", "screen")
SCREEN_B = os.environ.get("ROUTER_SCREEN_B", "screen20")
ROUTER_OUT = os.environ.get("ROUTER_OUT", "router-v5.json")
TASKS = json.load(open(os.path.join(BASE, KEPT_JSON)))["tasks"]
router = {}
print(f"{'TASK':22s} {'120b':5s} {'20b':5s} route")
for t in TASKS:
    tid = t["id"]
    p120 = passes(SCREEN_A, tid, "openai_gpt-oss-120b")
    p20 = passes(SCREEN_B, tid, "openai_gpt-oss-20b")
    model = "openai/gpt-oss-20b" if p20 > p120 else "openai/gpt-oss-120b"
    router[tid] = model
    print(f"{tid:22s} {p120:<5d} {p20:<5d} {model}")
with open(os.path.join(BASE, ROUTER_OUT), "w") as f:
    json.dump(router, f, indent=2)
n20 = sum(1 for m in router.values() if "20b" in m)
print(f"\nrouted to 20b on {n20}/{len(router)} kept tasks")
