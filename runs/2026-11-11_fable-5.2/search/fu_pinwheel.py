#!/usr/bin/env python3
"""Follow-up (after the run): tilted blocks plus an exact refill of the upright squares.

A packing in a square of side S = K - eps (K integer, eps small) is described by its tilted squares
only. They come in "blocks": stacks of rows of b unit squares tilted by theta, flush between a wall
and the grid anchored at the opposite wall (Ryu's band; rows as in Fang's Theorem A note). The
upright squares are not searched: for a given set of tilted squares the largest set of unit cells of
the four corner-anchored unit grids that avoids them is found exactly as a maximum independent set
(one inequality per elementary rectangle of the overlaid grids), solved with scipy's HiGHS MILP.

This module only counts and builds float packings; nothing here is a judge.
"""
import math
import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp


# ----------------------------------------------------------------------------- band geometry
def band_t(b, epsw):
    """t = tan(theta/2) just above 1/b with row width W = b cos + sin = b - epsw."""
    a = 2.0 * b - epsw
    return (1.0 + math.sqrt(1.0 + a * epsw)) / a


class Band:
    def __init__(self, b, epsw):
        self.b = b
        self.t = band_t(b, epsw)
        d = 1.0 + self.t * self.t
        self.c = (1.0 - self.t * self.t) / d
        self.s = 2.0 * self.t / d
        self.th = 2.0 * math.atan(self.t)
        self.W = b * self.c + self.s
        self.sec = 1.0 / self.c
        self.h = b * self.s + self.c


def block_squares(S, wall, b, R, lift, flip=False, taper=None, epsw=None, K=None):
    """Centres and angles of a block of R rows of b squares against `wall`.
    Local frame: X across the band (0 at the wall), Y along the wall; row j has its lowest corner
    at (s, lift + j*sec). taper[j] = (a, e) keeps squares a..e-1 of row j."""
    if epsw is None:
        epsw = (K if K is not None else math.ceil(S - 1e-12)) - S
    bd = Band(b, epsw)
    X, Y = [], []
    for j in range(R):
        a, e = (0, b) if taper is None or j not in taper else taper[j]
        for i in range(a, e):
            X.append(bd.s + (i + 0.5) * bd.c - 0.5 * bd.s)
            Y.append(lift + j * bd.sec + (i + 0.5) * bd.s + 0.5 * bd.c)
    X = np.array(X); Y = np.array(Y)
    th = bd.th
    if flip:
        X = bd.W - X
        th = -th
    if wall == "left":
        x, y, ang = X, Y, th
    elif wall == "right":
        x, y, ang = S - X, Y, -th
    elif wall == "bottom":
        x, y, ang = Y, X, -th
    elif wall == "top":
        x, y, ang = Y, S - X, th
    else:
        raise ValueError(wall)
    return x, y, np.full(len(x), ang), bd


# ----------------------------------------------------------------------------- exact refill
def _depth(cx, cy, tx, ty, tth):
    """Largest penetration depth of every upright cell into the tilted squares (0 if it touches none)."""
    dep = np.zeros(len(cx))
    if len(tx) == 0:
        return dep
    order = np.argsort(cx)
    cxs = cx[order]
    for k in range(len(tx)):
        lo = np.searchsorted(cxs, tx[k] - 1.4143)
        hi = np.searchsorted(cxs, tx[k] + 1.4143)
        if hi <= lo:
            continue
        idx = order[lo:hi]
        dx = cx[idx] - tx[k]
        dy = cy[idx] - ty[k]
        near = np.abs(dy) < 1.4143
        if not near.any():
            continue
        idx = idx[near]; dx = dx[near]; dy = dy[near]
        c, s = math.cos(tth[k]), math.sin(tth[k])
        Rr = 0.5 * (1.0 + abs(c) + abs(s))
        sep = np.maximum(np.maximum(np.abs(dx), np.abs(dy)), np.maximum(np.abs(dx * c + dy * s), np.abs(-dx * s + dy * c))) - Rr
        dep[idx] = np.maximum(dep[idx], -sep)
    return dep


def _free_mask(cx, cy, tx, ty, tth, tol=1e-9):
    """True for upright cells (centres cx, cy) that overlap no tilted square."""
    ok = np.ones(len(cx), bool)
    if len(tx) == 0:
        return ok
    order = np.argsort(cx)
    cxs = cx[order]
    for k in range(len(tx)):
        lo = np.searchsorted(cxs, tx[k] - 1.4143)
        hi = np.searchsorted(cxs, tx[k] + 1.4143)
        if hi <= lo:
            continue
        idx = order[lo:hi]
        dx = cx[idx] - tx[k]
        dy = cy[idx] - ty[k]
        near = np.abs(dy) < 1.4143
        if not near.any():
            continue
        idx = idx[near]; dx = dx[near]; dy = dy[near]
        c, s = math.cos(tth[k]), math.sin(tth[k])
        Rr = 0.5 * (1.0 + abs(c) + abs(s))
        sep = np.maximum(np.maximum(np.abs(dx), np.abs(dy)), np.maximum(np.abs(dx * c + dy * s), np.abs(-dx * s + dy * c))) - Rr
        ok[idx[sep < -tol]] = False
    return ok


def refill(S, tx, ty, tth, K=None, time_limit=20.0, forbid=None, soft=0.0, full=False):
    """Largest set of upright unit cells of the four corner-anchored grids avoiding the tilted squares.
    Returns (x, y) of the chosen cells and the MILP status."""
    if K is None:
        K = int(math.ceil(S - 1e-12))
    eps = K - S
    assert 0 < eps < 0.5
    # 1-D columns: type 0 (anchored at 0): cell [i, i+1], i = 0..K-2; type 1 (anchored at S): cell [r-eps, r+1-eps], r = 1..K-1
    cols = [(0, i) for i in range(K - 1)] + [(1, r) for r in range(1, K)]
    lo = np.array([i if a == 0 else i - eps for a, i in cols])
    ctr = lo + 0.5
    nc = len(cols)
    # elementary intervals: big i (covered by type0 i and type1 i), tiny i (type0 i and type1 i+1)
    idx0 = {i: k for k, (a, i) in enumerate(cols) if a == 0}
    idx1 = {i: k for k, (a, i) in enumerate(cols) if a == 1}
    ivals = []
    for i in range(K):
        ivals.append([c for c in (idx0.get(i), idx1.get(i)) if c is not None])
    for i in range(K - 1):
        ivals.append([c for c in (idx0.get(i), idx1.get(i + 1)) if c is not None])
    CX, CY = np.meshgrid(ctr, ctr, indexing="ij")
    cx = CX.ravel(); cy = CY.ravel()              # candidate id = ix * nc + iy
    if soft > 0:                                   # cells may dip into tilted squares by up to `soft`, at a price
        dep = _depth(cx, cy, tx, ty, tth)
        free = dep <= soft
    else:
        dep = None
        free = _free_mask(cx, cy, tx, ty, tth)
    if forbid is not None:
        free &= ~forbid(cx, cy)
    ids = -np.ones(nc * nc, int)
    fid = np.nonzero(free)[0]
    ids[fid] = np.arange(len(fid))
    rows, colsA = [], []
    r = 0
    for ax in ivals:
        for ay in ivals:
            mem = [ids[a * nc + b] for a in ax for b in ay]
            mem = [m for m in mem if m >= 0]
            if len(mem) >= 2:
                rows.extend([r] * len(mem)); colsA.extend(mem); r += 1
    nv = len(fid)
    if r == 0:
        return (cx[fid], cy[fid], "trivial") + ((np.zeros(len(fid)),) if full else ())
    A = sp.csr_matrix((np.ones(len(rows)), (rows, colsA)), shape=(r, nv))
    w = np.ones(nv)
    if dep is not None:
        w = 1.0 - 0.5 * np.maximum(dep[fid], 0.0) / soft          # a cell at the tolerance still counts one half
    res = milp(c=-w, constraints=LinearConstraint(A, -np.inf, 1.0), integrality=np.ones(nv),
               bounds=Bounds(0, 1), options={"time_limit": time_limit, "disp": False})
    if res.x is None:
        return (np.zeros(0), np.zeros(0), "failed") + ((np.zeros(0),) if full else ())
    pick = res.x > 0.5
    st = "optimal" if res.status == 0 else f"status{res.status}"
    if full:
        return cx[fid][pick], cy[fid][pick], st, (np.maximum(dep[fid][pick], 0.0) if dep is not None else np.zeros(int(pick.sum())))
    return cx[fid][pick], cy[fid][pick], st


def assemble(S, blocks, K=None, time_limit=20.0):
    """blocks: list of dicts for block_squares. Returns (n, x, y, th, n_tilted, status)."""
    if K is None:
        K = int(math.ceil(S - 1e-12))
    xs, ys, ts = [], [], []
    for bl in blocks:
        x, y, th, _ = block_squares(S, K=K, **bl)
        xs.append(x); ys.append(y); ts.append(th)
    tx = np.concatenate(xs) if xs else np.zeros(0)
    ty = np.concatenate(ys) if ys else np.zeros(0)
    tt = np.concatenate(ts) if ts else np.zeros(0)
    ax, ay, st = refill(S, tx, ty, tt, K=K, time_limit=time_limit)
    x = np.concatenate([tx, ax]); y = np.concatenate([ty, ay]); th = np.concatenate([tt, np.zeros(len(ax))])
    return len(x), x, y, th, len(tx), st


def tilted_ok(S, blocks, K=None, tol=1e-9):
    """Tilted squares inside the container and pairwise disjoint (blocks must not collide)."""
    from sqgeom import max_violation
    xs, ys, ts = [], [], []
    for bl in blocks:
        x, y, th, _ = block_squares(S, K=K, **bl)
        xs.append(x); ys.append(y); ts.append(th)
    x = np.concatenate(xs); y = np.concatenate(ys); th = np.concatenate(ts)
    mo, mw = max_violation(x, y, th, S)
    return max(mo, mw) <= tol


if __name__ == "__main__":
    import sys
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    from sqgeom import max_violation
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    S = K - 1e-3
    t0 = time.time()
    n, x, y, th, nt, st = assemble(S, [], K=K)
    print(f"K={K}: no blocks -> n={n} (expect {(K-1)**2}) [{st}] {time.time()-t0:.2f}s")
    b = max(3, int(round(math.sqrt(2 * K))) | 1)
    bd = Band(b, K - S)
    Rr = int((S - bd.h) / bd.sec) + 1
    Rt = int((K - b - bd.h) / bd.sec) + 1
    blocks = [dict(wall="right", b=b, R=Rr, lift=0.0, flip=True), dict(wall="top", b=b, R=Rt, lift=0.0, flip=True)]
    t0 = time.time()
    n, x, y, th, nt, st = assemble(S, blocks, K=K)
    mo, mw = max_violation(x, y, th, S)
    print(f"K={K}: Ryu L with b={b}, rows {Rr}+{Rt}: n={n} deficit {K*K-n} tilted {nt} [{st}] viol {max(mo,mw):.1e} {time.time()-t0:.2f}s")
