#!/usr/bin/env python3
"""Summarise attempts.jsonl: per method (first word of 'method'), and per n the best float side vs the record."""
import collections
import json
import os
import sys
from fractions import Fraction as F

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = {r["n"]: r for r in json.load(open(os.path.join(RUN, "records.json")))["records"]}
rows = [json.loads(l) for l in open(os.path.join(RUN, "attempts.jsonl")) if l.strip()]
bym = collections.defaultdict(list)
for r in rows:
    key = str(r.get("method", "")).split(":")[0].split("[")[0].strip() or "?"
    bym[key].append(r)
print(f"{len(rows)} logged attempts")
print("| method | attempts | distinct n | total wall s (sum of per-attempt figures) | below record |")
print("|---|---|---|---|---|")
for k, v in sorted(bym.items(), key=lambda kv: -len(kv[1])):
    below = sum(1 for r in v if r.get("best_float_S") is not None and r["n"] in R and float(r["best_float_S"]) < float(F(R[r["n"]]["upper"])) - 1e-9)
    print(f"| {k} | {len(v)} | {len(set(r['n'] for r in v))} | {sum(float(r.get('wall_seconds') or 0) for r in v):.0f} | {below} |")
byn = collections.defaultdict(list)
for r in rows:
    byn[r["n"]].append(r)
if "--pern" in sys.argv:
    print("\n| n | record | best float S (any method) | diff | methods tried | certified |")
    print("|---|---|---|---|---|---|")
    for n in sorted(byn):
        rec = float(F(R[n]["upper"])) if n in R else None
        vals = [(float(r["best_float_S"]), r) for r in byn[n] if r.get("best_float_S") is not None]
        best = min(vals, key=lambda t: t[0]) if vals else None
        meths = sorted(set(str(r.get("method", "")).split(":")[0].split("[")[0].strip() for r in byn[n]))
        cert = [r["certified_S"] for r in byn[n] if r.get("certified_S")]
        print(f"| {n} | {rec:.9f} | {best[0]:.9f} | {best[0]-rec:+.2e} | {', '.join(meths)} | {min(cert) if cert else ''} |" if best else f"| {n} | {rec} | - | - | {', '.join(meths)} | |")
