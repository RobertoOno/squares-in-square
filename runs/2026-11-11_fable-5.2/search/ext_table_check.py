#!/usr/bin/env python3
"""Compare a third-party directory of packings (cert / npz, any n) with records.json:
prints every n <= 324 where the third-party side is below our table value (i.e. our table would be stale),
and summary counts.  Usage: ext_table_check.py DIR [DIR ...]"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import attack  # noqa: E402
import diagper  # noqa: E402
from sqgeom import max_violation  # noqa: E402

for d in sys.argv[1:]:
    labels = diagper.dir_labels(d)
    best = {}
    bad = 0
    for lab in labels:
        try:
            S, x, y, th = diagper.source(lab)
            mo, mw = max_violation(x, y, th, S + 1e-9)
        except Exception:  # noqa: BLE001
            bad += 1
            continue
        if max(mo, mw) > 1e-6:
            bad += 1
            continue
        n = len(x)
        if n not in best or S < best[n][0]:
            best[n] = (S, os.path.basename(lab))
    N = max(attack.R())
    lower = [(n, S, f) for n, (S, f) in sorted(best.items()) if n <= N and S < attack.rec(n) - 1e-8]
    same = sum(1 for n, (S, f) in best.items() if n <= N and abs(S - attack.rec(n)) <= 1e-8)
    worse = sum(1 for n, (S, f) in best.items() if n <= N and S > attack.rec(n) + 1e-8)
    big = sum(1 for n in best if n > N)
    print(f"{d}: {len(labels)} files, {bad} unreadable/invalid, {len(best)} distinct n ({big} with n > {N}); "
          f"n <= {N}: {same} equal to our table, {worse} worse, {len(lower)} BELOW our table")
    for n, S, f in lower:
        print(f"   n={n}: third-party {S:.10f} < our record {attack.rec(n):.10f} (diff {S-attack.rec(n):+.2e})  [{f}]")
    for n in (147, 228):
        if n in best:
            print(f"   n={n}: third-party best {best[n][0]:.10f}, table {attack.rec(n):.10f}")
