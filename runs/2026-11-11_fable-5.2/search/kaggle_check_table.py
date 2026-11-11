#!/usr/bin/env python3
"""Post-run correction: write evidence/kaggle_per_puzzle_check.md, the comparison of the Kaggle
per-puzzle leaderboard with the two catalogues.  Run after add_kaggle_source.py (it reads the fields
that script adds to records.json) and with the frozen verifier available at the repository root."""
import json
import os
import re
import subprocess
import sys
from fractions import Fraction as F

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(RUN))
URL = "https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard"
POST = "https://www.kaggle.com/competitions/squares-in-squares/discussion/751633"
CERTS = [(147, "n147_S65104355.json"), (228, "n228_S59604312.json"), (228, "n228_S59708491.json")]


def cert_side(name):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "verify.py"), os.path.join(RUN, "certificates", name)],
                         capture_output=True, text=True).stdout
    m = re.search(r"exact: (\d+)/(\d+)", out)
    return F(int(m.group(1)), int(m.group(2)))


def dec(x, places):
    """Decimal string of a Fraction, truncated toward zero."""
    q = x.numerator * 10 ** places // x.denominator
    s = str(q).rjust(places + 1, "0")
    return s[:-places] + "." + s[-places:]


doc = json.load(open(os.path.join(RUN, "records.json"), encoding="utf-8"))
R = {int(r["n"]): r for r in doc["records"]}
real, digits, above = [], [], []
for n, r in sorted(R.items()):
    if "kaggle_team" not in r:
        continue
    cat = F(r.get("upper_catalogues", r["upper"]))
    d = F(r["upper_kaggle_per_puzzle"]) - cat
    (real if d < F(-1, 10 ** 12) else digits if d < 0 else above if d > 0 else []).append((n, d))

L = []
L.append("# Kaggle per-puzzle leaderboard against the two catalogues (check made after the run)\n")
L.append(f"- Source: `{URL}`, a notebook kept by Kaggle staff and announced in the competition's pinned")
L.append(f"  discussion \"Per-Puzzle Leaderboard\" (`{POST}`). The post says it refreshes about once a day, with a lag.")
L.append(f"- Copy used: {doc['source_page_last_modified']['kaggle_per_puzzle_notebook']}.")
L.append("  The sides in it can only have gone down since.")
L.append("- Columns: n, \"Best Side Length L (50 decimals)\", TeamName, DateSubmitted. Rows whose team is \"-\" are the")
L.append("  organisers' baseline; the others are the smallest side the competition's grader has accepted from a team.")
L.append("- It is **side only**: no packing is published.")
L.append("- \"Catalogues\" below means the smaller of the Kingbird page and the Squares Project, which is what")
L.append("  `records.json` held during the run.\n")
L.append("## The two withdrawn claims\n")
L.append("| n | certificate (this run) | certified side | Kaggle side, as published | team | submitted | certificate − Kaggle |")
L.append("|---|---|---|---|---|---|---|")
for n, name in CERTS:
    S = cert_side(name)
    r = R[n]
    L.append(f"| {n} | `certificates/{name}` | {dec(S, 15)}… | {r['upper_kaggle_per_puzzle']} | {r['kaggle_team']} | "
             f"{r['kaggle_date_submitted']} | {float(S - F(r['upper_kaggle_per_puzzle'])):+.4e} |")
L.append("\nThe frozen verifier, run against the corrected `records.json`, prints `does not beat record` for all three.\n")
L.append(f"## Every n ≤ 324 where a team's side is below both catalogues by more than 1e-12 ({len(real)} values of n)\n")
L.append("| n | catalogues | Kaggle side (20 decimals; all 50 are in `records.json`) | team | submitted | Kaggle − catalogues |")
L.append("|---|---|---|---|---|---|")
for n, d in real:
    r = R[n]
    L.append(f"| {n} | {r.get('upper_catalogues', r['upper'])} | {dec(F(r['upper_kaggle_per_puzzle']), 20)} | {r['kaggle_team']} | "
             f"{r['kaggle_date_submitted']} | {float(d):+.3e} |")
L.append(f"\n## Same record, more digits ({len(digits)} values of n)\n")
L.append("A team's side is below the catalogue value by less than 1e-12 (largest difference "
         f"{max(float(-d) for _, d in digits):.1e}): the same packing, printed with more digits. `records.json` takes the")
L.append("Kaggle digits here too, because the smaller published value is the safer bar.\n")
L.append("n = " + ", ".join(str(n) for n, _ in digits) + "\n")
L.append(f"## A team's side above the catalogues ({len(above)} values of n)\n")
L.append("The catalogue value is newer than this copy of the Kaggle table, or more tightly rounded: "
         + "; ".join(f"n = {n} ({float(d):+.1e})" for n, d in above) + ".\n")
L.append("## How to fetch it again\n")
L.append("Open the notebook; the table is in its rendered output, embedded as a JSON array (`DATA`) of")
L.append("`{n, L, team, date}`. `search/add_kaggle_source.py` reads it as four tab-separated columns from")
L.append("`work/web/kaggle_perpuzzle/per_puzzle_v28.tsv`.")
open(os.path.join(RUN, "evidence", "kaggle_per_puzzle_check.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"written: {len(real)} real gaps, {len(digits)} digit-level, {len(above)} above")
