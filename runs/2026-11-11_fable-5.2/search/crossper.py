#!/usr/bin/env python3
"""Cross-cut closure: the axis-parallel analogue of diagper.py.

  reduce(P, p, a, b): delete the squares whose centre has a <= x < a+p or b <= y < b+p, move the squares
                      to the right of the vertical strip by (-p, 0) and those above the horizontal strip
                      by (0, -p)   -> side S - p

For an all-axis-aligned packing the result is exactly valid for every (a, b): each row and each column
loses p cells.  Tilted squares next to the cuts overlap or leave gaps, which the penalty repair and the
exact polish then fix.  "Remove an L" (a = b = S - p) and the clean strip surgery of closure.py are
special cases; this pass tolerates overlaps and repairs them.

If the result (m squares) ends below the table value for m, the table was not closed under the
operation.  Nothing here is a result until verify.py says so.

  crossper.py screen|run [--nmin A --nmax B] [--certdir DIR | --labels json:/p1,cert:/p2] [--procs P] ...
"""
import argparse
import glob
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
import diagper  # noqa: E402
from opt import penalty_min, polish  # noqa: E402
from sqgeom import max_violation  # noqa: E402

_TAB = None


def table():
    """(rec[m], proven[m]) arrays for m = 0..N."""
    global _TAB
    if _TAB is None:
        R = attack.R()
        N = max(R)
        rec = np.zeros(N + 1); prov = np.zeros(N + 1, bool)
        for m in range(1, N + 1):
            rec[m] = attack.rec(m); prov[m] = bool(R[m]["proven_optimal"])
        _TAB = (rec, prov, N)
    return _TAB


def reduce_cross(S, x, y, th, p, a, b):
    k = ((x < a) | (x >= a + p)) & ((y < b) | (y >= b + p))
    x2 = np.where(x >= a + p, x - p, x)[k]
    y2 = np.where(y >= b + p, y - p, y)[k]
    t2 = th[k]
    S2 = S - p
    ins = diagper._inside(x2, y2, t2, S2, 0.02)
    return x2[ins], y2[ins], t2[ins], S2


def screen_src(label, margin, ps, step, maxviol, keep, mmin=26):
    try:
        S, x, y, th = diagper.source(label)
        mo0, mw0 = max_violation(x, y, th, S + 1e-9)
        if max(mo0, mw0) > 1e-6:
            return []
    except Exception:  # noqa: BLE001
        return []
    rec, prov, N = table()
    tn = (th + np.pi / 4) % (np.pi / 2) - np.pi / 4
    if np.count_nonzero(np.abs(tn) > 0.02) == 0:
        return []                              # all axis-aligned: the cut is plain grid arithmetic
    if ps == "auto":
        k = int(math.floor(S + 1e-9))
        ps = tuple(range(max(1, k - 17), max(1, k - 17) + 11))
    leads = []
    for p in ps:
        S2 = S - p
        if S2 < 4.5:
            continue
        seen = set()
        grid = np.arange(0.0, S - p + 1e-9, step)
        ky_all = [((y < b) | (y >= b + p)) for b in grid]
        ys_all = [np.where(y >= b + p, y - p, y) for b in grid]
        for a in grid:
            kx = (x < a) | (x >= a + p)
            xs = np.where(x >= a + p, x - p, x)
            nx = int(np.count_nonzero(kx))
            if nx < mmin or rec[min(nx, N)] <= S2 - margin:
                continue                       # even the vertical cut alone leaves too few squares to matter
            for ib, b in enumerate(grid):
                k = kx & ky_all[ib]
                m0 = int(np.count_nonzero(k))
                if m0 < mmin or rec[min(m0, N)] <= S2 - margin:
                    continue                   # records are non-decreasing in m: fewer squares cannot help
                sig = hash(k.tobytes())
                if sig in seen:
                    continue
                seen.add(sig)
                x2 = xs[k]; y2 = ys_all[ib][k]; t2 = th[k]
                ins = diagper._inside(x2, y2, t2, S2, 0.02)
                x2, y2, t2 = x2[ins], y2[ins], t2[ins]
                m = len(x2)
                if m < mmin or m > N or prov[m]:
                    continue
                gap = S2 - rec[m]
                if gap >= margin:
                    continue
                mo, mw = max_violation(x2, y2, t2, S2 + 1e-9)
                v = max(mo, mw)
                if v > maxviol:
                    continue
                leads.append(dict(src=label, kind="cross", p=int(p), c=float(a), b=float(b), anti=False, m=m, S0=float(S2),
                                  rec=float(rec[m]), gap=float(gap), viol=float(v)))
    groups = {}
    for L in leads:
        groups.setdefault((L["p"], L["m"]), []).append(L)
    out = []
    for key, g in groups.items():
        g.sort(key=lambda L: L["viol"])
        out.extend(g[:keep])
    return out


def _opt(L):
    S, x, y, th = diagper.source(L["src"])
    x2, y2, t2, S2 = reduce_cross(S, x, y, th, L["p"], L["c"], L["b"])
    t0 = time.time()
    try:
        if L["viol"] > 1e-7:
            x2, y2, t2, S3, E = penalty_min(x2, y2, t2, S2 + 2e-3, 2000.0, maxiter=3000)
            x2, y2, t2, S3, E = penalty_min(x2, y2, t2, S3, 20000.0, maxiter=3000)
            r = polish(x2, y2, t2, S=S3 + 1e-3, delta=0.01)
        else:
            r = polish(x2, y2, t2, S=S2 + 1e-9, delta=0.01)
    except Exception as e:  # noqa: BLE001
        return dict(L, S=None, err=str(e), t=time.time() - t0)
    if r[4] > 1e-10:
        return dict(L, S=None, err="viol", t=time.time() - t0)
    out = dict(L, S=float(r[3]), t=time.time() - t0)
    name = os.path.basename(str(L["src"])).replace(".cert", "").replace(".json", "").replace(".npz", "")[:60]
    if r[3] < L["rec"] - 1e-9:
        out["file"] = attack.save_cand(L["m"], r[3], r[0], r[1], r[2], f"cross_from{name}_p{L['p']}_a{L['c']:.2f}_b{L['b']:.2f}")
    elif r[3] < L["rec"] + 0.01:
        attack._save_seed(L["m"], r[3], r[0], r[1], r[2], f"cross_from{name}_p{L['p']}_a{L['c']:.2f}_b{L['b']:.2f}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["screen", "run"])
    ap.add_argument("--nmin", type=int, default=26); ap.add_argument("--nmax", type=int, default=324)
    ap.add_argument("--certdir", default=""); ap.add_argument("--labels", default="")
    ap.add_argument("--margin", type=float, default=0.02); ap.add_argument("--maxviol", type=float, default=0.40)
    ap.add_argument("--step", type=float, default=0.1); ap.add_argument("--pmin", type=int, default=1); ap.add_argument("--pmax", type=int, default=6)
    ap.add_argument("--pauto", action="store_true"); ap.add_argument("--keep", type=int, default=2)
    ap.add_argument("--alpha", type=float, default=0.12); ap.add_argument("--net", type=float, default=0.01)
    ap.add_argument("--maxleads", type=int, default=0); ap.add_argument("--targets", default="nontrivial", choices=["all", "nontrivial"])
    ap.add_argument("--procs", type=int, default=8); ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    if a.labels:
        labels = [v for v in a.labels.split(",") if v]
    elif a.certdir:
        labels = diagper.dir_labels(a.certdir)
    else:
        labels = [n for n in range(a.nmin, a.nmax + 1) if abs(attack.rec(n) - round(attack.rec(n))) > 1e-12]
    ps = "auto" if a.pauto else tuple(range(a.pmin, a.pmax + 1))
    print(f"cross-cut screen over {len(labels)} sources, p={ps}, step {a.step}", flush=True)
    with mp.Pool(a.procs) as pool:
        parts = pool.starmap(screen_src, [(lab, a.margin, ps, a.step, a.maxviol, a.keep) for lab in labels], chunksize=1)
    leads = [L for part in parts for L in part]
    leads.sort(key=lambda L: L["gap"] + a.alpha * L["viol"])
    print(f"screen: {len(leads)} leads with (S0 - record) < {a.margin} in {time.time()-t0:.0f}s", flush=True)
    json.dump(leads, open(os.path.join(RUN, "work", f"cross_leads{a.tag}.json"), "w"), indent=0)
    for L in leads[:40]:
        print(f"  src {os.path.basename(str(L['src']))} cross p={L['p']} a={L['c']:.2f} b={L['b']:.2f} -> m={L['m']:3d} S0={L['S0']:.6f} "
              f"record {L['rec']:.6f} gap {L['gap']:+.5f} raw viol {L['viol']:.4f}", flush=True)
    if a.mode == "screen":
        return
    leads = [L for L in leads if L["gap"] + a.alpha * L["viol"] < a.net]
    leads = [L for L in leads if not (L["gap"] > -1e-7 and L["viol"] < 1e-6)]
    if a.targets == "nontrivial":
        leads = [L for L in leads if abs(L["rec"] - round(L["rec"])) > 1e-9]
    seen = set(); uniq = []
    for L in leads:
        key = (L["m"], L["p"], round(L["S0"], 5), round(L["viol"], 3))
        if key in seen:
            continue
        seen.add(key); uniq.append(L)
    leads = uniq[: a.maxleads] if a.maxleads else uniq
    print(f"optimising {len(leads)} leads (gap + {a.alpha}*viol < {a.net}, targets={a.targets})", flush=True)
    res = []
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(_opt, leads, chunksize=1):
            res.append(r)
            if r.get("S") is not None:
                flag = "  <<< BELOW RECORD" if r["S"] < r["rec"] - 1e-9 else ""
                print(f"[{time.time()-t0:6.0f}s] src {os.path.basename(str(r['src']))} cross p={r['p']} c={r['c']:.2f} b={r['b']:.2f} -> m={r['m']} S={r['S']:.9f} "
                      f"record {r['rec']:.9f} diff {r['S']-r['rec']:+.6f} (raw gap {r['gap']:+.5f}, viol {r['viol']:.3f}){flag}", flush=True)
    ok = [r for r in res if r.get("S") is not None]
    bym = {}
    for r in ok:
        if r["m"] not in bym or r["S"] < bym[r["m"]]["S"]:
            bym[r["m"]] = r
    for m in sorted(bym):
        r = bym[m]
        attack.log_attempt(m, "crossper: cross-cut closure (delete a vertical and a horizontal strip of width p from a published packing, "
                              "close up, penalty repair + SLP polish) (search/crossper.py)",
                           r["S"], None, sum(q["t"] for q in ok if q["m"] == m),
                           f"{sum(1 for q in res if q['m']==m)} leads for this m; best from source {os.path.basename(str(r['src']))} (p={r['p']}, a={r['c']:.2f}, b={r['b']:.2f}): "
                           f"S={r['S']:.9f} vs record {r['rec']:.9f}; " + ("BELOW RECORD, see work/cand" if r["S"] < r["rec"] - 1e-9 else "no improvement"))
    json.dump(res, open(os.path.join(RUN, "work", f"cross_results{a.tag}.json"), "w"), indent=0)
    print(f"done: {len(ok)}/{len(res)} leads optimised; below record: {sum(1 for r in ok if r['S'] < r['rec'] - 1e-9)}; wall {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
