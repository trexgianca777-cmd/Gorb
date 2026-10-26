#!/usr/bin/env python3
"""xrevise.py — cross-model revision harness v2.

Mechanisms:
  plain          single 120b call (per-window canary / baseline)
  A>B            generator A, reviser B, <=2 revisions, thrash-guard
  cascade        20b generates, 20b revises (<=2), then 120b revises (<=2)
                 — escalates to the expensive model only on failure

Window-aware cache: within a time window the provider is deterministic
(byte-identical outputs for identical prompts — verified v5). Cache key
is sha256(model + prompt); the cache is valid only while the canary hash
matches. Canary = 2 fixed tiny prompts through plain 120b. If the canary
hash changed, the window drifted and the cache is ignored (never pooled
across windows).

Canary re-probe (mid-run, vina's question): the provider window can end
*inside* a paired comparison, so this is enforced, not hoped for. Every
K completed cells (default 12, --canary-every) the harness re-probes the
canary. On mismatch it records a window_boundary event (timestamp, cell
index, old/new hash), starts a new window segment, and resets the cache.
Pairs whose two cells land in different segments are marked
boundary_straddled in results.json and must be excluded from the sign test.

Usage:
  MECH_KEPT_JSON=tasks-v5-kept2.json python3 xrevise.py \
      --tasks p9-sexpr-let,q3-zebra-5,r5-fifty-words,r8-no-e,c1-expr-eval-3,c10-sexpr,l1-knights-6 \
      --mechs plain,120b>120b,20b>120b,20b>20b,20b>nemotron-super,20b>cohere-code,20b>qwen27b,qwen27b>qwen27b,cascade \
      --outdir results/xrevise-v2-<stamp> [--no-cache]

Model aliases:
  120b            openai/gpt-oss-120b
  20b             openai/gpt-oss-20b
  nemotron-super  nvidia/nemotron-3-super-120b-a12b:free
  cohere-code     cohere/north-mini-code:free
  qwen27b         qwen/qwen3.8-27b
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")

_spec = importlib.util.spec_from_file_location(
    "score_v5_mod", os.path.join(BASE, "score-v5.py"))
score_v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_v5)

KEPT_JSON = os.environ.get("MECH_KEPT_JSON", "tasks-v5-kept.json")

ALIASES = {
    "120b": "openai/gpt-oss-120b",
    "20b": "openai/gpt-oss-20b",
    "nemotron-super": "nvidia/nemotron-3-super-120b-a12b:free",
    "cohere-code": "cohere/north-mini-code:free",
    "qwen27b": "qwen/qwen3.8-27b",
}
PLAIN = ALIASES["120b"]

CANARY_PROMPTS = [
    "Reply with exactly: CANARY-ONE",
    "What is 17*23? Reply with the number only.",
]

REVISE_TEMPLATE = (
    "{prompt}\n\n"
    "Your previous answer FAILED the automated check.\n"
    "Failure detail: {detail}\n"
    "Your previous answer was:\n{answer}\n\n"
    "Study the failure detail carefully and produce a corrected answer. "
    "Follow the original instructions exactly. Do not repeat your previous "
    "answer unchanged."
)


def safe_name(model):
    return model.replace("/", "_").replace(":", "_")


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_task(tid):
    tasks = json.load(open(os.path.join(BASE, KEPT_JSON)))["tasks"]
    for t in tasks:
        if t["id"] == tid:
            return t
    raise ValueError(f"unknown kept task: {tid}")


def raw_call(model, prompt):
    """One fresh model call. Returns answer text ('' on transport failure)."""
    fd, ppath = tempfile.mkstemp(prefix="xrev-prompt-", suffix=".txt")
    outdir = tempfile.mkdtemp(prefix="xrev-out-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        env = dict(os.environ)
        env["no_proxy"] = "localhost,127.0.0.1"
        env["NO_PROXY"] = "localhost,127.0.0.1"
        env["SWARM_MODELS"] = model
        env["SWARM_CACHE"] = "0"
        env["SWARM_REDELEGATE"] = "0"
        env["SWARM_FALLBACK"] = ""
        env["SWARM_SKIP_UNHEALTHY"] = "0"
        env["SWARM_TIMEOUT"] = "180"
        subprocess.run(
            [SWARM_CALL, "-f", ppath, outdir],
            env=env, capture_output=True, text=True, timeout=300,
        )
        txt_path = os.path.join(outdir, safe_name(model) + ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(ppath):
            os.unlink(ppath)
        shutil.rmtree(outdir, ignore_errors=True)


class WindowCache:
    """Deterministic-within-window cache. Invalid across windows."""

    def __init__(self, path, enabled=True):
        self.path = path
        self.enabled = enabled
        self.hits = 0
        self.misses = 0
        self.data = {"window": None, "calls": {}}
        if enabled and os.path.exists(path):
            try:
                self.data = json.load(open(path))
            except Exception:
                self.data = {"window": None, "calls": {}}
        self.window = None

    def measure_window(self):
        outs = [raw_call(PLAIN, p) for p in CANARY_PROMPTS]
        self.window = sha256("\x00".join(outs))
        return self.window

    def get(self, model, prompt):
        key = sha256(model + "\x00" + prompt)
        if (self.enabled and self.data.get("window") == self.window
                and key in self.data["calls"]):
            self.hits += 1
            return self.data["calls"][key], True
        out = raw_call(model, prompt)
        self.misses += 1
        if self.enabled:
            self.data["window"] = self.window
            self.data["calls"][key] = out
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.data, f)
            os.replace(tmp, self.path)
        return out, False


def verify(task, answer):
    if not answer or not answer.strip():
        return False, "no output (transport failure or empty response)"
    try:
        ok, detail = score_v5.SCORERS[task["scorer"]](answer, task)
    except Exception as e:
        return False, f"scorer crashed: {type(e).__name__}: {e}"
    return bool(ok), detail


def norm_answer(a):
    return re.sub(r"\s+", " ", a.strip().lower())


def run_chain(task, gen, revs, cache):
    """gen generates; revs = [(model, n_revisions), ...] applied in order."""
    attempts = []
    seen = set()
    prompt = task["prompt"]
    answer = None
    detail = ""
    n = 0
    # attempt 1: generator on the raw prompt
    answer, hit = cache.get(gen, task["prompt"])
    n = 1
    passed, detail = verify(task, answer)
    key = norm_answer(answer)
    seen.add(key)
    attempts.append({"attempt": n, "model": gen, "pass": passed,
                     "detail": detail, "repeated": False, "cache_hit": hit})
    if passed:
        return answer, attempts
    for model, count in revs:
        for _ in range(count):
            prompt = REVISE_TEMPLATE.format(
                prompt=task["prompt"], detail=detail,
                answer=answer.strip()[:4000])
            n += 1
            answer, hit = cache.get(model, prompt)
            passed, detail = verify(task, answer)
            key = norm_answer(answer)
            repeated = key in seen
            seen.add(key)
            attempts.append({"attempt": n, "model": model, "pass": passed,
                             "detail": detail, "repeated": repeated,
                             "cache_hit": hit})
            if passed or repeated:
                break
        if passed or attempts[-1]["repeated"]:
            break
    return answer, attempts


def parse_mech(spec):
    spec = spec.strip()
    if spec == "plain":
        return ("plain", None)
    if spec == "cascade":
        return ("cascade", None)
    if ">" in spec:
        g, r = spec.split(">", 1)
        return ("chain", (ALIASES[g.strip()], [(ALIASES[r.strip()], 2)]))
    raise ValueError(f"bad mech spec: {spec}")


def run_mech(task, mech, cache):
    kind, cfg = mech
    if kind == "plain":
        answer, hit = cache.get(PLAIN, task["prompt"])
        passed, detail = verify(task, answer)
        attempts = [{"attempt": 1, "model": PLAIN, "pass": passed,
                     "detail": detail, "repeated": False, "cache_hit": hit}]
        return answer, attempts
    if kind == "cascade":
        gen = ALIASES["20b"]
        revs = [(ALIASES["20b"], 2), (ALIASES["120b"], 2)]
        return run_chain(task, gen, revs, cache)
    gen, revs = cfg
    return run_chain(task, gen, revs, cache)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True,
                    help="comma-separated task ids")
    ap.add_argument("--mechs", required=True,
                    help="comma-separated mech specs")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--canary-every", type=int, default=12,
                    help="mid-run canary re-probe every K completed cells "
                         "(0 disables; default 12)")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    tasks = [t.strip() for t in args.tasks.split(",")]
    mechs = [(s.strip(), parse_mech(s.strip())) for s in args.mechs.split(",")]

    cache = WindowCache(os.path.join(args.outdir, "cache.json"),
                        enabled=not args.no_cache)
    print("measuring window (canary)...", flush=True)
    window = cache.measure_window()
    print(f"window: {window[:16]}... "
          f"(cache window: {str(cache.data.get('window'))[:16]})", flush=True)
    cache_valid = cache.data.get("window") == window
    print(f"cache {'HIT — reusing in-window calls' if cache_valid else 'MISS — fresh window'}",
          flush=True)

    window_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results_path = os.path.join(args.outdir, "results.json")
    results = {"window_start_utc": window_start, "window_canary": window,
               "window_segments": [{"seg": 0, "canary": window,
                                    "started_at_utc": window_start,
                                    "cell_index": 0}],
               "window_boundaries": [],
               "straddled_pairs": [],
               "tasks": tasks, "mechs": [s for s, _ in mechs], "cells": []}
    done = set()
    cur_seg = 0
    if os.path.exists(results_path):
        try:
            prev = json.load(open(results_path))
            prev_segs = prev.get("window_segments") or [
                {"seg": 0, "canary": prev.get("window_canary")}]
            last_canary = prev_segs[-1]["canary"]
            if last_canary == window:
                results = prev
                results.setdefault("window_segments", prev_segs)
                results.setdefault("window_boundaries", [])
                results.setdefault("straddled_pairs", [])
                cur_seg = prev_segs[-1]["seg"]
                done = {(c["task"], c["mech"]) for c in prev["cells"]}
                print(f"resuming: {len(done)} cells already done in this "
                      f"window (segment {cur_seg})", flush=True)
            else:
                print("canary changed — previous partial was another window; "
                      "starting fresh", flush=True)
        except Exception as e:
            print(f"could not read previous results ({e}); starting fresh",
                  flush=True)
    cur_canary = results["window_segments"][-1]["canary"]
    cells_since_probe = 0
    k = args.canary_every
    for tid in tasks:
        task = load_task(tid)
        for spec, mech in mechs:
            if (tid, spec) in done:
                continue
            print(f"[{tid}] {spec}", flush=True)
            try:
                answer, attempts = run_mech(task, mech, cache)
            except Exception as e:
                attempts = [{"attempt": 0, "model": "error",
                             "pass": False,
                             "detail": f"harness error: {type(e).__name__}: {e}",
                             "repeated": False, "cache_hit": False}]
            final_pass = attempts[-1]["pass"] if attempts else False
            cell_ts = datetime.datetime.now(
                datetime.timezone.utc).isoformat()
            results["cells"].append({
                "task": tid, "mech": spec, "final_pass": final_pass,
                "trajectory": [a["pass"] for a in attempts],
                "models": [safe_name(a["model"]) for a in attempts],
                "cache_hits": sum(1 for a in attempts if a["cache_hit"]),
                "calls": len(attempts),
                "ts_utc": cell_ts,
                "window_seg": cur_seg,
            })
            cells_since_probe += 1
            # Mid-run canary re-probe. A window boundary inside a paired
            # comparison is an enforced event here, not a protocol hope.
            if k > 0 and cells_since_probe >= k:
                cells_since_probe = 0
                probe = cache.measure_window()
                if probe != cur_canary:
                    bts = datetime.datetime.now(
                        datetime.timezone.utc).isoformat()
                    # boundary falls after the cell just completed
                    bidx = len(results["cells"])
                    results["window_boundaries"].append({
                        "ts_utc": bts, "cell_index": bidx,
                        "old_canary": cur_canary, "new_canary": probe})
                    cur_seg += 1
                    cur_canary = probe
                    results["window_segments"].append({
                        "seg": cur_seg, "canary": probe,
                        "started_at_utc": bts, "cell_index": bidx})
                    # old cache is poisoned: calls from the old window must
                    # not leak into the new one
                    cache.window = probe
                    cache.data = {"window": probe, "calls": {}}
                    tmp = cache.path + ".tmp"
                    with open(tmp, "w") as f:
                        json.dump(cache.data, f)
                    os.replace(tmp, cache.path)
                    print(f"WINDOW BOUNDARY at cell {bidx}: "
                          f"{probe[:12]}... (segment {cur_seg})", flush=True)
            with open(os.path.join(args.outdir, "results.json"), "w") as f:
                json.dump(results, f, indent=1)

    # Pairs whose two cells landed in different window segments are invalid
    # for the sign test. The consumer drops them (see straddled_pairs).
    cell_by_key = {(c["task"], c["mech"]): c for c in results["cells"]}
    straddled = []
    for tid in tasks:
        pcell = cell_by_key.get((tid, "plain"))
        for spec, _ in mechs:
            if spec == "plain":
                continue
            mcell = cell_by_key.get((tid, spec))
            if pcell is not None and mcell is not None \
                    and pcell.get("window_seg", 0) != mcell.get("window_seg", 0):
                straddled.append({
                    "task": tid, "mech": spec,
                    "plain_seg": pcell.get("window_seg", 0),
                    "mech_seg": mcell.get("window_seg", 0)})
    results["straddled_pairs"] = straddled
    with open(os.path.join(args.outdir, "results.json"), "w") as f:
        json.dump(results, f, indent=1)

    # report
    lines = ["# Cross-model revision v2", "",
             f"Window start (UTC): {window_start}",
             f"Canary: {window[:16]}...",
             f"Cache: {cache.hits} hits, {cache.misses} misses", "",
             "| task | " + " | ".join(s for s, _ in mechs) + " |",
             "|---|---|" + "---|" * len(mechs)]
    for tid in tasks:
        row = [tid]
        for spec, _ in mechs:
            c = next(x for x in results["cells"]
                     if x["task"] == tid and x["mech"] == spec)
            traj = "".join("1" if p else "0" for p in c["trajectory"])
            row.append(f"{'PASS' if c['final_pass'] else 'fail'} ({traj})")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["",
              f"Window boundaries mid-run: {len(results['window_boundaries'])}",
              f"Straddled pairs (excluded from sign test): {len(straddled)}",
              "Trajectory: 1=pass, 0=fail per attempt in order.",
              "120b-call counts per mech on hard tasks: see results.json "
              "(models array per cell)."]
    with open(os.path.join(args.outdir, "REPORT.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\ncache: {cache.hits} hits / {cache.misses} misses", flush=True)


if __name__ == "__main__":
    main()
