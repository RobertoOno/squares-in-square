#!/usr/bin/env python3
"""Build records.json from the downloaded copy of David Ellsworth's "Squares in Squares" page
(the maintained successor of Erich Friedman's Packing Center page) plus the lower-bound table
of Friedman's survey (EJC DS7, 2009 version).

Inputs (downloaded verbatim into work/web/ on 2026-11-11):
  ellsworth_squares.html                      Kingbird flat grid view (HTTP Last-Modified 2026-09-24)
  squares_in_squares__triangular_table.html   Kingbird triangular view (internal cross-check)
  sqproj_cases.json                           front matter of the 324 case records
                                              https://github.com/jlevy/squares/tree/main/packing/frontier
                                              ("The Squares Project", repo head 591644a9e9, 2026-11-11T11:02Z);
                                              the same values are shown on https://jlevy.github.io/squares/frontier.html

For every n the SMALLER of the two published upper bounds is recorded (a record transcribed
too high would fake an improvement). An n is flagged proven_optimal if EITHER source lists a
proof, including proofs that are only *reported* (not yet replayed by the Squares Project).

Published values are copied as strings, digit for digit. Nothing is rounded or recomputed.
"""
import html
import json
import math
import os
import re
import sys
from fractions import Fraction as F

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RUN, "work", "web")
URL = "https://kingbird.myphotos.cc/packing/squares_in_squares.html"
URL_TRI = "https://kingbird.myphotos.cc/packing/squares_in_squares__triangular_table.html"
URL_SURVEY = "https://erich-friedman.github.io/papers/squares/squares.html"
URL_SP = "https://jlevy.github.io/squares/frontier.html"
URL_SP_CASE = "https://github.com/jlevy/squares/blob/main/packing/frontier/n-%03d.md"
SP_HEAD = "591644a9e9 (2026-11-11T11:02:26Z)"
RETRIEVED = "2026-11-11"
PAGE_LAST_MODIFIED = "2026-09-24"
NMAX = 324  # the page states: "For the n <= 324 not pictured, the trivial packing ... is the best known"


def parse_boxes(path):
    s = open(path, encoding="utf-8").read()
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    out = []
    for b in re.findall(r'<div class="box"><font size="\+3">(.*?)</div></div>', s, flags=re.S):
        label = b.split("<br>")[0]
        nums = [int(x) for x in re.findall(r"\d+", label)]
        d = b[b.find("<div"):]
        txt = re.sub(r"<br\s*/?>", " | ", d)
        txt = re.sub(r"<[^>]+>", "", txt)
        txt = html.unescape(re.sub(r"\s+", " ", txt)).strip()
        vals = re.findall(r"\\Nn\{([0-9.]+)\}", txt)
        if vals:
            assert len(set(vals)) == 1, (label, vals)
            val = vals[0]
        else:
            m = re.search(r"\$s = ([0-9]+(?:\.[0-9]+)?)\$", txt)
            assert m, (label, txt[:200])
            val = m.group(1)
        cf = re.search(r"s &?= (.*?) (?:\\\\ &)?= \\Nn", txt)
        closed = cf.group(1).strip() if cf else ""
        if "🔒" in closed:
            closed = "polynomial root (see source page)"
        svg = re.search(r'<a href="([^"]+\.svg)"', b)
        attrib = re.sub(r"\$[^$]*\$", "", txt)          # drop math
        attrib = re.sub(r"\s*\|\s*", " ", attrib).strip()
        attrib = re.sub(r"\s+", " ", attrib)
        out.append(dict(nums=nums, val=val, closed=closed, attrib=attrib, text=txt,
                        svg=svg.group(1) if svg else None))
    return out


# Friedman survey (DS7, 2009), Table 2 "Best known lower bounds for s(n)", plus later proofs
# listed on the Ellsworth page. Values as printed in the survey (4 decimals).
SURVEY_LOWER = [
    # (n_lo, n_hi, value, text)
    (11, 12, "3.7888", "2+4/sqrt(5), Stromquist (survey Thm 11)"),
    (17, 18, "4.4452", "(40*sqrt(2)+19)/17, Green"),
    (19, 20, "4.4852", "6*sqrt(2)-4, Friedman"),
    (21, 21, "4.7438", "Friedman"),
    (26, 27, "5.3918", "2*sqrt(2)+(27+2*sqrt(10))/13, Green"),
    (28, 30, "5.5117", "2*sqrt(2)+6/sqrt(5), Green"),
    (31, 31, "5.6415", "Green"),
    (37, 39, "6.3506", "2*sqrt(2)+(113+10*sqrt(3))/37, Green"),
    (40, 41, "6.4061", "2*sqrt(2)+8/sqrt(5), Green"),
    (50, 53, "7.3174", "2*sqrt(2)+(101+3*sqrt(14))/25, Green"),
    (65, 68, "8.2899", "2*sqrt(2)+71/13, Green"),
    (82, 85, "9.2667", "2*sqrt(2)+(288+12*sqrt(3))/41, Green"),
]


def main():
    flat = parse_boxes(os.path.join(WEB, "ellsworth_squares.html"))
    tri_path = os.path.join(WEB, "squares_in_squares__triangular_table.html")
    tri_vals = {}
    if os.path.exists(tri_path):
        s = open(tri_path, encoding="utf-8").read()
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        for m in re.finditer(r'<div class="box"><font size="\+3">(\d+)\.<br>(.*?)</div></div>', s, flags=re.S):
            n = int(m.group(1))
            txt = m.group(2)
            v = re.findall(r"\\Nn\{([0-9.]+)\}", txt)
            if not v:
                mm = re.search(r"\$s = ([0-9]+(?:\.[0-9]+)?)\$", txt)
                v = [mm.group(1)] if mm else []
            if v:
                tri_vals[n] = v[0]

    by_n = {}
    for b in flat:
        for n in b["nums"]:
            assert n not in by_n, n
            by_n[n] = b

    # cross-check flat vs triangular view (the triangular view labels each picture with its largest n)
    mism = [(n, by_n[n]["val"], v) for n, v in tri_vals.items() if n in by_n and by_n[n]["val"] != v]
    if mism:
        print("MISMATCH flat vs triangular:", mism, file=sys.stderr)
        sys.exit(1)

    proven = {}
    for n, b in by_n.items():
        t = b["attrib"]
        if "Proved by" in t or t.startswith("Trivial"):
            proven[n] = t
    cases = {int(k): v for k, v in json.load(open(os.path.join(WEB, "sqproj_cases.json"))).items()}
    records = []
    best_lower = F(0)
    lower_note = ""
    n_sp_better = 0
    for n in range(1, NMAX + 1):
        k = math.isqrt(n - 1) + 1  # ceil(sqrt(n))
        e = {"n": n}
        # --- Kingbird value
        if n in by_n:
            b = by_n[n]
            kb_val = b["val"]
            kb_note = b["attrib"]
            if b["closed"]:
                kb_note = f"s = {b['closed']}. " + kb_note
            if len(b["nums"]) > 1:
                kb_note += f" [page label covers n = {', '.join(map(str, b['nums']))}; smaller n by removing a square]"
        else:
            kb_val = str(k)
            kb_note = ("Not pictured on the Kingbird page, which states that for n <= 324 not pictured the "
                       "trivial packing (no tilted squares), side ceil(sqrt(n)), is the best known.")
        # --- Squares Project value
        c = cases[n]
        ru = c["reported_upper_bound"]
        sp_val = str(ru["value"])
        sp_ver = str(c["verified_upper_bound"]["value"])
        who = ", ".join(ru.get("found_by") or [])
        imp = ", ".join(str(x) for x in (ru.get("improved_by") or []))
        sp_note = f"Squares Project case record: reported upper {sp_val}"
        if who:
            sp_note += f", found by {who} ({ru.get('found_year')})"
        if imp:
            sp_note += f", improved by {imp}"
        if ru.get("source_date"):
            sp_note += f", source date {ru.get('source_date')}"
        if ru.get("exact_form") and len(str(ru.get("exact_form"))) < 80:
            sp_note += f", exact form {ru.get('exact_form')}"
        if F(sp_val) < F(kb_val):
            n_sp_better += 1
            e["upper"] = sp_val
            e["source"] = URL_SP_CASE % n
            note = (sp_note + f". Shown on {URL_SP}. Supersedes the Kingbird value {kb_val} ({kb_note[:300]})")
        else:
            e["upper"] = kb_val
            e["source"] = URL
            note = kb_note + f" | Second source agrees or is not lower: {sp_note} ({URL_SP_CASE % n})"
        e["upper_kingbird"] = kb_val
        e["upper_squares_project"] = sp_val
        if F(sp_ver) != F(sp_val):
            e["upper_squares_project_verified"] = sp_ver
        kb_proved = bool(n in proven or k * k == n)
        sp_proved = c.get("status") == "proved"
        sp_reported = c.get("reported_status") == "proved"
        e["proven_optimal"] = bool(kb_proved or sp_proved or sp_reported)
        if e["proven_optimal"]:
            why = []
            if kb_proved:
                why.append("Kingbird: " + (proven.get(n) or "trivial (perfect square)"))
            if sp_proved:
                why.append("Squares Project status 'proved'")
            elif sp_reported:
                why.append("Squares Project: optimality proof REPORTED but not yet replayed there (status 'open (reported proved)'); "
                           "flagged proven here to stay conservative")
            e["proven_note"] = "; ".join(why)
        # --- lower bound: best of survey Table 2 / proofs (monotone) / area / Squares Project verified lower
        cand = []
        if e["proven_optimal"] and not (sp_reported and not sp_proved and not kb_proved):
            cand.append((F(e["upper"]), "proven optimal"))
        for lo, hi, v, txt in SURVEY_LOWER:
            if lo <= n <= hi:
                cand.append((F(v), f"Friedman survey DS7 (2009) Table 2: {txt} ({URL_SURVEY})"))
        vl = c.get("verified_lower_bound") or {}
        if vl.get("value") is not None:
            pb = (c.get("reported_lower_bound") or {})
            cand.append((F(str(vl["value"])), "Squares Project verified lower bound"
                         + (f" ({', '.join(pb.get('proved_by') or [])} {pb.get('proved_year') or ''})" if pb.get("proved_by") else "")
                         + f" ({URL_SP_CASE % n})"))
        for v, txt in cand:
            if v > best_lower:
                best_lower, lower_note = v, f"n={n}: {txt}"
        lo_f = float(best_lower)
        sq = math.sqrt(n)
        if sq > lo_f + 1e-12:
            e["lower"] = f"{math.floor(sq * 1e6) / 1e6:.6f}"
            e["lower_source"] = "area bound sqrt(n), truncated to 6 decimals"
        else:
            e["lower"] = f"{math.floor(lo_f * 1e6) / 1e6:.6f}".rstrip("0").rstrip(".")
            e["lower_source"] = "monotonicity s(n) >= s(m) for m <= n, from " + lower_note
        e["retrieved"] = RETRIEVED
        e["note"] = note[:1200]
        records.append(e)

    doc = {
        "_doc": ("Best known upper bounds for s(n), n = 1..324, taken as the SMALLER of two public catalogues, both "
                 f"retrieved {RETRIEVED}. (1) 'Squares in Squares' maintained by David Ellsworth, the successor of Erich "
                 "Friedman's Packing Center page (https://erich-friedman.github.io/packing/squinsqu/ now redirects to it): "
                 f"{URL} (HTTP Last-Modified {PAGE_LAST_MODIFIED}; cross-checked against {URL_TRI}). It prints 14 "
                 "decimals followed by an ellipsis (truncated). (2) The Squares Project frontier, "
                 f"{URL_SP}, whose per-n case records live at https://github.com/jlevy/squares/tree/main/packing/frontier "
                 f"(repo head {SP_HEAD}); it supersedes (1) at many n with results from September-November 2026. "
                 "'upper' is copied digit for digit from whichever source is lower; 'upper_kingbird' and "
                 "'upper_squares_project' keep both. upper_truncated_down is deliberately NOT set anywhere, so verify.py "
                 "subtracts half a unit in the last printed place before comparing (conservative). proven_optimal is true "
                 "if either source lists a proof, including proofs only reported. Lower bounds: Friedman, 'Packing Unit "
                 f"Squares in Squares: A Survey and New Results', EJC DS7 (2009), Table 2 ({URL_SURVEY}); the Squares "
                 "Project's verified lower bounds; optimality proofs; all extended by monotonicity and the area bound."),
        "source_page_last_modified": {"kingbird": PAGE_LAST_MODIFIED, "squares_project_repo_head": SP_HEAD},
        "records": records,
    }
    with open(os.path.join(RUN, "records.json"), "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    nontriv = [r for r in records if "." in r["upper"]]
    print(f"wrote {len(records)} records; {len(nontriv)} non-integer; {sum(r['proven_optimal'] for r in records)} proven optimal")
    print("cross-checked against triangular view:", len(tri_vals), "values, no mismatch")
    print("n where the Squares Project value is lower than Kingbird:", n_sp_better)


if __name__ == "__main__":
    main()
