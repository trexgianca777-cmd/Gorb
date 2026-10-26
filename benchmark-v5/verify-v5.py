#!/usr/bin/env python3
"""verify-v5.py — prove every candidate task's scorer passes a known-correct
answer and fails known-wrong answers. Exits nonzero on any failure."""
import importlib.util
import inspect
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


design = _load("d5v", os.path.join(BASE, "design-v5.py"))
design = _load("d5v", os.path.join(BASE, "design-v5.py"))
design2 = _load("d5c2", os.path.join(BASE, "design-v5c2.py"))
sc = _load("s5v", os.path.join(BASE, "score-v5.py"))
TASKS = {}
for _jf in ("tasks-v5-candidates.json", "tasks-v5c2-candidates.json"):
    _p = os.path.join(BASE, _jf)
    if os.path.exists(_p):
        for _t in json.load(open(_p))["tasks"]:
            TASKS[_t["id"]] = _t

# Map task -> (module, reference fn, required function name)
REFMAP = {
    "c1-expr-eval-3": ("d5", "ref_eval", "evaluate"),
    "c2-csv-2": ("d5", "ref_parse_csv_row", "parse_csv_row"),
    "c3-sjson-2": ("d5", "ref_parse_sjson", "parse_sjson"),
    "c4-wildcard-2": ("d5", "ref_wildcard", "wildcard_match"),
    "c5-base-convert-2": ("d5", "ref_base_to_int", "base_to_int"),
    "c6-roman-validate": ("d5", "ref_roman_to_int", "roman_to_int"),
    "c7-date-add": ("d5", "ref_add_days", "add_days"),
    "c8-rle-decode": ("d5", "ref_rle_decode", "rle_decode"),
    "c9-brackets": ("d5", "ref_balanced", "is_balanced"),
    "c10-sexpr": ("d5", "ref_sexpr", "seval"),
    "c11-morse": ("d5", "ref_morse_decode", "morse_decode"),
    "c12-caesar-2": ("d5", "ref_caesar_decode", "caesar_decode"),
    "p1-custom-ops": ("d5c2", "ref_custom_eval", "ceval"),
    "p3-unicode-json": ("d5", "ref_parse_sjson", "parse_sjson"),
    "p4-csv-multiline": ("d5", "ref_parse_csv_row", "parse_csv_row"),
    "p6-tally": ("d5c2", "ref_tally", "base_to_int"),
    "p8-bizdays": ("d5c2", "ref_add_bizdays", "add_business_days"),
    "p9-sexpr-let": ("d5c2", "ref_sexpr_let", "seval"),
    "p12-ipv4": ("d5c2", "ref_ipv4", "ipv4_to_int"),
    "p13-cron": ("d5c2", "ref_cron_min", "cron_minutes"),
}
MODULES = {"d5": design, "d5c2": design2}


def ref_code_answer(tid):
    modkey, refname, fname = REFMAP[tid]
    mod = MODULES[modkey]
    src = inspect.getsource(getattr(mod, refname))
    # rename the def line; keep helper references used by the function
    src = src.replace(f"def {refname}(", f"def {fname}(", 1)
    # inline small helpers the reference depends on
    helpers = ""
    for h in ["_ROMAN_VAL", "_ROMAN_SUB", "ref_int_to_roman",
              "_MORSE", "_MORSE_REV",
              "_days_from_civil", "_civil_from_days", "_weekday", "_ANCHOR"]:
        if h in src and f"def {h}" not in src and f"{h} =" not in src:
            for mk in ("d5", "d5c2"):
                try:
                    hsrc = inspect.getsource(getattr(MODULES[mk], h))
                    helpers += hsrc + "\n"
                    break
                except (TypeError, AttributeError):
                    continue
            else:
                # getsource failed in both modules (h is a value, not a
                # function): inline its repr from whichever module has it
                for mk in ("d5", "d5c2"):
                    try:
                        helpers += f"{h} = {getattr(MODULES[mk], h)!r}\n"
                        break
                    except AttributeError:
                        continue
    # make inlined helpers standalone: drop the d5. module prefix
    # (applies to helpers and the main source alike)
    blob = ("```python\nimport re\n" + helpers + src + "\n```")
    blob = blob.replace("d5._days_from_civil", "_days_from_civil")
    blob = blob.replace("d5._civil_from_days", "_civil_from_days")
    # transitive dep: inlined _weekday needs the anchor value
    if "_weekday" in blob and "_ANCHOR =" not in blob:
        assert blob.endswith("```")
        blob = (blob[:-3] +
                f"_ANCHOR = {MODULES['d5c2']._ANCHOR!r}\n```")
    return blob


GOOD_TEXT = {
    "w1-double-constraint":
        "Great work is done. Only practice makes done. Long hours are done. "
        "Daily effort is done.",
    "w2-word-count":
        "One two three four five six. Seven eight nine ten eleven twelve. "
        "Red blue green yellow black white. Cats dogs birds fish swim fast. "
        "Spring summer autumn winter come soon.",
    "w3-acrostic":
        "Many sailors love the sea, and they sing songs. "
        "Across the waves the gulls cry free. "
        "Rough storms test every brave heart, yet crews endure more. "
        "Silent harbors welcome tired ships home again.",
    "w4-comma-exact":
        "I bought apples, oranges, and pears. "
        "She ran fast, jumped high, and won. "
        "We ate, we drank, we left.",
    "w5-lines-words":
        "- alpha beta gamma delta\n* epsilon zeta eta theta\n"
        "- iota kappa lambda mu\n* nu xi omicron pi\n"
        "- rho sigma tau upsilon\n* phi chi psi omega",
    "w6-n-words": None,  # built below (41 words)
    "s2-seven-words": "I will do exactly what you asked",
    "r1-six-seven":
        "Apples grow on tall trees daily here. "
        "Birds sing sweet songs each bright morning. "
        "Cats chase small mice around old barns. "
        "Dogs bark loudly at passing strangers now. "
        "Eagles fly high above rocky mountain peaks. "
        "Frogs jump quickly into cool pond water.",
    "r2-acrostic-5":
        "High above the earth the stars shine bright somehow. "
        "Every night the moon follows its arc through the halo. "
        "Lonely comets cross the dark sky forever. "
        "Last light fades as the planets turn still. "
        "Old telescopes watch the quiet void.",
    "r3-para-words": None,  # built below (6 sentences x 10 words)
    "r4-lines-8":
        "- alpha beta gamma delta epsilon\n"
        "* zeta eta theta iota kappa\n"
        "- lambda mu nu xi omicron\n"
        "* pi rho sigma tau upsilon\n"
        "- phi chi psi omega aleph\n"
        "* beth gimel dalet he vav\n"
        "- zayin het tet yod kaf\n"
        "* lamed mem nun samekh ayin",
    "r5-fifty-words": None,  # built below (50 words, 5 sentences)
    "r6-commas-3":
        "I bought apples, oranges, bananas, and pears. "
        "She ran fast, jumped high, stumbled once, and won. "
        "We ate well, drank deeply, laughed loudly, and left.",
    "r7-growing":
        "I like to eat apples. "
        "She likes to eat green apples. "
        "They like to eat big green apples. "
        "We like to eat fresh green apples daily.",
    "r8-no-e":
        "A dark night sky. "
        "Bright orbs glow at midnight. "
        "Clouds drift past Mars.",
}
_words41 = ["desert"] * 41
assert len(_words41) == 41
GOOD_TEXT["w6-n-words"] = " ".join(_words41) + "."

_words60 = [f"w{i}" for i in range(60)]
GOOD_TEXT["r3-para-words"] = " ".join(
    " ".join(_words60[i * 10:(i + 1) * 10]) + "." for i in range(6))

_words50 = [f"w{i}" for i in range(50)]
GOOD_TEXT["r5-fifty-words"] = " ".join(
    " ".join(_words50[i * 10:(i + 1) * 10]) + "." for i in range(5))

BAD_TEXT = {
    "w1-double-constraint": "Great work is done. Only practice makes done. Long hours.",
    "w2-word-count": "One two three four five. Too short here.",
    "w3-acrostic": "Hello world. Another test here.",
    "w4-comma-exact": "No commas here at all. Still none.",
    "w5-lines-words": "- only three words here\n* too few",
    "w6-n-words": "way too short.",
    "s2-seven-words": "I will do something what you asked",
    "r1-six-seven": "Too short. Also too short.",
    "r2-acrostic-5": "Hello world. Another test.",
    "r3-para-words": "Too short.",
    "r4-lines-8": "- only three words here\n* too few",
    "r5-fifty-words": "way too short.",
    "r6-commas-3": "No commas here at all.",
    "r7-growing": "Too short.",
    "r8-no-e": "Here is a sentence with e.",
}


def good_answer(task):
    tid = task["id"]
    if tid in REFMAP:
        return ref_code_answer(tid)
    if tid in GOOD_TEXT:
        return GOOD_TEXT[tid]
    exp = task.get("expected")
    if exp is not None:
        return str(exp)
    raise ValueError(f"no good answer for {tid}")


def bad_answers(task):
    tid = task["id"]
    if tid in REFMAP:
        return ["def broken(:\n  pass"]
    if tid in BAD_TEXT:
        return [BAD_TEXT[tid]]
    exp = str(task.get("expected", ""))
    if task["scorer"] in ("digits_strict",):
        # flip last digit
        last = exp[-1]
        flipped = "0" if last != "0" else "1"
        return [exp[:-1] + flipped]
    if task["scorer"] in ("numeric_decimal", "numeric_tolerance"):
        return [str(float(exp) + 100.0)]
    if task["scorer"] == "token_strict":
        return ["zzzzqqqq"]
    return ["wrong"]


def main():
    fails = []
    for tid, task in sorted(TASKS.items()):
        scorer = sc.SCORERS[task["scorer"]]
        try:
            g = good_answer(task)
            ok, detail = scorer(g, task)
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"scorer crashed on GOOD: {e}"
        if not ok:
            fails.append((tid, "GOOD failed", detail))
            continue
        for b in bad_answers(task):
            try:
                okb, detailb = scorer(b, task)
            except Exception as e:  # noqa: BLE001
                okb, detailb = False, f"scorer crashed on BAD: {e}"
            if okb:
                fails.append((tid, "BAD passed", detailb[:120]))
    if fails:
        print(f"{len(fails)} verification failures:")
        for tid, kind, d in fails:
            print(f"  {tid}: {kind}: {d}")
        sys.exit(1)
    print(f"all {len(TASKS)} tasks verified: good-pass + bad-fail OK")


if __name__ == "__main__":
    main()
