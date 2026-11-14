#!/usr/bin/env python3
"""Follow-up: seeds with one more square from a tolerant refill, then the exact polish decides.

For a public parent packing of n squares at side S < K: keep its tilted core, set the side to
K - eps, and re-place the upright squares with fu_pinwheel.refill(soft=delta): cells may dip into
core squares by up to delta. When that yields at least n + 1 squares, the slightly overlapping seed
goes through the penalty repair and the exact polish (attack.local_opt). A final side below K is a
packing of n + 1 squares under the grid side.

  fu_softseed.py K [--top 3] [--deltas 0.02 0.05 0.1] [--polish 4] [--extra 1]
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
import attack  # noqa: E402
import diagper  # noqa: E402
import fu_core as fc  # noqa: E402
import fu_pinwheel as fp  # noqa: E402
from sqgeom import max_violation  # noqa: E402


def parents(K, top):
    d = json.load(open(os.path.join(RUN, "work/followup/refill_public.json")))
    rs = [r for r in d if r["K"] == K]
    rs.sort(key=lambda r: (-r["n"], r["S"]))
    out = []
    for r in rs[: top * 3]:
        hits = glob.glob(os.path.join(RUN, "work/remote/*/work/**/" + r["src"]), recursive=True)
        if hits:
            out.append((r["n"], r["S"], ("npz:" if hits[0].endswith(".npz") else "cert:") + hits[0]))
        if len(out) >= top:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("K", type=int)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--deltas", type=float, nargs="+", default=[0.02, 0.05, 0.1])
    ap.add_argument("--polish", type=int, default=4)
    ap.add_argument("--extra", type=int, default=1)
    ap.add_argument("--eps", type=float, default=1e-4)
    ap.add_argument("--tilt", type=float, default=0.3)
    a = ap.parse_args()
    K = a.K
    S = K - a.eps
    seeds = []
    for n, S0, lab in parents(K, a.top):
        _, x, y, th = diagper.source(lab)
        tx, ty, tt = fc.split_core(x, y, th, a.tilt)
        tx, ty = fc.attach(tx, ty, tt, S0, S)
        if not fc.valid(tx, ty, tt, S):
            print(f"  parent n={n} {os.path.basename(lab)}: core invalid at K-eps, skipped", flush=True)
            continue
        base, _, _ = fc.count(tx, ty, tt, S, K)
        for dl in a.deltas:
            ax, ay, st, dep = fp.refill(S, tx, ty, tt, K=K, soft=dl, full=True, time_limit=20.0)
            cnt = len(tx) + len(ax)
            nsoft = int((dep > 1e-9).sum())
            print(f"  parent n={n} S0={S0:.5f} {os.path.basename(lab)[:40]}: exact refill {base}; tolerance {dl}: {cnt} squares, "
                  f"{nsoft} dipping, depth sum {dep.sum():.3f} max {dep.max() if len(dep) else 0:.3f}", flush=True)
            if cnt >= n + a.extra:
                seeds.append(dict(n0=n, cnt=cnt, delta=dl, depth=float(dep.sum()), maxdep=float(dep.max()), lab=lab,
                                  x=np.concatenate([tx, ax]), y=np.concatenate([ty, ay]), th=np.concatenate([tt, np.zeros(len(ax))]),
                                  dep=np.concatenate([np.zeros(len(tx)), dep])))
    seeds.sort(key=lambda s: (-(s["cnt"] - s["n0"] >= a.extra), s["depth"]))
    outdir = os.path.join(RUN, "work/followup/softseed")
    os.makedirs(outdir, exist_ok=True)
    done = 0
    for sd in seeds:
        if done >= a.polish:
            break
        target = sd["n0"] + a.extra
        x, y, th = sd["x"], sd["y"], sd["th"]
        if sd["cnt"] > target:                 # drop the deepest dipping cells first
            order = np.argsort(-sd["dep"])
            keep = np.ones(len(x), bool); keep[order[: sd["cnt"] - target]] = False
            x, y, th = x[keep], y[keep], th[keep]
        t0 = time.time()
        try:
            res = attack.local_opt(x.copy(), y.copy(), th.copy(), S + 0.02)
        except Exception as e:  # noqa: BLE001
            res = None
            print("   polish failed:", str(e)[:80], flush=True)
        done += 1
        if res is None:
            print(f"   seed from n={sd['n0']} (tolerance {sd['delta']}, depth {sd['depth']:.3f}): no feasible polish ({time.time()-t0:.0f}s)", flush=True)
            continue
        Sf = float(res[3])
        mo, mw = max_violation(res[0], res[1], res[2], Sf)
        flag = "  <<< BELOW THE GRID" if Sf < K - 1e-9 else ""
        print(f"   seed from n={sd['n0']} (tolerance {sd['delta']}, depth {sd['depth']:.3f}): n={target} polished side {Sf:.6f} "
              f"(K={K}, violation {max(mo,mw):.1e}, {time.time()-t0:.0f}s){flag}", flush=True)
        json.dump(dict(n=target, S=Sf, K=K, x=res[0].tolist(), y=res[1].tolist(), th=res[2].tolist(), parent=os.path.basename(sd["lab"]),
                       delta=sd["delta"]), open(os.path.join(outdir, f"K{K}_n{target}_S{Sf:.6f}.json"), "w"))
    if not seeds:
        print(f"K={K}: no seed with {a.extra} more square(s)")


if __name__ == "__main__":
    main()
