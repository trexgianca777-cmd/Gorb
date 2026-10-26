#!/usr/bin/env python3
"""sample-plain20.py — best-of-20 plain samples per task, time-spread.

Provider determinism means samples within one time window are byte-identical;
spread rounds ~7 minutes apart so the 20 samples span multiple windows.
Appends to results/part2/plain20/<task>.jsonl : {round, pass, detail}.
Idempotent: skips rounds already recorded.
"""
import importlib.util
import json
import os
import sys
import time

V5 = os.path.expanduser("~/workspace/hackathon/swarmzero-staging/benchmark-v5")
V6 = os.path.dirname(os.path.abspath(__file__))
os.environ["MECH_KEPT_JSON"] = "tasks-v5-kept2.json"
_CLI_TASKS = sys.argv[1:]
sys.argv = ["x"]
_spec = importlib.util.spec_from_file_location(
    "mech_v6", os.path.join(V6, "mech-v6.py"))
m6 = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(m6)
except SystemExit:
    pass

TASKS = _CLI_TASKS or [
    "c1-expr-eval-3", "c10-sexpr", "p3-unicode-json",
    "p9-sexpr-let", "q3-zebra-5", "w5-lines-words"]
N, GAP = 20, 420  # 20 rounds, 7 minutes apart

for rnd in range(1, N + 1):
    for tid in TASKS:
        task = m6.load_task(tid)
        outp = os.path.join(V6, "results", "part2", "plain20", tid + ".jsonl")
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        done = set()
        if os.path.exists(outp):
            for ln in open(outp):
                try:
                    done.add(json.loads(ln)["round"])
                except Exception:
                    pass
        if rnd in done:
            continue
        a = m6.call_model(task["prompt"])
        ok, detail = m6.verify(task, a)
        with open(outp, "a") as f:
            f.write(json.dumps({"round": rnd, "pass": bool(ok),
                                "detail": str(detail)[:160],
                                "t": time.strftime("%H:%M:%S")}) + "\n")
        print(f"round {rnd} {tid} pass={ok}", flush=True)
        time.sleep(5)
    if rnd < N:
        print(f"--- sleeping {GAP}s ---", flush=True)
        time.sleep(GAP)
print("PLAIN20 DONE")
