#!/usr/bin/env python3
"""Structured seeds: one or two rectangular blocks of equally tilted squares, the rest of the
container filled greedily with axis-aligned unit cells on the four corner-anchored integer grids.
The seed is then compressed (penalty continuation + exact SLP polish).

This is a from-first-principles construction family (no published coordinates are read), used in
phase 3 to look for arrangements that the published records do not use.

Usage:
  blockseed.py scan N [--procs P] [--top T] [--two]      scan the family for n = N
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
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sqgeom import pair_sep  # noqa: E402
import attack  # noqa: E402


def block(a, b, theta, cx, cy):
    """a x b squares, rows along e1 = (cos, sin); centre of the block at (cx, cy)."""
    c, s = math.cos(theta), math.sin(theta)
    xs, ys = [], []
    for i in range(a):
        for j in range(b):
            u = i - (a - 1) / 2.0
            v = j - (b - 1) / 2.0
            xs.append(cx + u * c - v * s)
            ys.append(cy + u * s + v * c)
    return np.array(xs), np.array(ys), np.full(a * b, theta)


@njit(cache=True)
def fill(S, tx, ty, tth, eps, order_mode, qmask=15):
    """Greedy corner-anchored fill. Returns arrays of accepted cell centres.
    A cell is accepted if it overlaps no tilted square by more than eps (penetration depth)
    and no accepted cell by more than eps."""
    K = int(math.floor(S + 1e-9))
    nt = tx.shape[0]
    # tilted squares must be inside the container
    ncand = 4 * K * K
    cxs = np.empty(ncand); cys = np.empty(ncand); key = np.empty(ncand)
    m = 0
    for q in range(4):
        if not ((qmask >> q) & 1):       # corner grids: bit0 bottom-left, bit1 bottom-right, bit2 top-left, bit3 top-right
            continue
        for i in range(K):
            for j in range(K):
                x = i + 0.5 if (q == 0 or q == 2) else S - i - 0.5
                y = j + 0.5 if (q == 0 or q == 1) else S - j - 0.5
                cxs[m] = x; cys[m] = y
                if order_mode == 0:
                    key[m] = max(i, j) + 1e-3 * (i + j) + 1e-6 * q
                elif order_mode == 1:
                    key[m] = (i + j) + 1e-3 * max(i, j) + 1e-6 * q
                else:
                    key[m] = math.sqrt(i * i + j * j) + 1e-6 * q
                m += 1
    order = np.argsort(key[:m])
    ax = np.empty(ncand); ay = np.empty(ncand)
    na = 0
    for o in order:
        x = cxs[o]; y = cys[o]
        ok = True
        for t in range(nt):
            dx = tx[t] - x; dy = ty[t] - y
            if dx * dx + dy * dy >= 2.0:
                continue
            sep, k, sg = pair_sep(x, y, 0.0, tx[t], ty[t], tth[t])
            if sep < -eps:
                ok = False
                break
        if not ok:
            continue
        for t in range(na):
            if abs(ax[t] - x) < 1.0 - eps and abs(ay[t] - y) < 1.0 - eps:
                ok = False
                break
        if ok:
            ax[na] = x; ay[na] = y; na += 1
    return ax[:na].copy(), ay[:na].copy()


def inside(S, tx, ty, tth, tol=1e-9):
    h = 0.5 * (np.abs(np.cos(tth)) + np.abs(np.sin(tth)))
    return bool(np.all(tx - h >= -tol) and np.all(tx + h <= S + tol) and np.all(ty - h >= -tol) and np.all(ty + h <= S + tol))


def blocks_disjoint(tx, ty, tth, eps=1e-9):
    n = len(tx)
    for i in range(n):
        for j in range(i + 1, n):
            if (tx[i] - tx[j]) ** 2 + (ty[i] - ty[j]) ** 2 < 2.0:
                sep, k, sg = pair_sep(tx[i], ty[i], tth[i], tx[j], ty[j], tth[j])
                if sep < -eps:
                    return False
    return True


def seed_count(S, blocks, eps, order_mode):
    """blocks: list of (a, b, theta, fx, fy) with centre = (fx*S, fy*S). Returns (count, x, y, th) or None."""
    txs, tys, tts = [], [], []
    for (a, b, th, fx, fy) in blocks:
        bx, by, bt = block(a, b, th, fx * S, fy * S)
        txs.append(bx); tys.append(by); tts.append(bt)
    tx = np.concatenate(txs); ty = np.concatenate(tys); tt = np.concatenate(tts)
    if not inside(S, tx, ty, tt):
        return None
    if len(blocks) > 1 and not blocks_disjoint(tx, ty, tt):
        return None
    ax, ay = fill(S, tx, ty, tt, eps, order_mode)
    x = np.concatenate([tx, ax]); y = np.concatenate([ty, ay]); th = np.concatenate([tt, np.zeros(len(ax))])
    return len(x), x, y, th


def _scan_task(args):
    n, blocks, eps, order_mode, S_hi, S_lo, dS = args
    # smallest S0 on the grid for which the seed holds at least n squares
    best = None
    S0 = S_hi
    while S0 >= S_lo - 1e-12:
        r = seed_count(S0, blocks, eps, order_mode)
        if r is not None and r[0] >= n:
            best = (S0, r)
        S0 -= dS
    if best is None:
        return None
    S0, (cnt, x, y, th) = best
    return (S0, cnt, blocks, eps, order_mode)


def _opt_task(args):
    n, S0, blocks, eps, order_mode, seed = args
    rng = np.random.default_rng(seed)
    r = seed_count(S0, blocks, eps, order_mode)
    if r is None:
        return None
    cnt, x, y, th = r
    nb = sum(a * b for a, b, *_ in blocks)
    # drop surplus axis-aligned cells (never the block squares): prefer the most-overlapping, else random
    if cnt > n:
        xa, ya, ta = attack.fix_count(x, y, th, S0, n, rng) if eps > 0 else (None, None, None)
        if xa is None:
            idx = np.arange(nb, cnt)
            drop = rng.choice(idx, cnt - n, replace=False)
            keep = np.ones(cnt, bool); keep[drop] = False
            xa, ya, ta = x[keep], y[keep], th[keep]
        x, y, th = xa, ya, ta
    t0 = time.time()
    try:
        res = attack.local_opt(x, y, th, S0 + 0.01, mus=((200.0, 2000.0, 20000.0) if eps > 0 else ()))
    except Exception:  # noqa: BLE001
        res = None
    if res is None:
        return None
    return dict(n=n, S=res[3], S0=S0, cnt=cnt, blocks=blocks, eps=eps, order=order_mode,
                x=res[0].tolist(), y=res[1].tolist(), th=res[2].tolist(), t=time.time() - t0)


THETAS = [math.pi / 4, math.radians(42.0), math.radians(40.0), math.atan(0.75), math.atan(2.0 / 3.0),
          math.radians(30.0), math.atan(0.5), math.radians(22.0), math.atan(1.0 / 3.0)]


def one_block_configs(n, k, offsets):
    cfgs = []
    for a in range(1, k + 3):
        for b in range(a, k + 6):
            if a * b > n * 0.75 or a * b < 2:
                continue
            for th in THETAS:
                for sgn in (1, -1):
                    if abs(th - math.pi / 4) < 1e-9 and sgn == -1 and a == b:
                        continue
                    for (fx, fy) in offsets:
                        cfgs.append([(a, b, sgn * th, fx, fy)])
    return cfgs


def cmd_scan(a):
    n = a.n
    record = attack.rec(n)
    k = int(math.floor(record + 1e-9))
    S_hi = record + a.above
    S_lo = record - a.below
    offs1 = [(0.5 + u, 0.5 + v) for u in (-0.04, -0.02, 0.0, 0.02, 0.04) for v in (-0.04, -0.02, 0.0, 0.02, 0.04)]
    offs1 += [(0.5 + u, 0.5 + v) for u in (-0.16, -0.08, 0.08, 0.16) for v in (-0.16, -0.08, 0.08, 0.16)]
    cfgs = one_block_configs(n, k, offs1)
    tasks = []
    for c in cfgs:
        for eps in a.eps:
            for om in (0, 1):
                tasks.append((n, c, eps, om, S_hi, S_lo, a.ds))
    print(f"n={n} record={record:.9f}: scanning {len(tasks)} one-block seeds, S0 in [{S_lo:.3f},{S_hi:.3f}]", flush=True)
    t0 = time.time()
    found = []
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(_scan_task, tasks, chunksize=64):
            if r is not None:
                found.append(r)
    found.sort(key=lambda r: (r[0], -r[1]))
    print(f"  {len(found)} seeds reach count >= {n} within the window ({time.time()-t0:.0f}s); best raw S0 = "
          f"{found[0][0] if found else None}", flush=True)
    top = found[: a.top]
    otasks = [(n, S0, blocks, eps, om, i) for i, (S0, cnt, blocks, eps, om) in enumerate(top)]
    results = []
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(_opt_task, otasks, chunksize=1):
            if r is not None:
                results.append(r)
    results.sort(key=lambda r: r["S"])
    outdir = os.path.join(RUN, "work", "blockscan")
    os.makedirs(outdir, exist_ok=True)
    for i, r in enumerate(results[:12]):
        b = r["blocks"][0]
        print(f"  #{i}: S={r['S']:.9f} (S0={r['S0']:.3f}, seed count {r['cnt']}) block {b[0]}x{b[1]} at {math.degrees(b[2]):.2f} deg "
              f"centre ({b[3]:.2f},{b[4]:.2f}) eps={r['eps']} order={r['order']}"
              + ("  <<< BELOW RECORD" if r["S"] < record - 1e-9 else ""), flush=True)
        if i < 5:
            json.dump(r, open(os.path.join(outdir, f"n{n}_rank{i}_S{r['S']:.8f}.json"), "w"))
        if r["S"] < record - 1e-9:
            attack.save_cand(n, r["S"], r["x"], r["y"], r["th"], f"blockscan_rank{i}", extra=dict(blocks=r["blocks"]))
    best = results[0]["S"] if results else None
    attack.log_attempt(n, "blockscan: one rectangular block of equally tilted squares + greedy corner-anchored axis-aligned fill, "
                          "penalty continuation + SLP polish (search/blockseed.py scan)",
                       best, None, time.time() - t0,
                       f"{len(tasks)} seeds scanned, {len(found)} reach count n in the S0 window, {len(results)} optimised; "
                       f"record {record:.9f}; " + ("BELOW RECORD, see work/cand" if best is not None and best < record - 1e-9 else "no improvement"))
    print(f"n={n} best {best} record {record:.9f} wall {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("n", type=int)
    p.add_argument("--procs", type=int, default=8)
    p.add_argument("--top", type=int, default=60)
    p.add_argument("--above", type=float, default=0.12)
    p.add_argument("--below", type=float, default=0.10)
    p.add_argument("--ds", type=float, default=0.01)
    p.add_argument("--eps", type=float, nargs="+", default=[0.0, 0.08])
    p.set_defaults(f=cmd_scan)
    a = ap.parse_args()
    a.f(a)
