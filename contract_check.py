#!/usr/bin/env python3
"""contract_check.py — mechanical enforcement of researcher-contract.md.

Scans a researcher output for SPECIFIC claims (numbers with units, dates,
paper titles, URLs, authority attributions) that lack a [V]/[U]/[I] tag.
Untagged specific claims are the fabrication vector A/B runs ab-1/ab-2
caught by hand; this catches them by code, before synthesis.

Usage:
  ./contract_check.py <output.txt>        # print violations, exit 1 if any
  ./contract_check.py --self-test        # run built-in synthetic test cases

Exit codes: 0 = no violations, 1 = violations found, 2 = usage/file error.
A violation is (severity, message). Severity HIGH = classic fabrication
vector (paper title, URL, authority quote). MEDIUM = untagged number/date.
"""
import re
import sys

TAG_RE = re.compile(r"\[\s*([VUI])\s*\]")
TAG_WINDOW = 60  # chars after a claim within which a tag counts
# Sentence ends: period/bang/question followed by whitespace (so "18.5"
# does not split), or a newline.
SENT_END_RE = re.compile(r"[.!?](?=\s|$)|\n")

# Specific-claim patterns: (name, regex, severity)
PATTERNS = [
    ("url", re.compile(r"https?://\S+"), "HIGH"),
    ("paper-title", re.compile(
        r"['\"]([A-Z][^'\"\n]{12,100}?)['\"]"
        r"(?=\s*(?:,|\.|;|\s|\[))"), "HIGH"),
    ("money", re.compile(r"\$ ?\d[\d,]*(?:\.\d+)?"), "MEDIUM"),
    ("percent", re.compile(r"\d+(?:\.\d+)?\s*%"), "MEDIUM"),
    ("multiple", re.compile(r"\b\d+(?:\.\d+)?\s*[x×]\b"), "MEDIUM"),
    ("year", re.compile(r"\b(19|20)\d{2}\b"), "MEDIUM"),
    ("full-date", re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"\.?\s+\d{1,2},?\s+\d{4}\b"), "MEDIUM"),
    ("authority", re.compile(
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
        r"\s+(?:argues?|claims?|shows?|finds?|concludes?|writes?|notes?|"
        r"says?|according to)\b"), "HIGH"),
    ("named-source", re.compile(
        r"\b(?:lead researcher|researcher|scientist|author|professor)\b"
        r".{0,50}?\bwas\b\s+\*{0,2}[A-Z][a-z]+"
        r"(?:\s+\*{0,2}[A-Z][a-z]+){0,2}"), "HIGH"),
]

# Phrases that look like attributions but are hedges/opinions — not claims.
HEDGE_RE = re.compile(
    r"\b(?:I think|I believe|in my (?:view|opinion|judgment)|"
    r"my (?:take|judgment|recommendation))\b", re.IGNORECASE)


def _tag_spans(text):
    return [(m.start(), m.end()) for m in TAG_RE.finditer(text)]


def _is_tagged(text, match_start, match_end, tag_spans):
    # Proximity: tag within TAG_WINDOW after the claim.
    for s, e in tag_spans:
        if s >= match_end and s - match_end <= TAG_WINDOW:
            return True
        if s < match_end and e > match_end:
            return True  # tag wraps/overlaps the match
    # Sentence scope: models naturally put one tag at sentence end to cover
    # all claims in the sentence — a tag anywhere in the same sentence counts.
    seg_start = 0
    for m in SENT_END_RE.finditer(text):
        seg_end = m.end()
        if seg_start <= match_start < seg_end:
            return any(seg_start <= s < seg_end for s, e in tag_spans)
        seg_start = seg_end
    return any(s >= seg_start for s, e in tag_spans)


def check_contract(text):
    """Return list of (severity, message) for untagged specific claims."""
    # Strip markdown bold/italic so **Name** still matches name patterns.
    text = re.sub(r"\*\*", "", text)
    violations = []
    tag_spans = _tag_spans(text)
    seen = set()
    for name, rx, sev in PATTERNS:
        for m in rx.finditer(text):
            key = (name, m.start())
            if key in seen:
                continue
            seen.add(key)
            # Skip matches inside a hedge/opinion sentence window
            window_start = max(0, m.start() - 80)
            if HEDGE_RE.search(text[window_start:m.start()]):
                continue
            if _is_tagged(text, m.start(), m.end(), tag_spans):
                continue
            snippet = m.group(0).strip()
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            violations.append(
                (sev, f"untagged {name}: {snippet!r} (add [V]/[U]/[I])"))
    return violations


def main():
    args = sys.argv[1:]
    if args == ["--self-test"]:
        return self_test()
    if len(args) != 1:
        print("usage: contract_check.py <output.txt> | --self-test",
              file=sys.stderr)
        return 2
    try:
        text = open(args[0], errors="replace").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    violations = check_contract(text)
    for sev, msg in violations:
        print(f"[{sev}] {msg}")
    print(f"{len(violations)} contract violation(s)")
    return 1 if violations else 0


def self_test():
    cases = [
        # (name, text, expected_violation_count)
        ("tagged-ok",
         "Revenue grew 12% [U] in 2024 [U]. Fair value $18.56 [V] "
         "(15 x 1.2374 = 18.56). Shiller argues [U] for caution.",
         0),
        ("untagged-number",
         "Revenue grew 12% in 2024 and fair value is $18.56.",
         3),  # 12%, 2024, $18.56
        ("untagged-title",
         'As shown in "Irrational Exuberance and Market Cycles", '
         "multiples compress.",
         1),
        ("untagged-url",
         "See https://example.com/paper.pdf for details.",
         1),
        ("untagged-authority",
         "Shiller argues that multiples always compress late-cycle.",
         1),
        ("opinion-clean",
         "My judgment: this is a hold. I think patience wins here.",
         0),
        ("mixed",
         "The thesis rests on 2021 [V] data. But margins hit 40% in 2023 "
         "and the CEO promised growth.",
         2),  # 40% and 2023 untagged; 2021 tagged
    ]
    fails = 0
    for name, text, expected in cases:
        got = check_contract(text)
        ok = len(got) == expected
        print(f"[{'ok' if ok else 'FAIL'}] {name}: "
              f"expected {expected}, got {len(got)}")
        if not ok:
            fails += 1
            for sev, msg in got:
                print(f"    [{sev}] {msg}")
    print(f"self-test: {len(cases) - fails}/{len(cases)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
