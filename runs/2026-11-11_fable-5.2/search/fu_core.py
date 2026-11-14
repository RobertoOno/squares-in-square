#!/usr/bin/env python3
"""Follow-up: search over tilted cores with an exact refill of the upright squares.

State: the tilted squares of a packing (the core), parsed into blocks (stacks of bars) taken from a
public parent packing. Container side fixed at S = K - eps. Objective: number of squares after the
exact refill (fu_pinwheel.refill). Moves act on the core only: slide a block along its wall, insert
or remove a bar inside a block (the rest of the block moves by the bar pitch), lengthen or shorten a
bar by one square, drop a square. A layout with at least `target` squares at S < K is a packing of
`target` squares below the grid side.

  fu_core.py run LABEL [--target N] [--evals M] [--seed s] [--eps 1e-4] [--tilt 0.3] [--out DIR]

LABEL is a diagper source label (cert:path, npz:path, json:path). One process.
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
from sqgeom import max_violation  # noqa: E402


def norm_angle(th):
    return (th + math.pi / 4) % (math.pi / 2) - math.pi / 4


def split_core(x, y, th, tilt_deg):
    t = norm_angle(np.asarray(th, float))
    core = np.abs(t) > math.radians(tilt_deg)
    return np.asarray(x, float)[core].copy(), np.asarray(y, float)[core].copy(), t[core].copy()


def components(tx, ty, link=1.3):
    n = len(tx)
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i in range(n):
        d2 = (tx - tx[i]) ** 2 + (ty - ty[i]) ** 2
        for j in np.nonzero(d2 < link * link)[0]:
            if j > i:
                par[find(i)] = find(int(j))
    lab = np.array([find(i) for i in range(n)])
    return lab


class Block:
    """A cluster of tilted squares with a common orientation, seen as a stack of bars."""

    def __init__(self, idx, tx, ty, tt):
        self.idx = np.array(idx)
        a = float(np.median(tt[self.idx]))
        self.a = a
        u = np.array([math.cos(a), math.sin(a)])
        v = np.array([-math.sin(a), math.cos(a)])
        P = np.stack([tx[self.idx], ty[self.idx]], axis=1)
        # bars are the direction along which neighbours are in registry (offset exactly one side)
        reg = [0, 0]
        for k, d in enumerate((u, v)):
            for i in range(len(P)):
                dd = P - P[i] - d
                reg[k] += int(np.sum(np.hypot(dd[:, 0], dd[:, 1]) < 0.03))
        self.bar = u if reg[0] >= reg[1] else v
        self.nrm = v if reg[0] >= reg[1] else u
        ax = np.array([1.0, 0.0]) if abs(self.nrm[0]) > abs(self.nrm[1]) else np.array([0.0, 1.0])
        self.wall_axis = ax                                   # bars are stacked along this axis
        self.pitch = ax / float(self.nrm @ ax)                # translation between consecutive bars
        q = P @ self.nrm
        self.row = np.round(q - q.min()).astype(int)          # bar index of every square
        self.nrows = int(self.row.max()) + 1


def parse_blocks(tx, ty, tt, min_size=6):
    lab = components(tx, ty)
    blocks = []
    for l in np.unique(lab):
        idx = np.nonzero(lab == l)[0]
        if len(idx) >= min_size:
            blocks.append(Block(idx, tx, ty, tt))
    return blocks


def valid(tx, ty, tt, S, tol=1e-9):
    if len(tx) == 0:
        return True
    mo, mw = max_violation(tx, ty, tt, S)
    return max(mo, mw) <= tol


def count(tx, ty, tt, S, K):
    ax, ay, st = fp.refill(S, tx, ty, tt, K=K, time_limit=10.0)
    return len(tx) + len(ax), ax, ay


# ----------------------------------------------------------------------------- moves (return new arrays or None)
def mv_slide(tx, ty, tt, bl, d):
    x, y = tx.copy(), ty.copy()
    x[bl.idx] += d * bl.wall_axis[0]
    y[bl.idx] += d * bl.wall_axis[1]
    return x, y, tt.copy()


def mv_shift(tx, ty, tt, bl, dx, dy):
    x, y = tx.copy(), ty.copy()
    x[bl.idx] += dx
    y[bl.idx] += dy
    return x, y, tt.copy()


def mv_insert_bar(tx, ty, tt, bl, r, upper=True):
    """Duplicate bar r; the bars beyond it (upper) or before it move by one pitch."""
    src = bl.idx[bl.row == r]
    if len(src) == 0:
        return None
    x, y = tx.copy(), ty.copy()
    if upper:
        mv = bl.idx[bl.row > r]
        x[mv] += bl.pitch[0]; y[mv] += bl.pitch[1]
        nx = tx[src] + bl.pitch[0]; ny = ty[src] + bl.pitch[1]
    else:
        mv = bl.idx[bl.row < r]
        x[mv] -= bl.pitch[0]; y[mv] -= bl.pitch[1]
        nx = tx[src] - bl.pitch[0]; ny = ty[src] - bl.pitch[1]
    return np.concatenate([x, nx]), np.concatenate([y, ny]), np.concatenate([tt, tt[src]])


def mv_remove_bar(tx, ty, tt, bl, r, upper=True):
    dele = bl.idx[bl.row == r]
    if len(dele) == 0 or bl.nrows < 3:
        return None
    x, y = tx.copy(), ty.copy()
    if upper:
        mv = bl.idx[bl.row > r]
        x[mv] -= bl.pitch[0]; y[mv] -= bl.pitch[1]
    else:
        mv = bl.idx[bl.row < r]
        x[mv] += bl.pitch[0]; y[mv] += bl.pitch[1]
    keep = np.ones(len(tx), bool); keep[dele] = False
    return x[keep], y[keep], tt[keep]


def mv_grow(tx, ty, tt, bl, r, sign):
    """Add one square at an end of bar r."""
    src = bl.idx[bl.row == r]
    if len(src) == 0:
        return None
    proj = tx[src] * bl.bar[0] + ty[src] * bl.bar[1]
    k = src[np.argmax(proj)] if sign > 0 else src[np.argmin(proj)]
    return (np.append(tx, tx[k] + sign * bl.bar[0]), np.append(ty, ty[k] + sign * bl.bar[1]), np.append(tt, tt[k]))


def mv_drop(tx, ty, tt, k):
    keep = np.ones(len(tx), bool); keep[k] = False
    return tx[keep], ty[keep], tt[keep]


def propose(tx, ty, tt, blocks, rng):
    kind = rng.choice(["slide", "slide", "shift", "ins", "rem", "grow", "drop", "slide2"])
    if not blocks:
        return None, "none"
    bl = blocks[int(rng.integers(len(blocks)))]
    if kind == "slide":
        d = float(rng.choice([1, -1]) * rng.choice([0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4]) * rng.uniform(0.5, 1.5))
        return mv_slide(tx, ty, tt, bl, d), f"slide {d:+.3f}"
    if kind == "slide2":
        out = (tx, ty, tt)
        desc = []
        for b2 in blocks:
            d = float(rng.normal(0, 0.05))
            out = mv_slide(out[0], out[1], out[2], b2, d); desc.append(f"{d:+.3f}")
        return out, "slide all " + ",".join(desc)
    if kind == "shift":
        dx, dy = (float(v) for v in rng.normal(0, 0.01, 2))
        return mv_shift(tx, ty, tt, bl, dx, dy), f"shift {dx:+.3f},{dy:+.3f}"
    if kind == "ins":
        r = int(rng.integers(bl.nrows)); up = bool(rng.integers(2))
        return mv_insert_bar(tx, ty, tt, bl, r, up), f"insert bar {r} {'up' if up else 'down'}"
    if kind == "rem":
        r = int(rng.integers(bl.nrows)); up = bool(rng.integers(2))
        return mv_remove_bar(tx, ty, tt, bl, r, up), f"remove bar {r} {'up' if up else 'down'}"
    if kind == "grow":
        r = int(rng.integers(bl.nrows)); sg = int(rng.choice([1, -1]))
        return mv_grow(tx, ty, tt, bl, r, sg), f"grow bar {r} {sg:+d}"
    k = int(rng.integers(len(tx)))
    return mv_drop(tx, ty, tt, k), f"drop {k}"


def attach(tx, ty, tt, S_old, S_new):
    """Keep every block flush with the wall it leans on when the side changes."""
    x, y = tx.copy(), ty.copy()
    d = S_new - S_old
    lab = components(tx, ty)
    for l in np.unique(lab):
        idx = np.nonzero(lab == l)[0]
        h = 0.5 * (np.abs(np.cos(tt[idx])) + np.abs(np.sin(tt[idx])))
        if S_old - (tx[idx] + h).max() < (tx[idx] - h).min():
            x[idx] += d
        if S_old - (ty[idx] + h).max() < (ty[idx] - h).min():
            y[idx] += d
    return x, y


def run(label, target, evals, seed, eps, tilt, outdir, quiet=False):
    import diagper
    S0, x, y, th = diagper.source(label)
    n0 = len(x)
    K = int(math.ceil(S0 - 1e-9))
    S = K - eps
    if target is None:
        target = n0 + 1
    tx, ty, tt = split_core(x, y, th, tilt)
    tx, ty = attach(tx, ty, tt, S0, S)
    if not valid(tx, ty, tt, S):
        print(f"{os.path.basename(label)}: core not valid after re-attaching; skipped")
        return None
    rng = np.random.default_rng(seed)
    cur = (tx, ty, tt)
    ncur, ax, ay = count(*cur, S, K)
    best = (ncur, cur, ax, ay, "start")
    if not quiet:
        print(f"{os.path.basename(label)}: n={n0} K={K} S0={S0:.5f} core {len(tx)}; refill at K-eps gives {ncur}; target {target}", flush=True)
    t0 = time.time()
    hist = {}
    for it in range(evals):
        blocks = parse_blocks(*cur)
        new, desc = propose(*cur, blocks, rng)
        if new is None or len(new[0]) == 0 or not valid(*new, S):
            continue
        nn, ax, ay = count(*new, S, K)
        hist[desc.split()[0]] = hist.get(desc.split()[0], 0) + (1 if nn > ncur else 0)
        if nn >= ncur:
            if nn > ncur and not quiet:
                print(f"  it {it}: {ncur} -> {nn} by {desc} (core {len(new[0])}) {time.time()-t0:.0f}s", flush=True)
            cur, ncur = new, nn
            if nn > best[0]:
                best = (nn, new, ax, ay, desc)
                if nn >= target:
                    break
    nb, core, ax, ay, desc = best
    res = dict(label=label, n0=n0, K=K, S=S, best=int(nb), target=int(target), core=len(core[0]), seconds=time.time() - t0, gains=hist)
    if nb >= target and outdir:
        os.makedirs(os.path.join(RUN, outdir), exist_ok=True)
        X = np.concatenate([core[0], ax]); Y = np.concatenate([core[1], ay]); T = np.concatenate([core[2], np.zeros(len(ax))])
        mo, mw = max_violation(X, Y, T, S)
        f = os.path.join(RUN, outdir, f"K{K}_n{nb}_from{n0}_seed{seed}.json")
        json.dump(dict(n=int(nb), S=S, K=K, x=X.tolist(), y=Y.tolist(), th=T.tolist(), viol=max(mo, mw), source=os.path.basename(label)), open(f, "w"))
        res["file"] = f
        print(f"  *** {nb} squares at side {S} < {K}: saved {f} (float violation {max(mo,mw):.1e})", flush=True)
    if not quiet:
        print(f"  best {nb} (target {target}) in {time.time()-t0:.0f}s; improving moves by kind: {hist}", flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("label")
    ap.add_argument("--target", type=int, default=None)
    ap.add_argument("--evals", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--eps", type=float, default=1e-4)
    ap.add_argument("--tilt", type=float, default=0.3)
    ap.add_argument("--out", default="work/followup/core_hits")
    a = ap.parse_args()
    run(a.label, a.target, a.evals, a.seed, a.eps, a.tilt, a.out)
