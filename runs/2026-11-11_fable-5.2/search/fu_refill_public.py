#!/usr/bin/env python3
"""Follow-up: exact refill around the tilted cores of public packings near the grid crossover.

For each public packing with K^2 - n small, keep its tilted squares (the core), enlarge the container
to S' = K - eps and re-place the upright squares optimally (fu_pinwheel.refill), for several positions
of the core inside the slack. Reports the best count per source and any count above the Kaggle bar.
"""
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
import fu_pinwheel as fp  # noqa: E402


def load_bars(path):
    bar = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            n, L, team, date = line.rstrip("\n").split("\t")
            bar[int(n)] = float(F(L))
    return bar


def main():
    bars = load_bars(os.path.join(RUN, "work/web/kaggle_perpuzzle/per_puzzle_v31.tsv"))
    eps = float(sys.argv[1]) if len(sys.argv) > 1 else 1e-4
    tilt_min = math.radians(float(sys.argv[2])) if len(sys.argv) > 2 else math.radians(0.3)
    pats = ["work/remote/A/work/bigcerts/*.cert", "work/remote/A/work/smallcerts/*.cert", "work/remote/A/work/couzo/best__*.cert",
            "work/remote/A/work/ext/**/*.cert", "work/remote/A/work/ext/**/*.npz", "work/remote/B/work/hugecerts/*.cert",
            "work/remote/B/work/morecerts/*.cert", "work/remote/B/work/evand/**/*.cert"]
    files = []
    for p in pats:
        files += sorted(glob.glob(os.path.join(RUN, p), recursive=True))
    out = []
    t0 = time.time()
    seen = set()
    for f in files:
        lab = ("npz:" if f.endswith(".npz") else "cert:") + f
        try:
            S, x, y, th = diagper.source(lab)
        except Exception:  # noqa: BLE001
            continue
        diagper._SRC_CACHE.clear()
        n = len(x)
        K = int(math.ceil(S - 1e-9))
        m = K * K - n
        if n > 1000 or K < 9 or S > K - 1e-7 or m > 3.9 * math.sqrt(K) + 6:
            continue
        key = (n, round(S, 7))
        if key in seen:
            continue
        seen.add(key)
        t = (th + math.pi / 4) % (math.pi / 2) - math.pi / 4
        core = np.abs(t) > tilt_min
        tx, ty, tt = x[core], y[core], th[core]
        S2 = K - eps
        slack = S2 - S
        best = None
        shifts = sorted(set([0.0, slack / 2, slack]))
        for dx in shifts:
            for dy in shifts:
                ax, ay, st = fp.refill(S2, tx + dx, ty + dy, tt, K=K, time_limit=10.0)
                cnt = len(tx) + len(ax)
                if best is None or cnt > best[0]:
                    best = (cnt, dx, dy, st)
        # the same at the packing's own side, core in place
        ax0, ay0, st0 = fp.refill(S, tx, ty, tt, K=K, time_limit=10.0) if K - S < 0.5 else (np.zeros(0), np.zeros(0), "skip")
        own = len(tx) + len(ax0)
        rec = dict(n=n, K=K, S=S, deficit=m, core=int(core.sum()), own=own, best=best[0], shift=(best[1], best[2]), src=os.path.basename(f))
        out.append(rec)
        flag = ""
        if best[0] > n:
            # is there any count above n whose Kaggle bar is not below K - eps?
            newn = [q for q in range(n + 1, best[0] + 1) if q <= 1000 and bars[q] > S2]
            flag = "  <<< MORE THAN THE SOURCE" + (f"; beats the Kaggle bar at n={newn}" if newn else "")
        print(f"n={n} K={K} deficit {m} S={S:.5f} core {int(core.sum())}: refill at own side {own}; at K-eps {best[0]} ({best[3]}){flag}", flush=True)
    json.dump(out, open(os.path.join(RUN, "work/followup/refill_public.json"), "w"))
    print(f"{len(out)} packings in {time.time()-t0:.0f}s; sources where the refill exceeds the source count: {sum(1 for r in out if r['best'] > r['n'])}")


if __name__ == "__main__":
    main()
