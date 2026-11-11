#!/usr/bin/env python3
"""Refine near-miss seeds: for every target m whose best diagonal-period result ended within --max of
the record (but not on it), run a few basin-hopping chains from that seed.
Usage: refine_near.py [--max 0.004] [--chains 4] [--time 480] [--procs 30] [--also-below]"""
import argparse
import glob
import multiprocessing as mp
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("SQ_MOVES", "poly")
import attack  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=float, default=0.004); ap.add_argument("--chains", type=int, default=4)
    ap.add_argument("--time", type=float, default=480); ap.add_argument("--procs", type=int, default=30)
    ap.add_argument("--temp", type=float, default=0.0008); ap.add_argument("--also-below", action="store_true")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--min", type=float, default=2e-6, help="skip seeds closer than this to the record (same arrangement as the record)")
    ap.add_argument("--nmin", type=int, default=26)
    ap.add_argument("--list", action="store_true", help="only print the chosen seed files")
    a = ap.parse_args()
    excl = set(int(v) for v in a.exclude.split(",") if v)
    best = {}
    files = glob.glob(os.path.join(RUN, "work", "seeds", "n*_S*_diag*.json")) + glob.glob(os.path.join(RUN, "work", "cand", "n*_S*_diag*.json"))
    for f in files:
        m = re.match(r"n(\d+)_S([0-9.]+)_", os.path.basename(f))
        if not m:
            continue
        n = int(m.group(1)); S = float(m.group(2))
        if n in excl or n < a.nmin or n not in attack.R() or attack.R()[n]["proven_optimal"]:
            continue
        if abs(attack.rec(n) - round(attack.rec(n))) < 1e-9:
            continue
        d = S - attack.rec(n)
        lo = -1.0 if a.also_below else a.min
        if lo < d < a.max and (n not in best or S < best[n][0]):
            best[n] = (S, f)
    if a.list:
        for n, (S, f) in sorted(best.items()):
            print(f)
        return
    print(f"{len(best)} targets to refine:", sorted((n, round(v[0] - attack.rec(n), 6)) for n, v in best.items()), flush=True)
    tasks = []
    for n, (S, f) in sorted(best.items(), key=lambda kv: kv[1][0] - attack.rec(kv[0])):
        for i in range(a.chains):
            tasks.append((n, f, 9000 + 100 * n + i, a.time, a.temp, f"rf{n}", f"hop_rf{n}"))
    t0 = time.time()
    res = {}
    with mp.Pool(a.procs) as pool:
        for r in pool.imap_unordered(attack._hop_task, tasks, chunksize=1):
            res.setdefault(r["n"], []).append(r)
            if len(res[r["n"]]) == a.chains:
                b = min(q["best"] for q in res[r["n"]])
                rec = attack.rec(r["n"])
                flag = "  <<< BELOW RECORD" if b < rec - 1e-9 else ""
                print(f"[{time.time()-t0:6.0f}s] n={r['n']}: seed {best[r['n']][0]:.8f} -> best {b:.8f} record {rec:.8f} diff {b-rec:+.2e}{flag}", flush=True)
                attack.log_attempt(r["n"], "refine: basin hopping (band-shape moves) from the best diagonal-period seed (search/refine_near.py)",
                                   b, None, sum(q["t"] for q in res[r["n"]]),
                                   f"{a.chains} chains x {a.time:.0f}s from {os.path.basename(best[r['n']][1])} (seed {best[r['n']][0]:.8f}); record {rec:.9f}; "
                                   + ("BELOW RECORD, see work/cand" if flag else "no improvement"))
    print("refine done, wall %.0fs" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
