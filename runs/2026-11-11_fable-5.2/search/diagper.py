#!/usr/bin/env python3
"""Diagonal-period closure.

Many records are diagonal bands of tilted squares between two corner-anchored grids, and the band
is (nearly) invariant under a translation (p, p).  Two operations follow, the diagonal analogues of
"remove an L" / "add an L":

  reduce(P, p, c): delete the squares whose centre has c <= x+y < c+2p, move the squares beyond
                   by (-p,-p), drop what falls outside the smaller container  -> side ~ S-p
  extend(P, p, c): move the squares with x+y >= c by (+p,+p), copy the tilted squares of the last
                   period below the cut into the gap, fill the rest with corner-anchored unit cells
                   -> side ~ S+p

Either result has some number m of squares; if its side (after exact optimisation) is below the
table value for m, the table was not closed under the operation.  Nothing here is a result until
verify.py says so.

  diagper.py screen [--nmin A --nmax B --margin 0.02]     cheap pre-screen over all records (prints leads)
  diagper.py run    [--nmin A --nmax B --margin 0.02 --procs P]   pre-screen + optimise the leads
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
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import attack  # noqa: E402
from blockseed import fill  # noqa: E402
from opt import penalty_min, polish  # noqa: E402
from sqgeom import max_violation  # noqa: E402


def load_cert(path):
    """Third-party certificate text format: '# ...' comments, then 'n side', then n lines 'x y t' (rationals, t = tan(theta/2))."""
    from fractions import Fraction as F
    rows = [l.split() for l in open(path).read().split("\n") if l.strip() and not l.startswith("#")]
    n = int(rows[0][0]); S = float(F(rows[0][1]))
    x = np.array([float(F(r[0])) for r in rows[1:n + 1]]); y = np.array([float(F(r[1])) for r in rows[1:n + 1]])
    th = np.array([2.0 * math.atan(float(F(r[2]))) for r in rows[1:n + 1]])
    assert len(x) == n
    return S, x, y, th


_SRC_CACHE = {}


def source(label):
    """'229' -> published record witness of n=229;  'cert:/path/file.cert' -> third-party certificate file."""
    if label not in _SRC_CACHE:
        if str(label).startswith("cert:"):
            _SRC_CACHE[label] = load_cert(label[5:])
        elif str(label).startswith("npz:"):        # third-party numpy archive with keys xy (n,2), th (n,), L
            from sqgeom import normalize
            z = np.load(label[4:], allow_pickle=False)
            xy = np.array(z["xy"], float)
            x, y, th, S = normalize(xy[:, 0].copy(), xy[:, 1].copy(), np.array(z["th"], float).copy())
            _SRC_CACHE[label] = (S + 2e-10, x + 1e-10, y + 1e-10, th)
        elif str(label).startswith("json:"):       # one of our own float packings (keys x, y, th)
            from sqgeom import normalize
            d = json.load(open(label[5:]))
            x, y, th, S = normalize(np.array(d["x"], float), np.array(d["y"], float), np.array(d["th"], float))
            _SRC_CACHE[label] = (S + 2e-10, x + 1e-10, y + 1e-10, th)
        else:
            _SRC_CACHE[label] = attack.wit(int(label))
    return _SRC_CACHE[label]


def dir_labels(d):
    """All third-party packings under a directory (recursive): *.cert -> 'cert:path', *.npz -> 'npz:path'."""
    import glob
    out = ["cert:" + f for f in sorted(glob.glob(os.path.join(d, "**", "*.cert"), recursive=True))]
    out += ["npz:" + f for f in sorted(glob.glob(os.path.join(d, "**", "*.npz"), recursive=True))]
    return out


def screen_label(label, margin, ps, cstep, maxviol, keep, kinds=("red",), mmax=324):
    """Screen one arbitrary source (used for the n > 324 certificates: only reductions that land at m <= 324)."""
    try:
        S, x, y, th = source(label)
        mo0, mw0 = max_violation(x, y, th, S + 1e-9)
        if max(mo0, mw0) > 1e-6:          # not a valid packing as read (corrupt download or different format): skip
            return []
    except Exception:  # noqa: BLE001
        return []
    n = len(x)
    if ps == "auto":                       # periods that land between side 7 and side 18
        k = int(math.floor(S + 1e-9))
        ps = tuple(range(max(1, k - 17), max(1, k - 17) + 11))
    leads = []
    for anti in (False, True):
        for p in ps:
            if S - p < 2.5:
                continue
            for c in np.arange(1.0, 2 * S - 1.0, cstep):
                x2, y2, t2, S2 = reduce_(S, x, y, th, p, c, anti)
                m = len(x2)
                if m < 26 or m > mmax or attack.R()[m]["proven_optimal"]:
                    continue
                gap = S2 - attack.rec(m)
                if gap >= margin:
                    continue
                mo, mw = max_violation(x2, y2, t2, S2 + 1e-9)
                v = max(mo, mw)
                if v > maxviol:
                    continue
                leads.append(dict(src=label, kind="red", p=p, c=float(c), anti=anti, m=m, S0=S2, rec=attack.rec(m), gap=gap, viol=float(v)))
    groups = {}
    for L in leads:
        groups.setdefault((L["p"], L["anti"], L["m"]), []).append(L)
    out = []
    for key, g in groups.items():
        g.sort(key=lambda L: L["viol"])
        picked = []
        for L in g:
            if all(abs(L["c"] - q["c"]) >= 0.5 for q in picked):
                picked.append(L)
            if len(picked) >= keep:
                break
        out.extend(picked)
    return out


def _inside(x, y, th, S, tol):
    h = 0.5 * (np.abs(np.cos(th)) + np.abs(np.sin(th)))
    return (x - h >= -tol) & (x + h <= S + tol) & (y - h >= -tol) & (y + h <= S + tol)


def reduce_(S, x, y, th, p, c, anti=False):
    if anti:                       # band along the other diagonal: mirror x
        x = S - x; th = -th
    s = x + y
    lo = s < c
    up = s >= c + 2 * p
    x2 = np.concatenate([x[lo], x[up] - p]); y2 = np.concatenate([y[lo], y[up] - p]); t2 = np.concatenate([th[lo], th[up]])
    S2 = S - p
    keep = _inside(x2, y2, t2, S2, 0.02)
    return x2[keep], y2[keep], t2[keep], S2


def extend_(S, x, y, th, p, c, anti=False):
    if anti:
        x = S - x; th = -th
    s = x + y
    lo = s < c
    up = ~lo
    tn = (th + np.pi / 4) % (np.pi / 2) - np.pi / 4
    tilted = np.abs(tn) > 0.02
    band = tilted & (s >= c - 2 * p) & (s < c)
    x2 = np.concatenate([x[lo], x[up] + p, x[band] + p]); y2 = np.concatenate([y[lo], y[up] + p, y[band] + p])
    t2 = np.concatenate([th[lo], th[up], th[band]])
    S2 = S + p
    # the grids of a main-diagonal band packing are anchored bottom-right and top-left: fill those first,
    # then whatever the other two corner grids can still add
    ax, ay = fill(S2, x2, y2, t2, 1e-6, 0, 6)
    x3 = np.concatenate([x2, ax]); y3 = np.concatenate([y2, ay]); t3 = np.concatenate([t2, np.zeros(len(ax))])
    bx, by = fill(S2, x3, y3, t3, 1e-6, 0, 9)
    x3 = np.concatenate([x3, bx]); y3 = np.concatenate([y3, by]); t3 = np.concatenate([t3, np.zeros(len(bx))])
    return x3, y3, t3, S2


def screen(nmin, nmax, margin, ps=(1, 2, 3, 4, 5, 6), cstep=0.25, maxviol=0.12, keep=1, kinds=("red", "ext")):
    leads = []
    N = max(attack.R())
    for n in range(nmin, nmax + 1):
        if abs(attack.rec(n) - round(attack.rec(n))) < 1e-12:
            continue                                    # plain grids: nothing diagonal to exploit
        S, x, y, th = attack.wit(n)
        tn = (th + np.pi / 4) % (np.pi / 2) - np.pi / 4
        if np.count_nonzero(np.abs(tn) > 0.02) == 0:
            continue
        for anti in (False, True):
            for p in ps:
                for c in np.arange(1.0, 2 * S - 1.0, cstep):
                    for kind in kinds:
                        if kind == "red":
                            if S - p < 2.5:
                                continue
                            x2, y2, t2, S2 = reduce_(S, x, y, th, p, c, anti)
                        else:
                            if n + 2 * p * int(S) > N + 40:
                                continue
                            x2, y2, t2, S2 = extend_(S, x, y, th, p, c, anti)
                        m = len(x2)
                        if m < 5 or m > N:
                            continue
                        mo, mw = max_violation(x2, y2, t2, S2 + 1e-9)
                        v = max(mo, mw)
                        if v > maxviol:
                            continue
                        # the table value this would have to beat (m squares; fewer squares can only be easier)
                        target = attack.rec(m)
                        if attack.R()[m]["proven_optimal"]:
                            continue
                        gap = S2 - target
                        if gap < margin:
                            leads.append(dict(src=n, kind=kind, p=p, c=float(c), anti=anti, m=m, S0=S2, rec=target, gap=gap, viol=float(v)))
    # keep, per (src, kind, p, anti, m), the lead with the smallest raw violation
    # keep, per (src, kind, p, anti, m), the `keep` leads with the smallest raw violation (distinct cuts)
    groups = {}
    for L in leads:
        groups.setdefault((L["src"], L["kind"], L["p"], L["anti"], L["m"]), []).append(L)
    out = []
    for key, g in groups.items():
        g.sort(key=lambda L: L["viol"])
        picked = []
        for L in g:
            if all(abs(L["c"] - q["c"]) >= 0.5 for q in picked):
                picked.append(L)
            if len(picked) >= keep:
                break
        out.extend(picked)
    out.sort(key=lambda L: (L["gap"] + L["viol"], L["viol"]))
    return out


def _opt(L):
    S, x, y, th = source(L["src"])
    f = reduce_ if L["kind"] == "red" else extend_
    x2, y2, t2, S2 = f(S, x, y, th, L["p"], L["c"], L["anti"])
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
    if r[3] < L["rec"] - 1e-9:
        out["file"] = attack.save_cand(L["m"], r[3], r[0], r[1], r[2], f"diag{L['kind']}_from{os.path.basename(str(L['src'])).replace('.cert','').replace('.json','').replace('.npz','')[:60]}_p{L['p']}_c{L['c']:.2f}_{'anti' if L['anti'] else 'main'}")
    elif r[3] < L["rec"] + 0.01:
        attack._save_seed(L["m"], r[3], r[0], r[1], r[2], f"diag{L['kind']}_from{os.path.basename(str(L['src'])).replace('.cert','').replace('.json','').replace('.npz','')[:60]}_p{L['p']}_c{L['c']:.2f}")
    return out


def deep(a):
    """Second pass: for every (source, kind, p, diagonal, m) whose best optimised result ended within
    a.deepmax of the record (but not on it), optimise ALL cuts that give that m, not just the two with
    the smallest raw overlap."""
    import glob
    res = []
    for f in glob.glob(os.path.join(RUN, "work", "diag_results*.json")):
        try:
            res.extend(json.load(open(f)))
        except Exception:  # noqa: BLE001
            pass
    near = {}
    for r in res:
        if r.get("S") is None:
            continue
        d = r["S"] - r["rec"]
        if 1e-6 < d < a.deepmax and abs(r["rec"] - round(r["rec"])) > 1e-9:
            key = (str(r["src"]), r["kind"], r["p"], r["anti"], r["m"])
            if key not in near or d < near[key]:
                near[key] = d
    print(f"deep: {len(near)} (source, op, p, diagonal, m) groups within {a.deepmax} of a record", flush=True)
    leads = []
    for (src, kind, p, anti, m), d in sorted(near.items(), key=lambda kv: kv[1]):
        label = src if src.startswith("cert:") else int(src)
        try:
            S, x, y, th = source(label)
        except Exception:  # noqa: BLE001
            continue
        f = reduce_ if kind == "red" else extend_
        for c in np.arange(1.0, 2 * S - 1.0, 0.05):
            x2, y2, t2, S2 = f(S, x, y, th, p, c, anti)
            if len(x2) != m:
                continue
            mo, mw = max_violation(x2, y2, t2, S2 + 1e-9)
            v = max(mo, mw)
            if v > 0.7:
                continue
            leads.append(dict(src=label, kind=kind, p=p, c=float(c), anti=anti, m=m, S0=S2, rec=attack.rec(m), gap=S2 - attack.rec(m), viol=float(v)))
    print(f"deep: {len(leads)} cuts to optimise", flush=True)
    t0 = time.time()
    out = []
    best = {}
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(_opt, leads, chunksize=1):
            out.append(r)
            if r.get("S") is None:
                continue
            key = (str(r["src"]), r["kind"], r["p"], r["m"])
            if key not in best or r["S"] < best[key] - 1e-9:
                best[key] = r["S"]
                flag = "  <<< BELOW RECORD" if r["S"] < r["rec"] - 1e-9 else ""
                print(f"[{time.time()-t0:6.0f}s] src {os.path.basename(str(r['src']))} {r['kind']} p={r['p']} c={r['c']:.2f} -> m={r['m']} S={r['S']:.9f} "
                      f"record {r['rec']:.9f} diff {r['S']-r['rec']:+.6f} (was {near[(str(r['src']), r['kind'], r['p'], r['anti'], r['m'])]:+.6f}){flag}", flush=True)
    json.dump(out, open(os.path.join(RUN, "work", f"diag_results_deep{a.tag}.json"), "w"), indent=0)
    ok = [r for r in out if r.get("S") is not None]
    bym = {}
    for r in ok:
        if r["m"] not in bym or r["S"] < bym[r["m"]]["S"]:
            bym[r["m"]] = r
    for m in sorted(bym):
        r = bym[m]
        attack.log_attempt(m, "diagper-deep: all cuts for near-miss diagonal reductions/extensions (not only the two with least raw overlap), "
                              "penalty repair + SLP polish (search/diagper.py deep)",
                           r["S"], None, sum(q["t"] for q in ok if q["m"] == m),
                           f"{sum(1 for q in out if q['m']==m)} cuts; best from source {os.path.basename(str(r['src']))} ({r['kind']}, p={r['p']}, c={r['c']:.2f}): "
                           f"S={r['S']:.9f} vs record {r['rec']:.9f}; " + ("BELOW RECORD, see work/cand" if r["S"] < r["rec"] - 1e-9 else "no improvement"))
    print(f"deep done: {len(ok)}/{len(out)} optimised; below record: {sum(1 for r in ok if r['S'] < r['rec'] - 1e-9)}; wall {time.time()-t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["screen", "run", "deep"])
    ap.add_argument("--deepmax", type=float, default=0.01)
    ap.add_argument("--nmin", type=int, default=26); ap.add_argument("--nmax", type=int, default=324)
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--maxviol", type=float, default=0.12)
    ap.add_argument("--net", type=float, default=0.01)
    ap.add_argument("--keeptrivial", action="store_true")
    ap.add_argument("--targets", default="all", choices=["all", "nontrivial", "trivial"])
    ap.add_argument("--certdir", default="", help="directory of third-party .cert files to use as sources (reductions only)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--cstep", type=float, default=0.25); ap.add_argument("--pmax", type=int, default=6); ap.add_argument("--keep", type=int, default=1)
    ap.add_argument("--pmin", type=int, default=1)
    ap.add_argument("--pauto", action="store_true"); ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--leadsfile", default=""); ap.add_argument("--maxleads", type=int, default=0)
    ap.add_argument("--kinds", default="red,ext")
    ap.add_argument("--labels", default="", help="comma list of explicit sources, e.g. json:/path/packing.json (reductions only)")
    a = ap.parse_args()
    if a.mode == "deep":
        deep(a)
        return
    t0 = time.time()
    ps = tuple(range(a.pmin, a.pmax + 1))
    if a.leadsfile:
        leads = json.load(open(a.leadsfile))
        print(f"loaded {len(leads)} screened leads from {a.leadsfile}", flush=True)
    elif a.certdir or a.labels:
        import glob
        if a.labels:                          # explicit sources: 'json:/path' (our float packings) or 'cert:/path'
            labels = [v for v in a.labels.split(",") if v]
        else:
            labels = dir_labels(a.certdir)
        print(f"{len(labels)} certificate sources from {a.certdir or 'explicit labels'}", flush=True)
        with mp.Pool(a.procs) as pool:
            parts = pool.starmap(screen_label, [(lab, a.margin, ("auto" if a.pauto else ps), a.cstep, a.maxviol, a.keep) for lab in labels], chunksize=1)
        leads = [L for part in parts for L in part]
        leads.sort(key=lambda L: (L["gap"] + L["viol"], L["viol"]))
    elif a.procs > 1:
        with mp.Pool(a.procs) as pool:      # the screen itself is parallel over the source n
            parts = pool.starmap(screen, [(n, n, a.margin, ps, a.cstep, a.maxviol, a.keep, tuple(a.kinds.split(","))) for n in range(a.nmin, a.nmax + 1)], chunksize=1)
        leads = [L for part in parts for L in part]
        leads.sort(key=lambda L: (L["gap"] + L["viol"], L["viol"]))
    else:
        leads = screen(a.nmin, a.nmax, a.margin, ps=ps, cstep=a.cstep, maxviol=a.maxviol, keep=a.keep)
    print(f"screen: {len(leads)} leads with (S0 - record) < {a.margin} in {time.time()-t0:.0f}s", flush=True)
    if a.leadsfile:
        pass
    else:
        json.dump(leads, open(os.path.join(RUN, "work", f"diag_leads{a.tag}.json"), "w"), indent=0)
    for L in leads[:60]:
        print(f"  src n={os.path.basename(str(L['src']))} {L['kind']} p={L['p']} c={L['c']:.2f} {'anti' if L['anti'] else 'main'} -> m={L['m']:3d} S0={L['S0']:.6f} "
              f"record {L['rec']:.6f} gap {L['gap']:+.5f} raw viol {L['viol']:.4f}", flush=True)
    if a.mode == "screen":
        return
    # optimise only leads that are not obviously the trivial grid again: raw gap + raw violation below a threshold
    if a.alpha != 1.0:        # optimise a lead only if (raw gap + alpha * raw overlap) is below the threshold
        leads = [L for L in leads if L["gap"] + a.alpha * L["viol"] < a.net]
        # drop plain reproductions and near-duplicates (many source files are variants of one arrangement), best first
        leads = [L for L in leads if not (L["gap"] > -1e-7 and L["viol"] < 1e-6)]
        seen = set(); uniq = []
        for L in sorted(leads, key=lambda L: L["gap"] + a.alpha * L["viol"]):
            key = (L["m"], L["p"], L["anti"], round(L["S0"], 5), round(L["viol"], 3))
            if key in seen:
                continue
            seen.add(key); uniq.append(L)
        leads = uniq
        if a.maxleads:
            leads = leads[: a.maxleads]
    elif a.keeptrivial:
        leads = [L for L in leads if L["gap"] + L["viol"] < a.net]
    else:
        leads = [L for L in leads if L["gap"] + L["viol"] < a.net and not (abs(L["rec"] - round(L["rec"])) < 1e-12 and abs(L["gap"] + L["viol"]) < 1e-6)]
    if a.targets == "nontrivial":
        leads = [L for L in leads if abs(L["rec"] - round(L["rec"])) > 1e-9]
    elif a.targets == "trivial":
        leads = [L for L in leads if abs(L["rec"] - round(L["rec"])) <= 1e-9]
    print(f"optimising {len(leads)} leads (net < {a.net}, trivial-grid coincidences skipped, targets={a.targets})", flush=True)
    res = []
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(_opt, leads, chunksize=1):
            res.append(r)
            if r.get("S") is not None:
                flag = "  <<< BELOW RECORD" if r["S"] < r["rec"] - 1e-9 else ""
                print(f"[{time.time()-t0:6.0f}s] src {os.path.basename(str(r['src']))} {r['kind']} p={r['p']} c={r['c']:.2f} -> m={r['m']} S={r['S']:.9f} record {r['rec']:.9f} "
                      f"diff {r['S']-r['rec']:+.6f} (raw gap {r['gap']:+.5f}, viol {r['viol']:.3f}){flag}", flush=True)
    ok = [r for r in res if r.get("S") is not None]
    bym = {}
    for r in ok:
        if r["m"] not in bym or r["S"] < bym[r["m"]]["S"]:
            bym[r["m"]] = r
    for m in sorted(bym):
        r = bym[m]
        attack.log_attempt(m, "diagper: diagonal-period closure (remove/insert one (p,p) period of a diagonal band in a published record, "
                              "penalty repair + SLP polish) (search/diagper.py)",
                           r["S"], None, sum(q["t"] for q in ok if q["m"] == m),
                           f"{sum(1 for q in res if q['m']==m)} leads for this m; best from source {os.path.basename(str(r['src']))} ({r['kind']}, p={r['p']}, c={r['c']:.2f}): "
                           f"S={r['S']:.9f} vs record {r['rec']:.9f}; " + ("BELOW RECORD, see work/cand" if r["S"] < r["rec"] - 1e-9 else "no improvement"))
    json.dump(res, open(os.path.join(RUN, "work", f"diag_results{a.tag}.json"), "w"), indent=0)
    print(f"done: {len(ok)}/{len(res)} leads optimised; below record: {sum(1 for r in ok if r['S'] < r['rec'] - 1e-9)}; wall {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
