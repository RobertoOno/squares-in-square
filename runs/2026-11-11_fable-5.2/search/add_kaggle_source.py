#!/usr/bin/env python3
"""Post-run correction: add a third public source to records.json.

The source is the Kaggle "Squares in Squares" per-puzzle leaderboard, a notebook kept by Kaggle staff
that lists, for every n = 1..1000, the smallest container side any team has had accepted by the
competition's grader (side only: no packing is published), with the team and the submission time:

    https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard

Input: work/web/kaggle_perpuzzle/per_puzzle_v28.tsv (n, side with 50 decimals, team, date), parsed
from the notebook's rendered output (version 28, retrieved 2026-11-11 22:06 UTC).  Rows whose team is
"-" are the organisers' baseline, not a result, and never replace anything.

Every entry gets `upper_kaggle_per_puzzle` (and the team and date when a team holds the row).  Where a
team's side is smaller than the current `upper` (exact rational comparison), `upper` and `source` are
replaced by the Kaggle value, copied digit for digit, and the previous value and source are kept in
`upper_catalogues` / `source_catalogues`.  Idempotent.  Usage: add_kaggle_source.py [--dry]
"""
import json
import os
import sys
from fractions import Fraction as F

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(RUN, "work", "web", "kaggle_perpuzzle", "per_puzzle_v28.tsv")
REC = os.path.join(RUN, "records.json")
URL = "https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard"
TABLE = "notebook version 28; newest submission in the table 2026-11-08 04:29:46 UTC; retrieved 2026-11-11 22:06 UTC"
DOC3 = (" POST-RUN CORRECTION (2026-11-11, after the run had ended): a third public source was added, "
        "(3) the Kaggle 'Squares in Squares' per-puzzle leaderboard, " + URL + " (" + TABLE + "), which "
        "lists the smallest side accepted by the competition's grader for each n, side only, with no "
        "packing. Every entry carries it in 'upper_kaggle_per_puzzle'. Where a team's side is smaller "
        "than both catalogues, 'upper' and 'source' now hold the Kaggle value, copied digit for digit "
        "(50 decimals), and 'upper_catalogues' / 'source_catalogues' keep what the two catalogues say. "
        "So 'upper' is the SMALLEST of three public sources. See search/add_kaggle_source.py.")


def main():
    dry = "--dry" in sys.argv
    kag = {}
    with open(TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            n, side, team, date = line.rstrip("\n").split("\t")
            kag[int(n)] = (side, team, date)
    rec = json.load(open(REC, encoding="utf-8"))
    changed = []
    for r in rec["records"]:
        n = int(r["n"])
        side, team, date = kag[n]
        r["upper_kaggle_per_puzzle"] = side
        if team != "-":
            r["kaggle_team"] = team
            r["kaggle_date_submitted"] = date
        base = r.get("upper_catalogues", r["upper"])          # idempotent: compare with the catalogue value
        if team != "-" and F(side) < F(base):
            if "upper_catalogues" not in r:
                r["upper_catalogues"] = r["upper"]
                r["source_catalogues"] = r["source"]
                r["note"] = (f"Kaggle per-puzzle leaderboard ({TABLE}): side only, no public packing; "
                             f"team {team}, submitted {date}. Supersedes the catalogue value "
                             f"{r['upper_catalogues']} ({r['source_catalogues']}). | " + r.get("note", ""))
            r["upper"] = side
            r["source"] = URL
            changed.append((n, float(F(side) - F(base)), team, date))
    if "POST-RUN CORRECTION" not in rec["_doc"]:
        rec["_doc"] += DOC3
    rec["source_page_last_modified"]["kaggle_per_puzzle_notebook"] = TABLE
    print(f"{len(changed)} entries now take their upper bound from the Kaggle per-puzzle leaderboard:")
    for n, d, team, date in changed:
        print(f"  n={n:3d}  Kaggle - catalogues = {d:+.3e}  {team}  {date}")
    if dry:
        print("(dry run: records.json not written)")
        return
    with open(REC, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)      # same serialisation as build_records.py
    print("records.json written")


if __name__ == "__main__":
    main()
