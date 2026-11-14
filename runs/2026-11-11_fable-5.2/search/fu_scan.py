#!/usr/bin/env python3
"""Follow-up: random scan of two-block layouts (fu_pinwheel) for one K; keeps the best counts.

  fu_scan.py K [--evals N] [--seed s] [--eps 1e-3] [--topo pin|L|any] [--out file.json]

One process; each evaluation is one exact refill (a small MILP).
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fu_pinwheel as fp  # noqa: E402

OPP = {"left": "right", "right": "left", "bottom": "top", "top": "bottom"}


def sample(K, S, rng, topo):
    """Two blocks: one against a vertical wall, one against a horizontal wall."""
    b0 = math.sqrt(2 * K)
    bs = [b for b in range(max(3, int(b0) - 2), int(b0) + 3)]
    blocks = []
    for kind in ("V", "H"):
        b = int(rng.choice(bs))
        bd = fp.Band(b, K - S)
        if topo == "L":
            wall = "right" if kind == "V" else "top"
        elif topo == "pin":
            wall = "left" if kind == "V" else "bottom"
        else:
            wall = str(rng.choice(["left", "right"] if kind == "V" else ["bottom", "top"]))
        Rmax = int((S - bd.h) / bd.sec) + 1
        R = int(rng.integers(max(2, Rmax // 3), Rmax + 1))
        free = S - ((R - 1) * bd.sec + bd.h)
        mode = rng.integers(0, 4)
        if mode == 0:
            lift = 0.0
        elif mode == 1:
            lift = free
        else:
            lift = float(rng.uniform(0, max(free, 0)))
        blocks.append(dict(wall=wall, b=b, R=R, lift=lift, flip=bool(rng.integers(0, 2))))
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("K", type=int)
    ap.add_argument("--evals", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--topo", default="any")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    K = a.K; S = K - a.eps
    rng = np.random.default_rng(a.seed)
    best = []
    t0 = time.time(); done = 0; tried = 0
    while done < a.evals:
        blocks = sample(K, S, rng, a.topo)
        tried += 1
        if not fp.tilted_ok(S, blocks, K=K):
            continue
        n, x, y, th, nt, st = fp.assemble(S, blocks, K=K, time_limit=10.0)
        done += 1
        best.append((n, nt, st, blocks))
        best.sort(key=lambda r: -r[0])
        best = best[:25]
        if done % 250 == 0:
            print(f"  {done} evals ({tried} tried) {time.time()-t0:.0f}s best deficit {K*K-best[0][0]}", flush=True)
    print(f"K={K} eps={a.eps} topo={a.topo}: {done} evaluations in {time.time()-t0:.0f}s")
    for n, nt, st, blocks in best[:8]:
        d = "; ".join(f"{b['wall']} b={b['b']} R={b['R']} lift={b['lift']:.3f} flip={int(b['flip'])}" for b in blocks)
        print(f"  n={n} deficit {K*K-n} tilted {nt} [{st}]  {d}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.join(RUN, a.out)), exist_ok=True)
        json.dump([dict(n=int(n), nt=int(nt), status=st, blocks=bl) for n, nt, st, bl in best], open(os.path.join(RUN, a.out), "w"))


if __name__ == "__main__":
    main()
