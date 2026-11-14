#!/usr/bin/env python3
"""Simulated annealing at a fixed container side S with a soft overlap energy (numba),
finished by L-BFGS at fixed S and the exact SLP polish (which then lowers S as far as the
arrangement allows).

  E = sum_pairs depth^2 + sum_walls violation^2,  single-square moves (dx, dy, dtheta),
  Metropolis acceptance, geometric cooling, adaptive step.

Usage
  sa.py scratch N --S target_side [--time SEC] [--procs P] [--sweeps K]   random starts (calibration / attack)
  sa.py seed N seedfile --S target_side ...                               start from a packing JSON
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from opt import penalty_min, polish  # noqa: E402
from sqgeom import max_violation, normalize  # noqa: E402


@njit(cache=True)
def _e_one(i, xi, yi, ci, si, x, y, c, s, S):
    """Energy of square i at (xi, yi, cos, sin) against walls and all other squares."""
    n = x.shape[0]
    h = 0.5 * (abs(ci) + abs(si))
    e = 0.0
    v = h - xi
    if v > 0:
        e += v * v
    v = xi + h - S
    if v > 0:
        e += v * v
    v = h - yi
    if v > 0:
        e += v * v
    v = yi + h - S
    if v > 0:
        e += v * v
    for j in range(n):
        if j == i:
            continue
        dx = x[j] - xi
        if dx >= 1.4142135623730951 or dx <= -1.4142135623730951:
            continue
        dy = y[j] - yi
        if dx * dx + dy * dy >= 2.0:
            continue
        cj = c[j]; sj = s[j]
        cd = cj * ci + sj * si
        sd = sj * ci - cj * si
        R = 0.5 * (1.0 + abs(cd) + abs(sd))
        best = abs(dx * ci + dy * si)
        a = abs(-dx * si + dy * ci)
        if a > best:
            best = a
        a = abs(dx * cj + dy * sj)
        if a > best:
            best = a
        a = abs(-dx * sj + dy * cj)
        if a > best:
            best = a
        dep = R - best
        if dep > 0:
            e += dep * dep
    return e


@njit(cache=True)
def sa_run(x, y, th, S, T0, T1, nsweeps, seed, step0, p_jump, stop_E):
    """In-place SA. Returns (final E, sweeps done, best E seen)."""
    np.random.seed(seed)
    n = x.shape[0]
    c = np.cos(th); s = np.sin(th)
    E = 0.0
    for i in range(n):
        E += _e_one(i, x[i], y[i], c[i], s[i], x, y, c, s, S)
    # pair terms counted twice, walls once: recompute properly
    Ew = 0.0
    for i in range(n):
        h = 0.5 * (abs(c[i]) + abs(s[i]))
        for v in (h - x[i], x[i] + h - S, h - y[i], y[i] + h - S):
            if v > 0:
                Ew += v * v
    E = (E - Ew) * 0.5 + Ew
    step = step0
    bestE = E
    ratio = (T1 / T0) ** (1.0 / max(1, nsweeps - 1))
    T = T0
    sw = 0
    for sw in range(nsweeps):
        acc = 0
        for m in range(n):
            i = np.random.randint(n)
            eo = _e_one(i, x[i], y[i], c[i], s[i], x, y, c, s, S)
            if np.random.random() < p_jump:
                xn = 0.5 + (S - 1.0) * np.random.random()
                yn = 0.5 + (S - 1.0) * np.random.random()
                tn = (np.random.random() - 0.5) * 1.5707963267948966
            else:
                xn = x[i] + step * (2.0 * np.random.random() - 1.0)
                yn = y[i] + step * (2.0 * np.random.random() - 1.0)
                tn = th[i] + 1.5 * step * (2.0 * np.random.random() - 1.0)
            cn = math.cos(tn); sn = math.sin(tn)
            en = _e_one(i, xn, yn, cn, sn, x, y, c, s, S)
            dE = en - eo
            if dE <= 0.0 or np.random.random() < math.exp(-dE / T):
                x[i] = xn; y[i] = yn; th[i] = tn; c[i] = cn; s[i] = sn
                E += dE
                acc += 1
        r = acc / n
        if r > 0.45:
            step = min(step * 1.04, 0.5)
        elif r < 0.30:
            step = max(step * 0.96, 1e-6)
        if E < bestE:
            bestE = E
        if E < stop_E:
            break
        T *= ratio
    return E, sw + 1, bestE


def finish(x, y, th, S, e_gate=1e-5):
    """L-BFGS at fixed S, then (if nearly feasible) exact polish with S free. Returns (S_final or None, x, y, th, E)."""
    x, y, th, _, E = penalty_min(x, y, th, S, 1.0, opt_S=False, maxiter=4000)
    if E > e_gate:
        return None, x, y, th, E
    xp, yp, tp, Sp, V, info = polish(x, y, th, S=S + 1e-4, delta=0.01)
    if V > 1e-10:
        return None, x, y, th, E
    return Sp, xp, yp, tp, E


def _worker(args):
    (n, S, seed, tlimit, sweeps, T0, T1, seedfile, outdir, tag, p_jump, jitter) = args
    rng = np.random.default_rng(seed)
    t0 = time.time()
    best = None
    runs = 0
    Es = []
    while time.time() - t0 < tlimit:
        runs += 1
        if seedfile:
            d = json.load(open(seedfile))
            x = np.array(d["x"], float); y = np.array(d["y"], float); th = np.array(d["th"], float)
            # rescale the seed into the target container and jitter
            S_seed = float(d["S"])
            x = x * (S / S_seed); y = y * (S / S_seed)
            x += rng.normal(0, jitter, n); y += rng.normal(0, jitter, n); th += rng.normal(0, jitter, n)
        else:
            x = rng.uniform(0.5, S - 0.5, n); y = rng.uniform(0.5, S - 0.5, n)
            th = rng.uniform(-np.pi / 4, np.pi / 4, n)
        E, sw, bE = sa_run(x, y, th, S, T0, T1, sweeps, int(rng.integers(1 << 30)), 0.1, p_jump, 1e-9)
        Sf, xf, yf, tf, Ef = finish(x, y, th, S)
        Es.append(Ef)
        if Sf is not None and (best is None or Sf < best[0]):
            best = (Sf, xf, yf, tf)
            json.dump(dict(n=n, S=Sf, x=xf.tolist(), y=yf.tolist(), th=tf.tolist(), seed=seed, t=time.time() - t0, runs=runs,
                           target_S=S, tag=tag),
                      open(os.path.join(outdir, f"n{n}_{tag}_seed{seed}.json"), "w"))
    return dict(seed=seed, best=(best[0] if best else None), runs=runs, t=time.time() - t0,
                minE=(min(Es) if Es else None), medE=(float(np.median(Es)) if Es else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["scratch", "seed"])
    ap.add_argument("n", type=int)
    ap.add_argument("seedfile", nargs="?")
    ap.add_argument("--S", type=float, required=True)
    ap.add_argument("--time", type=float, default=120)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--sweeps", type=int, default=100000)
    ap.add_argument("--T0", type=float, default=0.02)
    ap.add_argument("--T1", type=float, default=1e-8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pjump", type=float, default=0.0)
    ap.add_argument("--jitter", type=float, default=0.0)
    ap.add_argument("--out", default=os.path.join(RUN, "work", "sa"))
    ap.add_argument("--tag", default="sa")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    jobs = [(a.n, a.S, a.seed * 1000 + i, a.time, a.sweeps, a.T0, a.T1, a.seedfile if a.mode == "seed" else None,
             a.out, a.tag, a.pjump, a.jitter) for i in range(a.procs)]
    t0 = time.time()
    with mp.Pool(a.procs) as pool:
        res = pool.map(_worker, jobs)
    res.sort(key=lambda r: (r["best"] is None, r["best"]))
    for r in res:
        print(f"seed {r['seed']}: best S={r['best']} runs={r['runs']} minE={r['minE']} medE={r['medE']} t={r['t']:.0f}s")
    b = [r["best"] for r in res if r["best"] is not None]
    print(f"n={a.n} target S={a.S} best={min(b) if b else None} total runs={sum(r['runs'] for r in res)} wall={time.time()-t0:.0f}s")
    json.dump(res, open(os.path.join(a.out, f"n{a.n}_{a.tag}_summary_seed{a.seed}.json"), "w"))


if __name__ == "__main__":
    main()
