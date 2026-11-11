#!/usr/bin/env python3
"""Clean-strip surgery (the exact 'remove rows and columns' operation of closure.py) applied to
third-party certificate files, e.g. the published packings with n > 324. A hit is a packing of m <= 324
squares, obtained by deleting clean strips, whose side is below the table value for m."""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import attack  # noqa: E402
import closure  # noqa: E402
import diagper  # noqa: E402
from sqgeom import max_violation  # noqa: E402

d = sys.argv[1]
hits = []
nfiles = 0
for f in sorted(glob.glob(os.path.join(d, "*.cert"))):
    try:
        S, x, y, th = diagper.load_cert(f)
        mo, mw = max_violation(x, y, th, S + 1e-9)
        if max(mo, mw) > 1e-6:
            continue
    except Exception:  # noqa: BLE001
        continue
    nfiles += 1
    n = len(x)
    best, ncx, ncy = closure.surgery(n, S, x, y, th, 1e-9)
    for m, (side, strips) in best.items():
        if m < 26 or m > 324 or attack.R()[m]["proven_optimal"]:
            continue
        if side < attack.rec(m) - 1e-7:
            hits.append((attack.rec(m) - side, m, side, attack.rec(m), os.path.basename(f), n, S, strips))
hits.sort(reverse=True)
print(nfiles, "valid certificate files;", len(hits), "strip-surgery hits against the n<=324 table")
seen = set()
for h in hits:
    if h[1] in seen:
        continue
    seen.add(h[1])
    print("  m=%d: side %.9f < record %.9f (gain %.3e) from %s (n=%d, S=%.6f) strips x[%.3f,%.3f] y[%.3f,%.3f]" % (h[1], h[2], h[3], h[0], h[4], h[5], h[6], *h[7]))
json.dump([dict(gain=h[0], m=h[1], side=h[2], rec=h[3], file=h[4], n=h[5], S=h[6], strips=list(h[7])) for h in hits],
          open(os.path.join(os.path.dirname(HERE), "work", "bigclosure_hits.json"), "w"), indent=0)
