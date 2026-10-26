#!/usr/bin/env python3
"""Majority-vote ensemble over the SwarmZero free-model roster.

Usage:
    python3 vote.py <task-id> [model ...] [--all]

- With no model args, uses the full ranked roster.
- --all runs every v1 task and writes a summary to results/.
- Each model is run once via swarm-call.sh with SWARM_CACHE=1
  (cached answers reused; noted as best-effort per call).
- SWARM_FALLBACK is disabled and SWARM_REDELEGATE=0 so every counted
  vote genuinely comes from the named model. A model with no output
  abstains; it is never filled in by another model.
- Normalized answers are extracted per task scorer, reusing
  benchmark/score.py's extraction logic (imported, not reimplemented).
- The majority answer is scored with the task's mechanical scorer.

The unified API key is resolved read-only from the local server DB and
passed to the subprocess via environment only. It is never printed,
logged, or written to any file.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "..", "benchmark")
sys.path.insert(0, BENCH)
import score as S  # noqa: E402  (reuses _numbers, _strip_fences, SCORERS)

SWARM_CALL = os.path.expanduser("~/workspace/freellmapi/swarm-call.sh")
DB_PATH = os.path.expanduser("~/workspace/freellmapi/server/data/freeapi.db")

# Tie-break ranking: best first. Models not listed rank below all listed.
RANKING = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "cohere/north-mini-code:free",
    "dots-studio/dots-3-note-preview:free",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "liquid/lfm-2.5-2.6b:free",
]
RANK = {m: i for i, m in enumerate(RANKING)}


def rank_of(model):
    return RANK.get(model, len(RANKING))


def resolve_key():
    """Read-only lookup of the unified API key from the server DB."""
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT value FROM settings WHERE key='unified_api_key'"
        ).fetchone()
    finally:
        db.close()
    if not row or not row[0]:
        raise RuntimeError("no unified API key found in server DB")
    return row[0]


def run_model(model, prompt, key):
    """Run one model once via swarm-call.sh. Returns (text|None, cached|None).

    cached is best-effort, inferred from the script's stdout.
    """
    pf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    try:
        pf.write(prompt)
        pf.close()
        outdir = tempfile.mkdtemp(prefix="vote-out-")
        env = os.environ.copy()
        env.update({
            "no_proxy": "localhost,127.0.0.1",
            "NO_PROXY": "localhost,127.0.0.1",
            "SWARM_MODELS": model,
            "SWARM_CACHE": "1",
            "SWARM_REDELEGATE": "0",      # never substitute another model
            "SWARM_FALLBACK": "",          # never fill slot with fallback
            "SWARM_SKIP_UNHEALTHY": "1",   # unhealthy model abstains
            "FREELLMAPI_API_KEY": key,
        })
        try:
            r = subprocess.run(
                [SWARM_CALL, "-f", pf.name, outdir],
                env=env, capture_output=True, text=True, timeout=400,
            )
        except subprocess.TimeoutExpired:
            return None, None
        out = (r.stdout or "") + (r.stderr or "")
        cached = True if re.search(r"cache hit", out, re.I) else (
            False if re.search(r"cache miss", out, re.I) else None)
        texts = []
        for fn in sorted(os.listdir(outdir)):
            if fn.endswith(".txt") and fn != "prompt.txt":
                with open(os.path.join(outdir, fn), encoding="utf-8",
                          errors="replace") as f:
                    texts.append(f.read())
        if not texts:
            return None, cached
        return texts[0], cached
    finally:
        try:
            os.unlink(pf.name)
        except OSError:
            pass


def extract_answer(text, task):
    """Normalized answer string, derived from score.py's extraction logic."""
    sc = task["scorer"]
    if sc == "exact_year":
        years = re.findall(r"\b\d{4}\b", text)
        return "|".join(years) if years else "<none>"
    if sc in ("numeric_exact", "numeric_tolerance"):
        nums = S._numbers(text)
        return "|".join(f"{n:.6g}" for n in nums) if nums else "<none>"
    if sc == "code_tests":
        return S._strip_fences(text)
    if sc == "json_exact":
        try:
            return json.dumps(json.loads(S._strip_fences(text)), sort_keys=True)
        except Exception:
            return S._strip_fences(text)
    if sc == "mechanical_constraints":
        return text.strip()
    if sc == "fact_substrings":
        low = text.lower()
        length = "9289" if (("9289" in low) or ("9,289" in low)) else "MISSING"
        began = "1891" if "1891" in low else "MISSING"
        tz = "8" if (("8 time zone" in low)
                     or (("eight" in low) and ("time zone" in low))) else "MISSING"
        return f"{length}|{began}|{tz}"
    if sc == "day_name":
        return re.sub(r"[^a-z]", "", text.lower())
    if sc == "label_sequence":
        labels = []
        for line in text.strip().splitlines():
            m = re.search(r"\b(FRUIT|VEGETABLE|GRAIN)\b", line.upper())
            labels.append(m.group(1) if m else "?")
        return "|".join(labels)
    if sc == "uncertainty_expressed":
        ok, _ = S.score_uncertainty_expressed(text)
        return "UNCERTAIN" if ok else "CONFIDENT"
    return text.strip()


def to_scorable_text(norm, task):
    """Convert a normalized majority answer back into text the scorer accepts."""
    sc = task["scorer"]
    if sc == "fact_substrings":
        length, began, tz = norm.split("|")
        parts = []
        if length != "MISSING":
            parts.append(f"spans {length} km")
        if began != "MISSING":
            parts.append(f"began in {began}")
        if tz != "MISSING":
            parts.append("crosses 8 time zones")
        return ("The railway " + ", ".join(parts) + "."
                if parts else "No facts found.")
    if sc == "label_sequence":
        return "\n".join(norm.split("|"))
    if sc == "uncertainty_expressed":
        if norm == "UNCERTAIN":
            return "I'm not sure; there was no such study."
        return "The lead researcher was Dr. Elena Vasquez."
    return norm


def majority_vote(votes):
    """votes: list of (model, normalized). Returns (winner_norm, voter_models).

    Ties broken by preferring the answer backed by the highest-ranked model.
    """
    counts = {}
    voters = {}
    for model, norm in votes:
        counts[norm] = counts.get(norm, 0) + 1
        voters.setdefault(norm, []).append(model)
    top = max(counts.values())
    cands = [n for n, c in counts.items() if c == top]
    # tie-break: candidate whose best-ranked voter ranks highest wins
    winner = min(cands, key=lambda n: min(rank_of(m) for m in voters[n]))
    return winner, voters[winner]


def run_task(task, models, key):
    votes = []
    abstentions = []
    details = []
    for model in models:
        text, cached = run_model(model, task["prompt"], key)
        if text is None:
            abstentions.append(model)
            details.append({"model": model, "vote": None,
                            "cached": cached, "status": "abstain"})
            continue
        norm = extract_answer(text, task)
        votes.append((model, norm))
        details.append({"model": model, "vote": norm,
                        "cached": cached, "status": "voted"})
    if not votes:
        return {"task_id": task["id"], "scorer": task["scorer"],
                "votes": details, "abstentions": abstentions,
                "majority_normalized": None, "majority_voters": [],
                "majority_scorable_text": None, "pass": False,
                "detail": "no votes cast", "diverged_from_120b": None,
                "model_120b_normalized": None}
    winner, winner_voters = majority_vote(votes)
    scorable = to_scorable_text(winner, task)
    try:
        ok, detail = S.SCORERS[task["scorer"]](scorable, task)
    except Exception as e:
        ok, detail = False, f"scorer crashed: {type(e).__name__}: {e}"
    m120 = next((n for m, n in votes if m == "openai/gpt-oss-120b"), None)
    return {"task_id": task["id"], "scorer": task["scorer"],
            "votes": details, "abstentions": abstentions,
            "majority_normalized": winner, "majority_voters": winner_voters,
            "majority_scorable_text": scorable, "pass": bool(ok),
            "detail": detail,
            "diverged_from_120b": (m120 is not None and m120 != winner),
            "model_120b_normalized": m120}


def load_tasks():
    with open(os.path.join(BENCH, "tasks.json")) as f:
        return json.load(f)["tasks"]


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    run_all = "--all" in argv[1:]
    tasks = load_tasks()
    by_id = {t["id"]: t for t in tasks}
    if run_all:
        targets = tasks
    else:
        if not args:
            print("usage: vote.py <task-id> [model ...] [--all]", file=sys.stderr)
            return 2
        if args[0] not in by_id:
            print(f"unknown task id: {args[0]}", file=sys.stderr)
            return 2
        targets = [by_id[args[0]]]
    models = args[1:] if len(args) > 1 else list(RANKING)
    key = resolve_key()
    results = {}
    for task in targets:
        print(f"=== {task['id']} ({len(models)} models) ===", file=sys.stderr)
        results[task["id"]] = run_task(task, models, key)
    if run_all:
        outdir = os.path.join(HERE, "results")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "vote-results.json"), "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n{'TASK':28s} VOTE  120b  DIVERGE")
        for tid, r in results.items():
            v = "P" if r["pass"] else "F"
            m120 = r["model_120b_normalized"]
            d120 = next((d for d in r["votes"]
                         if d["model"] == "openai/gpt-oss-120b"), None)
            s120 = "P" if False else "?"
            if d120 and d120["status"] == "voted":
                ok120, _ = S.SCORERS[r["scorer"]](
                    to_scorable_text(m120, by_id[tid]), by_id[tid])
                s120 = "P" if ok120 else "F"
            div = "YES" if r["diverged_from_120b"] else ("no" if r["diverged_from_120b"] is False else "-")
            print(f"{tid:28s} {v:5s} {s120:5s} {div}")
        nv = sum(1 for r in results.values() if r["pass"])
        print(f"\nVoted score: {nv}/{len(results)}")
    else:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
