#!/usr/bin/env python3
"""Rotated-lattice region seeds ("RLR").

Many good packings consist of (i) a polyomino of equally tilted squares that all sit on ONE
lattice rotated by theta, and (ii) axis-aligned squares on integer grids anchored at the
container corners. This module enumerates such arrangements from first principles:

  tilted cells  = cells of the lattice rotated by theta (offset ox, oy) whose centres lie in a
                  region (a strip around the main diagonal, or a rotated rectangle) and that fit
                  inside the container;
  straight cells = greedy fill of the four corner-anchored unit grids (blockseed.fill);

then drops surplus straight cells so that exactly n remain and compresses the seed with the exact
SLP polish (the polish may move and rotate every square, so the lattice is only a starting
topology). No published coordinates are used.

  latseed.py scan N --kind band|rect|both [--procs P] [--limit M] [--s0 0.02 0.06 0.12]
"""
import argparse
import itertools
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import attack  # noqa: E402
from blockseed import fill  # noqa: E402
from opt import polish  # noqa: E402

R2 = math.sqrt(2.0)


def lattice_cells(S, theta, ox, oy, region):
    """Centres of rotated-lattice cells inside `region` and fully inside [0,S]^2."""
    c, s = math.cos(theta), math.sin(theta)
    h = 0.5 * (abs(c) + abs(s))
    K = int(S * 1.5) + 3
    I, J = np.meshgrid(np.arange(-K, K + 1), np.arange(-K, K + 1), indexing="ij")
    I = I.ravel().astype(float); J = J.ravel().astype(float)
    x = S / 2 + ox + I * c - J * s
    y = S / 2 + oy + I * s + J * c
    ok = (x - h >= -1e-9) & (x + h <= S + 1e-9) & (y - h >= -1e-9) & (y + h <= S + 1e-9)
    x = x[ok]; y = y[ok]
    kind = region[0]
    if kind == "band":           # strip around the main diagonal: |perp - off| <= hw, along in [-L/2+sh, L/2+sh]
        _, hw, off, L, sh = region
        perp = (y - x) / R2 - off
        along = (x + y - S) / R2 - sh
        m = (np.abs(perp) <= hw) & (np.abs(along) <= L / 2)
    elif kind == "rect":         # rectangle aligned with the lattice, centre offset (rx, ry), half sizes (A, B)
        _, A, B, rx, ry = region
        dx = x - (S / 2 + rx); dy = y - (S / 2 + ry)
        u = dx * c + dy * s; v = -dx * s + dy * c
        m = (np.abs(u) <= A) & (np.abs(v) <= B)
    else:
        raise ValueError(kind)
    return x[m], y[m]


def make_seed(n, S0, theta, ox, oy, region, drop_mode, rng):
    tx, ty = lattice_cells(S0, theta, ox, oy, region)
    nt = len(tx)
    if nt == 0 or nt > n:
        return None
    tt = np.full(nt, theta)
    ax, ay = fill(S0, tx, ty, tt, 0.0, 0)
    N = nt + len(ax)
    if N < n:
        return None
    if N > n:
        extra = N - n
        if extra > 6:
            return None
        if drop_mode == 0:            # drop the last accepted (they touch the tilted region)
            keep = np.ones(len(ax), bool); keep[len(ax) - extra:] = False
        else:                         # drop random straight cells among the last third
            pool = np.arange(max(0, len(ax) - max(extra * 6, len(ax) // 3)), len(ax))
            drop = rng.choice(pool, extra, replace=False)
            keep = np.ones(len(ax), bool); keep[drop] = False
        ax = ax[keep]; ay = ay[keep]
    x = np.concatenate([tx, ax]); y = np.concatenate([ty, ay]); th = np.concatenate([tt, np.zeros(len(ax))])
    return x, y, th, nt, N


def _task(args):
    n, S0, theta, ox, oy, region, drop_mode, seed = args
    rng = np.random.default_rng(seed)
    sd = make_seed(n, S0, theta, ox, oy, region, drop_mode, rng)
    if sd is None:
        return None
    x, y, th, nt, N = sd
    try:
        r = polish(x, y, th, S=S0, delta=0.03)
    except Exception:  # noqa: BLE001
        return None
    if r[4] > 1e-10:
        return None
    return dict(n=n, S=float(r[3]), S0=S0, theta=theta, ox=ox, oy=oy, region=list(region), drop=drop_mode, nt=nt, N=N,
                x=r[0].tolist(), y=r[1].tolist(), th=r[2].tolist())


def param_grid(kind, record, rng, limit):
    k = int(math.floor(record + 1e-9))
    thetas = [math.radians(d) for d in range(14, 46, 2)]
    P = []
    if kind in ("band", "both"):
        for th in thetas:
            for sgn in (1, -1):
                for hw in (0.55, 0.8, 1.05, 1.3, 1.55, 1.8, 2.05, 2.55, 3.05):
                    for off in (-0.3, -0.15, 0.0, 0.15, 0.3):
                        for L in (record * R2 * f for f in (1.0, 0.92, 0.84, 0.76, 0.66, 0.5)):
                            for sh in (0.0,):
                                for ox in (0.0, 0.25, 0.5, 0.75):
                                    for oy in (0.0, 0.25, 0.5, 0.75):
                                        P.append((sgn * th, ox, oy, ("band", hw, off, L, sh)))
    if kind in ("rect", "both"):
        for th in thetas:
            for sgn in (1, -1):
                for A in np.arange(1.0, k * 0.55, 0.5):
                    for B in np.arange(1.0, A + 0.01, 0.5):
                        for (rx, ry) in ((0, 0), (0.6, 0.6), (-0.6, 0.6), (1.5, 1.5), (-1.5, 1.5), (0, 1.2), (1.2, 0), (2.5, 2.5), (-2.5, 2.5)):
                            for ox in (0.0, 0.33, 0.67):
                                for oy in (0.0, 0.33, 0.67):
                                    P.append((sgn * th, ox, oy, ("rect", float(A), float(B), float(rx), float(ry))))
    rng.shuffle(P)
    return P[:limit] if limit else P


def cmd_scan(a):
    n = a.n
    record = attack.rec(n)
    rng = np.random.default_rng(a.seed)
    P = param_grid(a.kind, record, rng, a.limit)
    tasks = []
    for i, (th, ox, oy, region) in enumerate(P):
        for ds in a.s0:
            for dm in (0, 1):
                tasks.append((n, record + ds, th, ox, oy, region, dm, a.seed * 1000003 + len(tasks)))
    print(f"n={n} record={record:.9f}: {len(tasks)} seeds ({a.kind})", flush=True)
    t0 = time.time()
    best = []
    npol = 0
    outdir = os.path.join(RUN, "work", "latscan")
    os.makedirs(outdir, exist_ok=True)
    bestS = 1e9
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(_task, tasks, chunksize=16):
            if r is None:
                continue
            npol += 1
            if r["S"] < bestS - 1e-9:
                bestS = r["S"]
                reg = r["region"]
                print(f"[{time.time()-t0:6.0f}s] n={n} S={r['S']:.9f} (record {record:.9f}, diff {r['S']-record:+.6f}) theta={math.degrees(r['theta']):.0f} "
                      f"region={reg[0]} {[round(v,2) for v in reg[1:]]} off=({r['ox']},{r['oy']}) S0=+{r['S0']-record:.2f} tilted={r['nt']} seedN={r['N']}"
                      + ("  <<< BELOW RECORD" if r["S"] < record - 1e-9 else ""), flush=True)
                json.dump(r, open(os.path.join(outdir, f"n{n}_{a.kind}_best.json"), "w"))
                if r["S"] < record - 1e-9:
                    attack.save_cand(n, r["S"], r["x"], r["y"], r["th"], f"latscan_{a.kind}", extra=dict(theta=r["theta"], region=reg))
            best.append((r["S"], r["nt"], round(math.degrees(r["theta"])), r["region"][0]))
    best.sort()
    print(f"n={n} done: {npol} seeds reached n and were polished; best {bestS if npol else None}; record {record:.9f}; wall {time.time()-t0:.0f}s", flush=True)
    print("  top:", [(round(b[0], 6), b[1], b[2], b[3]) for b in best[:8]], flush=True)
    attack.log_attempt(n, f"latscan[{a.kind}]: tilted squares on one rotated lattice inside a diagonal band / rotated rectangle, greedy "
                          "corner-anchored axis-aligned fill, exact SLP compression (search/latseed.py scan)",
                       bestS if npol else None, None, time.time() - t0,
                       f"{len(tasks)} seeds enumerated, {npol} held >= n squares and were polished; record {record:.9f}; "
                       + ("BELOW RECORD, see work/cand" if npol and bestS < record - 1e-9 else "no improvement"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("n", type=int)
    p.add_argument("--kind", default="band")
    p.add_argument("--procs", type=int, default=8)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--s0", type=float, nargs="+", default=[0.03, 0.08, 0.15])
    p.set_defaults(f=cmd_scan)
    a = ap.parse_args()
    a.f(a)
