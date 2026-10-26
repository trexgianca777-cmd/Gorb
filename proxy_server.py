#!/usr/bin/env python3
"""proxy_server.py — prompt_filter as a drop-in product (option 2).

A $0 OpenAI-compatible proxy: point any chat-completions client at
this server instead of the provider, and every request passes through
the prompt_filter rules before it reaches the upstream API:

  1. Cheap tier by default; strong model only with verified failure.
  2. Stable system prefix pinned (prefix changes flagged as cache breaks).
  3. History trimmed to budget (system + goal + recent turns kept).
  4. Output capped at the ceiling.
  5. Exact repeats served from cache at zero calls.
  6. Identical retries of model-level failures blocked.

It is a proxy, not a model: it never answers itself, it forwards.
Upstream auth comes from the environment, never from a file the proxy
writes. The filter state and ledger live next to this script.

Usage:
  UPSTREAM_BASE_URL=http://localhost:3001/v1 \
  UPSTREAM_API_KEY=$FREELLMAPI_API_KEY \
  FILTER_CHEAP_MODEL=openai/gpt-oss-20b \
  FILTER_STRONG_MODEL=openai/gpt-oss-120b \
  python3 proxy_server.py [--port 8080]

Client config (OpenAI SDK):
  client = OpenAI(base_url="http://localhost:8080/v1",
                  api_key="proxy")  # key ignored; upstream key is server-side

Escalation: a client that already has a verified cheap-tier failure
sends header "X-Verified-Fail: true" and the strong model is kept.
A transport-level retry sends "X-Transport-Error: true".

Endpoints:
  POST /v1/chat/completions   filtered + forwarded (or cached/blocked)
  GET  /health                {"status": "ok"}
  GET  /                       usage text
"""

import json
import os
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from prompt_filter import PromptFilter  # noqa: E402

UPSTREAM = os.environ.get("UPSTREAM_BASE_URL",
                          "http://localhost:3001/v1").rstrip("/")
UPSTREAM_KEY = (os.environ.get("UPSTREAM_API_KEY")
                or os.environ.get("FREELLMAPI_API_KEY", ""))
CHEAP = os.environ.get("FILTER_CHEAP_MODEL", "openai/gpt-oss-20b")
STRONG = os.environ.get("FILTER_STRONG_MODEL", "openai/gpt-oss-120b")

PF = PromptFilter(
    cheap_model=CHEAP, strong_model=STRONG,
    state_path=os.path.join(HERE, "proxy_state.json"),
    ledger_path=os.path.join(HERE, "proxy_ledger.jsonl"))


def forward(req):
    """POST the filtered request upstream; return (status, body_dict)."""
    data = json.dumps(req).encode()
    http_req = urllib.request.Request(
        UPSTREAM + "/chat/completions", data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {UPSTREAM_KEY}"},
        method="POST")
    try:
        with urllib.request.urlopen(http_req, timeout=300) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": f"upstream HTTP {e.code}"}
    except Exception as e:
        return 502, {"error": f"upstream unreachable: {e}"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._text(200, __doc__)

    def do_POST(self):
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self._json(404, {"error": "unknown path"})
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n).decode())
        except Exception:
            self._json(400, {"error": "request body is not JSON"})
            return
        meta = {
            "verified_fail":
                self.headers.get("X-Verified-Fail", "").lower() == "true",
            "transport_error":
                self.headers.get("X-Transport-Error", "").lower() == "true",
        }
        req, report = PF.prepare(body, meta=meta)
        if report["action"] == "cached":
            self._json(200, {"cached": True,
                             "response": report["cached_response"],
                             "filter": report})
            return
        if report["action"] == "blocked":
            self._json(400, {"error": "blocked by prompt_filter",
                             "reason": report.get("reason"),
                             "filter": report})
            return
        status, resp_body = forward(req)
        PF.record_result(req, ok=(status == 200), response=resp_body)
        self._json(status, resp_body)

    def _json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, status, text):
        data = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    port = 8080
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    print(f"prompt_filter proxy on http://localhost:{port}/v1 "
          f"(upstream {UPSTREAM}, cheap {CHEAP}, strong {STRONG})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
