#!/usr/bin/env python3
"""Per-n table for REPORT.md from attempts.jsonl: record, methods tried, best float side, certified side."""
import collections
import json
import os
import sys
from fractions import Fraction as F

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = {r["n"]: r for r in json.load(open(os.path.join(RUN, "records.json")))["records"]}
rows = [json.loads(l) for l in open(os.path.join(RUN, "attempts.jsonl")) if l.strip()]
byn = collections.defaultdict(list)
for r in rows:
    if r["n"] in R:
        byn[r["n"]].append(r)
want = [int(v) for v in sys.argv[1:]] or sorted(byn)
print("| n | record | methods tried | best float side | best − record | certified |")
print("|---|---|---|---|---|---|")
for n in want:
    if n not in byn:
        continue
    rec = float(F(R[n]["upper"]))
    vals = []
    coarse = []                  # values read back from a 7-decimal progress log (stopped basin-hopping runs)
    for r in byn[n]:
        b = r.get("best_float_S")
        if b is None:
            continue
        b = float(b)
        note = str(r.get("note", ""))
        if "reconstructed from the progress log" in note or "last progress at" in note:
            if abs(b - rec) < 6e-8:
                b = rec          # 7-decimal progress value equal to the record within rounding
            coarse.append(b)
        else:
            vals.append(b)
    # a 7-decimal value only counts if it is clearly different from every full-precision value
    for b in coarse:
        if not vals or all(abs(b - v) > 6e-8 for v in vals):
            vals.append(b)
    meths = collections.Counter(str(r.get("method", "")).split(":")[0].split("[")[0].split(" ")[0].strip() for r in byn[n])
    cert = sorted(float(r["certified_S"]) for r in byn[n] if r.get("certified_S"))
    best = min(vals) if vals else None
    print(f"| {n} | {rec:.9f} | {', '.join(f'{k}×{v}' if v > 1 else k for k, v in sorted(meths.items()))} | "
          f"{best:.9f} | {best - rec:+.2e} | {('%.12f' % cert[0]) if cert else ''} |" if best is not None else f"| {n} | {rec:.9f} | {', '.join(sorted(meths))} | – | – | |")
