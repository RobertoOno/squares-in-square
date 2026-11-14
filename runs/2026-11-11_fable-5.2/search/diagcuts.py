#!/usr/bin/env python3
"""All cuts for one (source, p) diagonal reduction that leave exactly m squares; optimise each.
Usage: diagcuts.py SOURCE P M [--procs N]   SOURCE = record n, or a .cert file, or a glob of .cert files"""
import argparse
import glob
import json
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
from sqgeom import max_violation  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("p", type=int); ap.add_argument("m", type=int)
    ap.add_argument("--procs", type=int, default=8); ap.add_argument("--maxviol", type=float, default=0.8)
    a = ap.parse_args()
    labels = [int(a.source)] if a.source.isdigit() else ["cert:" + f for f in sorted(glob.glob(a.source))]
    leads = []
    for lab in labels:
        try:
            S, x, y, th = diagper.source(lab)
        except Exception as e:  # noqa: BLE001
            print("skip", lab, e); continue
        for anti in (False, True):
            for c in np.arange(1.0, 2 * S - 1.0, 0.05):
                x2, y2, t2, S2 = diagper.reduce_(S, x, y, th, a.p, c, anti)
                if len(x2) != a.m:
                    continue
                mo, mw = max_violation(x2, y2, t2, S2 + 1e-9)
                v = max(mo, mw)
                if v <= a.maxviol:
                    leads.append(dict(src=lab, kind="red", p=a.p, c=float(c), anti=anti, m=a.m, S0=S2, rec=attack.rec(a.m), gap=S2 - attack.rec(a.m), viol=float(v)))
    print(f"{len(leads)} cuts from {len(labels)} source(s) leave m={a.m}", flush=True)
    t0 = time.time()
    best = None
    res = []
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(diagper._opt, leads, chunksize=1):
            res.append(r)
            if r.get("S") is not None and (best is None or r["S"] < best - 1e-10):
                best = r["S"]
                print(f"[{time.time()-t0:5.0f}s] {os.path.basename(str(r['src']))} c={r['c']:.2f} {'anti' if r['anti'] else 'main'}: S={r['S']:.10f} record {r['rec']:.10f} diff {r['S']-r['rec']:+.7f} (raw viol {r['viol']:.3f})", flush=True)
    ok = [r for r in res if r.get("S") is not None]
    print(f"done: {len(ok)}/{len(res)} optimised; best {best}; distinct values (1e-6): {sorted(set(round(r['S'],6) for r in ok))[:12]}")
    attack.log_attempt(a.m, "diagcuts: every cut position for one diagonal-period reduction (search/diagcuts.py)", best, None, time.time() - t0,
                       f"source {a.source}, p={a.p}: {len(res)} cuts, {len(ok)} optimised; record {attack.rec(a.m):.9f}; "
                       + ("BELOW RECORD, see work/cand" if best is not None and best < attack.rec(a.m) - 1e-9 else "no improvement"))


if __name__ == "__main__":
    main()
