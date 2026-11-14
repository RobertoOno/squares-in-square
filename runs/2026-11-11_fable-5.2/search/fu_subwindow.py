#!/usr/bin/env python3
"""Follow-up (after the run): corner-anchored sub-window closure.

For every public packing in the local mirror and each of its four corners, keep the squares whose
bounding boxes lie inside a smaller square window anchored at that corner. The N squares nearest the
corner (by the window side they need) form a valid packing of N squares in a window of that side, so
every source gives an upper bound for every N below its own count. The bounds are compared with the
Kaggle per-puzzle table (N <= 1000) and, above 1000, with the trivial grid and with the best public
packing seen for that N.

Light: one process, numpy only.  Usage: fu_subwindow.py [--bars work/web/kaggle_perpuzzle/per_puzzle_v31.tsv]
"""
import argparse
import glob
import json
import math
import os
import sys
import time
from fractions import Fraction as F

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import diagper  # noqa: E402


def sources():
    pats = ["work/remote/A/work/bigcerts/*.cert", "work/remote/A/work/smallcerts/*.cert", "work/remote/A/work/couzo/*.cert",
            "work/remote/A/work/ext/**/*.cert", "work/remote/A/work/ext/**/*.npz", "work/remote/B/work/hugecerts/*.cert",
            "work/remote/B/work/morecerts/*.cert", "work/remote/B/work/evand/**/*.cert"]
    seen, out = set(), []
    for p in pats:
        for f in sorted(glob.glob(os.path.join(RUN, p), recursive=True)):
            key = os.path.basename(f)
            if key in seen:
                continue
            seen.add(key)
            out.append(("npz:" if f.endswith(".npz") else "cert:") + f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", default="work/web/kaggle_perpuzzle/per_puzzle_v31.tsv")
    ap.add_argument("--out", default="work/followup/subwindow_hits.json")
    a = ap.parse_args()
    bar = {}
    with open(os.path.join(RUN, a.bars), encoding="utf-8") as f:
        next(f)
        for line in f:
            n, L, team, date = line.rstrip("\n").split("\t")
            bar[int(n)] = float(F(L))
    srcs = sources()
    print(f"{len(srcs)} sources", flush=True)
    best = {}                      # N -> (side, label, corner)
    pub = {}                       # n -> best public side among the sources themselves
    t0 = time.time()
    bad = 0
    for k, lab in enumerate(srcs):
        try:
            S, x, y, th = diagper.source(lab)
        except Exception:  # noqa: BLE001
            bad += 1
            continue
        diagper._SRC_CACHE.clear()
        n = len(x)
        if n < 5:
            continue
        if n not in pub or S < pub[n][0]:
            pub[n] = (float(S), os.path.basename(lab))
        h = 0.5 * (np.abs(np.cos(th)) + np.abs(np.sin(th)))
        for c, (ux, uy) in enumerate(((x + h, y + h), (S - x + h, y + h), (x + h, S - y + h), (S - x + h, S - y + h))):
            w = np.sort(np.maximum(ux, uy))
            for N in range(5, n):
                if N not in best or w[N - 1] < best[N][0]:
                    best[N] = (float(w[N - 1]), os.path.basename(lab), c)
        if k % 500 == 0:
            print(f"  {k}/{len(srcs)} {time.time()-t0:.0f}s", flush=True)
    hits = []
    for N in sorted(best):
        side, lab, c = best[N]
        grid = math.ceil(math.sqrt(N) - 1e-12)
        if N <= 1000:
            ref, kind = bar[N], "kaggle"
        else:
            ref, kind = min(grid, pub.get(N, (grid,))[0]), "public/grid"
        if side < ref - 1e-9:
            hits.append(dict(N=N, side=side, ref=ref, kind=kind, gain=ref - side, source=lab, corner=c))
    os.makedirs(os.path.dirname(os.path.join(RUN, a.out)), exist_ok=True)
    json.dump(dict(hits=hits, pub={str(k): v for k, v in pub.items()}), open(os.path.join(RUN, a.out), "w"))
    le = [h for h in hits if h["N"] <= 1000]
    gt = [h for h in hits if h["N"] > 1000]
    print(f"done in {time.time()-t0:.0f}s; unreadable sources {bad}; largest public n {max(pub)}; public counts above 1000: {sum(1 for n in pub if n > 1000)}")
    print(f"hits against the Kaggle table (N <= 1000): {len(le)}")
    for h in le[:40]:
        print(f"  N={h['N']} side {h['side']:.6f} < {h['ref']:.6f} by {h['gain']:.2e}  from {h['source']} corner {h['corner']}")
    print(f"hits above 1000 against grid/public: {len(gt)}")
    for h in sorted(gt, key=lambda h: -h["gain"])[:25]:
        print(f"  N={h['N']} side {h['side']:.6f} < {h['ref']:.6f} by {h['gain']:.2e}  from {h['source']} corner {h['corner']}")


if __name__ == "__main__":
    main()
