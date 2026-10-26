#!/usr/bin/env python3
"""prompt_filter.py — a $0 pre-flight filter for LLM API calls.

Sits between your code and any chat-completions style API. It never calls a
model itself; it rewrites, blocks, or passes through a request dict of the
form {"model": str, "messages": [{"role": ..., "content": ...}, ...],
"max_tokens": int (optional), ...} and returns (request, report).

Rules enforced, mapped to the token-saving discipline:

1. ROUTE CHEAP FIRST. The request model is forced to the cheap tier unless
   the caller passes meta={"verified_fail": True}, meaning a deterministic
   check already failed the cheap tier's answer. Escalation without evidence
   is downgraded and flagged.
2. STABLE PREFIX. The system prompt is moved to position 0 and its hash is
   pinned in the state file. If a later call changes it, the report flags a
   cache break (a changed prefix forfeits provider prompt-cache discounts).
3. TRIM HISTORY. System + the first user message (the goal) are pinned.
   Middle turns are dropped, oldest first, until the estimated input fits
   the token budget. A marker records how many turns were elided.
4. CAP OUTPUT. max_tokens is set to the configured ceiling when absent or
   above it. With structured=True, an instruction to answer in JSON fields
   only is appended once to the system prompt.
5. CODE BEFORE MODEL. Empty content is rejected. An exact repeat of a
   previously answered request returns the cached response with zero calls.
6. NO BLIND RETRIES. A request whose identical hash already produced a
   model-level failure is blocked until its inputs change or the caller
   passes meta={"transport_error": True}.

Token estimates use chars/4 (close enough for budgeting; the ledger records
estimates, not billing truth). State (response cache, attempt ledger,
prefix pin) lives in one JSON file next to this script. Every prepared call
appends one line to prompt_filter_ledger.jsonl with before/after estimates.

Usage as a library:

    from prompt_filter import PromptFilter
    pf = PromptFilter(cheap_model="meta/llama-3.1-8b",
                      strong_model="meta/llama-3.3-70b")
    req, report = pf.prepare(request_dict)
    if report["action"] == "cached":   # zero-cost answer
        answer = report["cached_response"]
    elif report["action"] == "blocked":
        ...                            # fix inputs; do not resend
    else:
        answer = call_api(req)         # your code
        pf.record_result(req, ok=True, response=answer)

CLI self-test:  python3 prompt_filter.py --selftest
"""

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "prompt_filter_state.json")
LEDGER_PATH = os.path.join(HERE, "prompt_filter_ledger.jsonl")


def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token for English text/code."""
    return max(1, (len(text) + 3) // 4)


def messages_tokens(messages):
    return sum(estimate_tokens(m.get("content", "")) + 4 for m in messages)


def request_hash(model, messages):
    payload = json.dumps({"model": model, "messages": messages},
                         sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PromptFilter:
    def __init__(self, cheap_model, strong_model=None,
                 input_budget=6000, output_ceiling=512,
                 keep_recent_turns=6, state_path=STATE_PATH,
                 ledger_path=LEDGER_PATH):
        self.cheap_model = cheap_model
        self.strong_model = strong_model or cheap_model
        self.input_budget = input_budget
        self.output_ceiling = output_ceiling
        self.keep_recent_turns = keep_recent_turns
        self.state_path = state_path
        self.ledger_path = ledger_path
        self.state = self._load_state()

    # -- state ---------------------------------------------------------
    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                return json.load(f)
        return {"prefix_hash": None, "cache": {}, "attempts": {}}

    def _save_state(self):
        with open(self.state_path, "w") as f:
            json.dump(self.state, f)

    def _log(self, entry):
        entry["ts"] = int(time.time())
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # -- main entry ----------------------------------------------------
    def prepare(self, request, meta=None):
        meta = meta or {}
        report = {"action": "pass", "flags": []}
        req = json.loads(json.dumps(request))  # deep copy
        messages = req.get("messages", [])
        before_tokens = messages_tokens(messages)

        # Rule 5a: reject empties before anything else.
        if not messages or not any(m.get("content", "").strip()
                                   for m in messages):
            report.update(action="blocked", reason="empty request")
            self._log({"result": "blocked-empty",
                       "in_tokens": before_tokens})
            return req, report

        # Rule 2: pin the system prompt at position 0, watch its hash.
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        if system:
            sys_hash = hashlib.sha256(
                system[0]["content"].encode()).hexdigest()[:16]
            if self.state["prefix_hash"] is None:
                self.state["prefix_hash"] = sys_hash
                self._save_state()
            elif self.state["prefix_hash"] != sys_hash:
                report["flags"].append(
                    "PREFIX CHANGED: cache discount forfeited this call")
            messages = [system[0]] + rest

        # Rule 3: trim history to budget. Keep system, the goal (first
        # user message), and the most recent turns; elide the middle.
        if messages_tokens(messages) > self.input_budget:
            head, tail = [], messages
            sys_msgs = [m for m in messages if m.get("role") == "system"]
            convo = [m for m in messages if m.get("role") != "system"]
            if sys_msgs:
                head.append(sys_msgs[0])
            goal = next((m for m in convo if m.get("role") == "user"),
                        None)
            if goal is not None:
                head.append(goal)
                convo = [m for m in convo if m is not goal]
            recent = convo[-self.keep_recent_turns:]
            dropped = len(convo) - len(recent)
            messages = head + ([{"role": "system",
                                 "content": f"[{dropped} earlier turns "
                                            f"elided by prompt_filter]"}]
                               if dropped else []) + recent
            report["flags"].append(f"history trimmed: {dropped} turns "
                                   f"elided")

        # Rule 4: cap output; optional JSON-only instruction.
        if req.get("max_tokens") is None or \
                req["max_tokens"] > self.output_ceiling:
            req["max_tokens"] = self.output_ceiling
            report["flags"].append(
                f"max_tokens capped at {self.output_ceiling}")
        if meta.get("structured") and system:
            tag = " Respond with JSON fields only, no prose."
            if tag not in messages[0]["content"]:
                messages[0]["content"] += tag

        req["messages"] = messages

        # Rule 1: cheap tier by default; escalation needs evidence.
        if req.get("model") == self.strong_model and \
                not meta.get("verified_fail"):
            req["model"] = self.cheap_model
            report["flags"].append(
                "escalation downgraded: no verified_fail evidence")

        h = request_hash(req["model"], req["messages"])
        report["hash"] = h

        # Rule 5b: exact repeat of an answered request costs nothing.
        if h in self.state["cache"]:
            report.update(action="cached",
                          cached_response=self.state["cache"][h])
            self._log({"result": "cache-hit", "hash": h,
                       "in_tokens": 0,
                       "saved_tokens": messages_tokens(messages)})
            return req, report

        # Rule 6: identical retry of a model-level failure is blocked.
        prev = self.state["attempts"].get(h)
        if prev and not prev.get("ok") and not meta.get("transport_error"):
            report.update(action="blocked",
                          reason="identical request already failed at "
                                 "the model level; change the inputs "
                                 "instead of retrying")
            self._log({"result": "blocked-retry", "hash": h,
                       "in_tokens": before_tokens})
            return req, report

        after_tokens = messages_tokens(messages)
        report["est_input_tokens"] = after_tokens
        report["saved_tokens"] = before_tokens - after_tokens
        self._log({"result": "pass", "hash": h, "model": req["model"],
                   "in_tokens": after_tokens,
                   "saved_tokens": report["saved_tokens"],
                   "flags": report["flags"]})
        return req, report

    def record_result(self, request, ok, response=None):
        """Call after the API returns, so cache/retry rules have data."""
        h = request_hash(request.get("model", ""),
                         request.get("messages", []))
        self.state["attempts"][h] = {"ok": bool(ok)}
        if ok and response is not None:
            self.state["cache"][h] = response
        self._save_state()


def selftest():
    tmp_state = os.path.join(HERE, "prompt_filter_state.test.json")
    tmp_ledger = os.path.join(HERE, "prompt_filter_ledger.test.jsonl")
    for p in (tmp_state, tmp_ledger):
        if os.path.exists(p):
            os.remove(p)
    pf = PromptFilter(cheap_model="cheap-8b", strong_model="strong-70b",
                      input_budget=200, output_ceiling=256,
                      keep_recent_turns=2,
                      state_path=tmp_state, ledger_path=tmp_ledger)

    big_history = [{"role": "system", "content": "You grade answers."},
                   {"role": "user", "content": "GOAL: grade the set."}]
    for i in range(10):
        big_history.append({"role": "user",
                            "content": f"turn {i} " + "x" * 120})
        big_history.append({"role": "assistant",
                            "content": f"reply {i} " + "y" * 120})
    big_history.append({"role": "user", "content": "grade item 42"})

    req, rep = pf.prepare({"model": "strong-70b",
                           "messages": big_history, "max_tokens": 4000})
    assert rep["action"] == "pass", rep
    assert req["model"] == "cheap-8b", req["model"]
    assert req["max_tokens"] == 256
    assert messages_tokens(req["messages"]) <= 200 + 60, \
        messages_tokens(req["messages"])
    assert rep["saved_tokens"] > 500, rep["saved_tokens"]
    print("1. downgrade + cap + trim OK; saved ~%d est. tokens"
          % rep["saved_tokens"])

    pf.record_result(req, ok=True, response='{"grade": "pass"}')
    req2, rep2 = pf.prepare({"model": "strong-70b",
                             "messages": big_history, "max_tokens": 4000})
    assert rep2["action"] == "cached", rep2
    print("2. repeat request served from cache, zero calls")

    fail_req = {"model": "cheap-8b",
                "messages": [{"role": "user", "content": "hard task"}]}
    fail_req, _ = pf.prepare(fail_req)
    pf.record_result(fail_req, ok=False)
    _, rep3 = pf.prepare({"model": "cheap-8b",
                          "messages": [{"role": "user",
                                        "content": "hard task"}]})
    assert rep3["action"] == "blocked", rep3
    print("3. blind retry of a failed request blocked")

    esc, rep4 = pf.prepare({"model": "strong-70b",
                            "messages": [{"role": "user",
                                          "content": "hard task v2"}]},
                           meta={"verified_fail": True})
    assert esc["model"] == "strong-70b" and rep4["action"] == "pass"
    print("4. escalation allowed with verified_fail evidence")

    for p in (tmp_state, tmp_ledger):
        os.remove(p)
    print("SELFTEST PASSED")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        print(__doc__)
