#!/usr/bin/env python3
"""Table-consistency ("closure") checks on the merged record table.

A record table that is updated daily by many people can miss cheap consequences:
  (a) monotonicity:  s(n) <= s(n+1)                      (delete a square)
  (b) L-extension:   s(n + 2*floor(S) + 1) <= S + 1       (add a row and a column)
  (c) strip surgery: if a published packing has a "clean" vertical strip [c1,c2] and a clean
      horizontal strip [d1,d2] (no square is cut by the strip borders), deleting the squares
      inside the strips and closing up gives a packing of the remaining m squares in a square
      of side S - min(c2-c1, d2-d1).  With unit-wide strips this is the classical "un-extension".

Any hit is only a lead: it still has to be built as an explicit packing and certified.
"""
import json
import math
import os
import sys
from fractions import Fraction as F

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def load_records():
    recs = json.load(open(os.path.join(RUN, "records.json")))["records"]
    return {r["n"]: r for r in recs}


def clean_lines(lo, hi, S, tol=1e-9):
    """Coordinates c in [0,S] such that no interval (lo_i, hi_i) strictly contains c. Candidates: endpoints."""
    cand = np.unique(np.round(np.concatenate([[0.0, S], lo, hi]), 10))
    out = []
    for c in cand:
        if c < -tol or c > S + tol:
            continue
        if not np.any((lo < c - tol) & (hi > c + tol)):
            out.append(float(c))
    return out


def surgery(n, S, x, y, th, tol=1e-9):
    """Yield (m, new_side, description) for all single-vertical x single-horizontal clean strip removals."""
    h = 0.5 * (np.abs(np.cos(th)) + np.abs(np.sin(th)))
    xl, xh, yl, yh = x - h, x + h, y - h, y + h
    cx = clean_lines(xl, xh, S, tol)
    cy = clean_lines(yl, yh, S, tol)
    vstrips = [(0.0, 0.0, np.zeros(n, bool))]
    for a in range(len(cx)):
        for b in range(a + 1, len(cx)):
            inside = (xl >= cx[a] - tol) & (xh <= cx[b] + tol)
            vstrips.append((cx[a], cx[b], inside))
    hstrips = [(0.0, 0.0, np.zeros(n, bool))]
    for a in range(len(cy)):
        for b in range(a + 1, len(cy)):
            inside = (yl >= cy[a] - tol) & (yh <= cy[b] + tol)
            hstrips.append((cy[a], cy[b], inside))
    best = {}
    for (c1, c2, vi) in vstrips:
        wv = c2 - c1
        for (d1, d2, hi_) in hstrips:
            wh = d2 - d1
            w = min(wv, wh)
            if w <= tol:
                continue
            m = int(n - np.count_nonzero(vi | hi_))
            if m <= 0:
                continue
            side = S - w
            if m not in best or side < best[m][0] - 1e-12:
                best[m] = (side, (c1, c2, d1, d2))
    return best, len(cx), len(cy)


def main():
    R = load_records()
    N = max(R)
    rec = {n: float(F(R[n]["upper"])) for n in R}
    hits = []
    # (a) monotonicity
    for n in range(1, N):
        if rec[n] > rec[n + 1] + 1e-12:
            hits.append(("monotone", n, rec[n + 1], rec[n], f"delete a square from the n={n+1} record"))
    # (b) L-extension (iterated automatically because we scan all n)
    for n in range(1, N + 1):
        k = math.floor(rec[n] + 1e-12)
        m = n + 2 * k + 1
        if m <= N and rec[m] > rec[n] + 1 + 1e-12:
            hits.append(("L-extension", m, rec[n] + 1, rec[m], f"add an L to the n={n} record"))
    # (c) strip surgery on witnesses
    W = json.load(open(os.path.join(RUN, "work", "witness_float.json")))
    nclean = {}
    for key, w in W.items():
        n = int(key)
        S = w["side"]
        x, y, th = np.array(w["x"]), np.array(w["y"]), np.array(w["th"])
        best, ncx, ncy = surgery(n, S, x, y, th)
        nclean[n] = (ncx, ncy)
        for m, (side, strips) in best.items():
            # best table value reachable for m squares, or for any count below m (monotone), is rec[m]
            for mm in range(m, 0, -1):
                if R[mm]["proven_optimal"]:
                    break
                if side < rec[mm] - 1e-9:
                    hits.append(("surgery", mm, side, rec[mm],
                                 f"from n={n} record (S={S:.9f}) remove strips x[{strips[0]:.6f},{strips[1]:.6f}] "
                                 f"y[{strips[2]:.6f},{strips[3]:.6f}] leaving {m} squares"))
                else:
                    break
    hits.sort(key=lambda t: (t[1], t[2]))
    print(f"{len(hits)} closure hits")
    seen = set()
    for kind, n, new, old, desc in hits:
        tag = "" if n not in seen else "   (dup n)"
        seen.add(n)
        print(f"  {kind:11s} n={n:3d}: {new:.10f} < record {old:.10f}  (gain {old-new:.3e})  {desc}{tag}")
    json.dump([dict(kind=k, n=n, new=a, old=b, desc=d) for k, n, a, b, d in hits],
              open(os.path.join(RUN, "work", "closure_hits.json"), "w"), indent=1)
    # how many record packings have any interior clean line at all (informational)
    nontriv = [n for n in nclean if "." in R[n]["upper"]]
    print("non-trivial records with an interior clean vertical AND horizontal line:",
          sum(1 for n in nontriv if nclean[n][0] > 2 and nclean[n][1] > 2), "of", len(nontriv))


if __name__ == "__main__":
    main()
