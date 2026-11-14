#!/usr/bin/env python3
"""List near misses of the closure passes from their logs: per target m, the best optimised side that is
above the record by more than 2e-7 (i.e. not a reproduction) and by less than --max.
Usage: near_misses.py [--max 0.004] LOGDIR [LOGDIR ...]"""
import argparse
import glob
import os
import re

ap = argparse.ArgumentParser()
ap.add_argument("--max", type=float, default=0.004)
ap.add_argument("dirs", nargs="+")
a = ap.parse_args()
pat = re.compile(r"src (\S+) (red|ext|cross) p=(\d+) c=([\d.]+)(?: b=([\d.]+))? -> m=(\d+) S=([\d.]+) record ([\d.]+) diff ([+-][\d.]+)")
best = {}
below = {}
nlines = 0
for d in a.dirs:
    for f in sorted(glob.glob(os.path.join(d, "*.log"))):
        for line in open(f, errors="replace"):
            mm = pat.search(line)
            if not mm:
                continue
            nlines += 1
            src, kind, p, c, b, m, S, rec, diff = mm.groups()
            m = int(m); S = float(S); rec = float(rec); dd = S - rec
            if dd < -1e-9:
                if m not in below or S < below[m][0]:
                    below[m] = (S, rec, src, kind, p, c, os.path.basename(f))
            elif 2e-7 < dd < a.max:
                if m not in best or S < best[m][0]:
                    best[m] = (S, rec, src, kind, p, c, os.path.basename(f))
print(f"{nlines} optimised leads read")
print("below record:")
for m in sorted(below):
    S, rec, src, kind, p, c, f = below[m]
    print(f"  m={m} S={S:.9f} record {rec:.9f} diff {S-rec:+.6f}  from {src} {kind} p={p} c={c} [{f}]")
print(f"near misses (2e-7 < diff < {a.max}), best per m, {len(best)} targets:")
for m in sorted(best, key=lambda m: best[m][0] - best[m][1]):
    S, rec, src, kind, p, c, f = best[m]
    print(f"  m={m} S={S:.9f} record {rec:.9f} diff {S-rec:+.6f}  from {src[:50]} {kind} p={p} c={c} [{f}]")
