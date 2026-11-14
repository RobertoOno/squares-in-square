#!/usr/bin/env python3
"""From-scratch global search: random start -> penalty continuation -> exact SLP polish,
wrapped in basin hopping. No published coordinates are read here (phase 2 calibration uses
this file only; the only table value used is an optional stopping threshold).

Usage: python3 gsearch.py N --time SECONDS --procs P --out work/calib [--target S] [--seed K]
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from opt import penalty_min, polish  # noqa: E402
from sqgeom import max_violation, normalize  # noqa: E402


def random_init(n, S0, rng, p_axis):
    x = rng.uniform(0.5, S0 - 0.5, n)
    y = rng.uniform(0.5, S0 - 0.5, n)
    th = np.where(rng.random(n) < p_axis, 0.0, rng.uniform(-np.pi / 4, np.pi / 4, n))
    return x, y, th


def descend(x, y, th, S, mus=(2.0, 20.0, 200.0, 2000.0), maxiter=1500):
    for mu in mus:
        x, y, th, S, E = penalty_min(x, y, th, S, mu, maxiter=maxiter)
    return x, y, th, S


def local_opt(x, y, th, S, mus=(2.0, 20.0, 200.0, 2000.0)):
    x, y, th, S = descend(x, y, th, S, mus)
    x, y, th, S, V, info = polish(x, y, th, S=S + 1e-3, delta=0.03)
    if V > 1e-10:
        return None
    return x, y, th, S


def perturb(x, y, th, S, rng):
    n = len(x)
    x = x.copy(); y = y.copy(); th = th.copy()
    r = rng.random()
    if r < 0.35:        # re-seat a few squares at random places
        k = int(rng.integers(1, 4))
        idx = rng.choice(n, k, replace=False)
        x[idx] = rng.uniform(0.5, S - 0.5, k)
        y[idx] = rng.uniform(0.5, S - 0.5, k)
        th[idx] = rng.uniform(-np.pi / 4, np.pi / 4, k)
    elif r < 0.7:       # jiggle everything
        sig = rng.choice([0.03, 0.08, 0.2])
        x += rng.normal(0, sig, n); y += rng.normal(0, sig, n); th += rng.normal(0, sig, n)
    elif r < 0.85:      # shake a local cluster
        c = int(rng.integers(n))
        d2 = (x - x[c]) ** 2 + (y - y[c]) ** 2
        idx = np.argsort(d2)[: int(rng.integers(3, 8))]
        x[idx] += rng.normal(0, 0.3, len(idx)); y[idx] += rng.normal(0, 0.3, len(idx))
        th[idx] = rng.uniform(-np.pi / 4, np.pi / 4, len(idx))
    else:               # straighten or randomise angles of a few squares
        k = int(rng.integers(1, 5))
        idx = rng.choice(n, k, replace=False)
        th[idx] = 0.0 if rng.random() < 0.5 else rng.uniform(-np.pi / 4, np.pi / 4, k)
    return x, y, th


def worker(args):
    n, seed, tlimit, outdir, target, hop_iters, S_guess = args
    rng = np.random.default_rng(seed)
    t0 = time.time()
    best = None
    nruns = 0
    nloc = 0
    log = []
    while time.time() - t0 < tlimit:
        nruns += 1
        S0 = S_guess * rng.uniform(1.05, 1.35)
        x, y, th = random_init(n, S0, rng, rng.choice([0.0, 0.3, 0.6, 0.85]))
        cur = local_opt(x, y, th, S0)
        nloc += 1
        if cur is None:
            continue
        # basin hopping from this start
        temp = 0.01
        stale = 0
        for h in range(hop_iters):
            if time.time() - t0 > tlimit:
                break
            px, py, pt = perturb(cur[0], cur[1], cur[2], cur[3], rng)
            cand = local_opt(px, py, pt, cur[3] * 1.02, mus=(20.0, 200.0, 2000.0))
            nloc += 1
            if cand is None:
                continue
            dS = cand[3] - cur[3]
            if dS < -1e-9:
                cur = cand; stale = 0
            else:
                stale += 1
                if dS < 1e-9 or rng.random() < math.exp(-dS / temp):
                    cur = cand
            if best is None or cur[3] < best[3] - 1e-10:
                best = cur
                log.append((time.time() - t0, nruns, nloc, best[3]))
                json.dump(dict(n=n, S=best[3], x=best[0].tolist(), y=best[1].tolist(), th=best[2].tolist(),
                               seed=seed, t=time.time() - t0, nloc=nloc),
                          open(os.path.join(outdir, f"n{n}_seed{seed}.json"), "w"))
                if target is not None and best[3] <= target:
                    return dict(seed=seed, S=best[3], t=time.time() - t0, nruns=nruns, nloc=nloc, hit=True, log=log)
            if stale > hop_iters // 3:
                break
    return dict(seed=seed, S=(best[3] if best else None), t=time.time() - t0, nruns=nruns, nloc=nloc, hit=False, log=log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--time", type=float, default=60)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "work", "calib"))
    ap.add_argument("--target", type=float, default=None, help="stop a worker when S <= target")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hops", type=int, default=60)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    k = math.isqrt(a.n - 1) + 1
    S_guess = float(k)          # trivial bound ceil(sqrt(n)) as a scale only
    jobs = [(a.n, a.seed * 1000 + i, a.time, a.out, a.target, a.hops, S_guess) for i in range(a.procs)]
    t0 = time.time()
    with mp.Pool(a.procs) as pool:
        res = pool.map(worker, jobs)
    res.sort(key=lambda r: (r["S"] is None, r["S"]))
    for r in res:
        print(f"seed {r['seed']}: S={r['S']} t={r['t']:.1f}s runs={r['nruns']} locals={r['nloc']} hit={r['hit']}")
    print("best", res[0]["S"], "wall %.1fs" % (time.time() - t0))
    json.dump(res, open(os.path.join(a.out, f"n{a.n}_summary_seed{a.seed}.json"), "w"))


if __name__ == "__main__":
    main()
