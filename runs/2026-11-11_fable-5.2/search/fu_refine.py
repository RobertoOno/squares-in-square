#!/usr/bin/env python3
"""Follow-up: hill climbing on block layouts (fu_pinwheel) with tapered rows.

Starts from the layouts saved by fu_scan.py and tries local edits: lift changes, one row more or
fewer, a different wall or tilt sign, and tapers (rows near the ends of a block shortened from
either side). Accepts an edit when the exact refill count does not drop.

  fu_refine.py K scan.json [--iters N] [--seed s] [--eps 1e-3] [--starts 6]
"""
import argparse
import copy
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


def norm(blocks):
    out = []
    for b in blocks:
        b = dict(b)
        if b.get("taper"):
            b["taper"] = {int(k): tuple(v) for k, v in b["taper"].items()}
        else:
            b.pop("taper", None)
        out.append(b)
    return out


def mutate(blocks, K, S, rng):
    bl = copy.deepcopy(blocks)
    b = bl[int(rng.integers(len(bl)))]
    bd = fp.Band(b["b"], K - S)
    kind = rng.choice(["lift", "lift", "rows", "taper", "taper", "taper", "flip", "width"])
    if kind == "lift":
        b["lift"] = max(0.0, b["lift"] + float(rng.choice([-1, 1]) * rng.choice([0.003, 0.01, 0.03, 0.1, 0.3])))
    elif kind == "rows":
        d = int(rng.choice([-1, 1]))
        if b["R"] + d < 2:
            return None
        if rng.integers(2):                      # keep the far end where it is
            b["lift"] = max(0.0, b["lift"] - d * bd.sec)
        b["R"] += d
        if b.get("taper"):
            b["taper"] = {j: v for j, v in b["taper"].items() if j < b["R"]}
    elif kind == "taper":
        tp = dict(b.get("taper") or {})
        j = int(rng.choice([0, 1, 2, 3, b["R"] - 4, b["R"] - 3, b["R"] - 2, b["R"] - 1]))
        if j < 0 or j >= b["R"]:
            return None
        a, e = tp.get(j, (0, b["b"]))
        which = rng.integers(4)
        if which == 0:
            a += 1
        elif which == 1:
            e -= 1
        elif which == 2:
            a = max(0, a - 1)
        else:
            e = min(b["b"], e + 1)
        if e - a < 0:
            return None
        if (a, e) == (0, b["b"]):
            tp.pop(j, None)
        else:
            tp[j] = (a, e)
        b["taper"] = tp
    elif kind == "flip":
        b["flip"] = not b["flip"]
    else:
        d = int(rng.choice([-1, 1]))
        if b["b"] + d < 3:
            return None
        b["b"] += d
        b.pop("taper", None)
        nb = fp.Band(b["b"], K - S)
        b["R"] = max(2, int(round(b["R"] * bd.sec / nb.sec)))
    return bl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("K", type=int)
    ap.add_argument("scan")
    ap.add_argument("--iters", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--starts", type=int, default=6)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    K = a.K; S = K - a.eps
    rng = np.random.default_rng(a.seed)
    starts = json.load(open(os.path.join(RUN, a.scan)))[: a.starts]
    best_all = None
    t0 = time.time()
    for si, st in enumerate(starts):
        cur = norm(st["blocks"])
        ncur = fp.assemble(S, cur, K=K)[0]
        for it in range(a.iters // len(starts)):
            new = mutate(cur, K, S, rng)
            if new is None:
                continue
            try:
                if not fp.tilted_ok(S, new, K=K):
                    continue
                nn = fp.assemble(S, new, K=K, time_limit=10.0)[0]
            except Exception:  # noqa: BLE001
                continue
            if nn >= ncur:
                if nn > ncur:
                    print(f"  start {si} it {it}: {ncur} -> {nn} (deficit {K*K-nn}) {time.time()-t0:.0f}s", flush=True)
                cur, ncur = new, nn
        if best_all is None or ncur > best_all[0]:
            best_all = (ncur, cur)
    n, bl = best_all
    print(f"K={K}: best after refinement n={n} deficit {K*K-n} ({time.time()-t0:.0f}s)")
    for b in bl:
        print("   ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in b.items()})
    if a.out:
        js = [dict(n=int(n), blocks=[{**b, "taper": {str(k): list(v) for k, v in (b.get("taper") or {}).items()}} for b in bl])]
        json.dump(js, open(os.path.join(RUN, a.out), "w"))


if __name__ == "__main__":
    main()
