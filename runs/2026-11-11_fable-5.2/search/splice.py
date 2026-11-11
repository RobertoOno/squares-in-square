#!/usr/bin/env python3
"""Periodic splice for the diagonal-band family.

Observation (see REPORT): the published records for n = 106, 177, 266 are one band structure
extended by a (3,3) "period" each time (k -> k+3, 71 resp. 89 squares inserted), but with different
local configurations at the top-right end of the band, and therefore different sides.
splice(A, B, shift) builds  {A below the cut} + {slab of B between the cuts} + {A above the cut,
moved by (shift, shift)}  so that the end configuration of the SMALLER packing A is carried into the
size of the LARGER packing B.  The result is then optimised by opt.py and judged by verify.py.

Usage: splice.py A_n B_n [--out DIR]     (packings are the published record witnesses)
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import attack  # noqa: E402
from opt import penalty_min, polish  # noqa: E402
from sqgeom import max_violation  # noqa: E402


def load(spec):
    if str(spec).isdigit():
        S, x, y, th = attack.wit(int(spec))
        return S, x, y, th
    d = json.load(open(spec))
    return float(d["S"]), np.array(d["x"]), np.array(d["y"]), np.array(d["th"])


def splice(A, B, shift, s_cut):
    SA, xa, ya, ta = A
    SB, xb, yb, tb = B
    sa = xa + ya
    sb = xb + yb
    lo = sa < s_cut
    up = ~lo
    slab = (sb >= s_cut) & (sb < s_cut + 2 * shift)
    x = np.concatenate([xa[lo], xb[slab], xa[up] + shift])
    y = np.concatenate([ya[lo], yb[slab], ya[up] + shift])
    th = np.concatenate([ta[lo], tb[slab], ta[up]])
    return x, y, th, SA + shift


def try_all(A, B, n_target, shift, label, outdir, verbose=True, step=0.25):
    SA, xa, ya, ta = A
    res = []
    for s_cut in np.arange(2.0, 2 * SA - 2.0, step):
        x, y, th, S0 = splice(A, B, shift, s_cut)
        if len(x) != n_target:
            continue
        mo, mw = max_violation(x, y, th, S0 + 1e-3)
        if max(mo, mw) > 0.2:
            continue
        # resolve the small mismatch with a stiff penalty, then exact polish
        try:
            x1, y1, t1, S1, E = penalty_min(x, y, th, S0 + 2e-3, 2000.0, maxiter=3000)
            x1, y1, t1, S1, E = penalty_min(x1, y1, t1, S1, 20000.0, maxiter=3000)
            r = polish(x1, y1, t1, S=S1 + 1e-3, delta=0.003)
        except Exception as e:  # noqa: BLE001
            continue
        if r[4] > 1e-10:
            continue
        res.append((r[3], s_cut, max(mo, mw), r))
        if verbose:
            print(f"   {label}: s_cut={s_cut:.2f} raw violation {max(mo,mw):.4f} -> S={r[3]:.10f}", flush=True)
    res.sort(key=lambda t: t[0])
    if res:
        S, s_cut, v, r = res[0]
        os.makedirs(outdir, exist_ok=True)
        p = os.path.join(outdir, f"n{n_target}_S{S:.10f}_splice_{label}.json")
        json.dump(dict(n=n_target, S=S, x=r[0].tolist(), y=r[1].tolist(), th=r[2].tolist(), tag=f"splice {label} s_cut={s_cut:.2f}"), open(p, "w"))
        return S, p
    return None, None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("A"); ap.add_argument("B"); ap.add_argument("--shift", type=float, default=3.0)
    ap.add_argument("--n", type=int, default=0); ap.add_argument("--label", default=""); ap.add_argument("--step", type=float, default=0.25)
    ap.add_argument("--out", default=os.path.join(RUN, "work", "splice"))
    a = ap.parse_args()
    A = load(a.A); B = load(a.B)
    n_target = a.n or len(B[1])
    label = a.label or f"{os.path.basename(str(a.A))}_into_{os.path.basename(str(a.B))}"
    S, p = try_all(A, B, n_target, a.shift, label, a.out, step=a.step)
    rec = attack.rec(n_target)
    print(f"RESULT n={n_target}: best S={S} record {rec:.12f} diff {None if S is None else S-rec:+.3e} file {p}")
