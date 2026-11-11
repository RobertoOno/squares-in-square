#!/usr/bin/env python3
"""Softness indicators for every open n: position in its band, age/method of the record, and how far
the record sits above the trend of its neighbours in the (k, j) table, n = k^2 + j, g = record - k."""
import json, math, os, sys
from fractions import Fraction as F
HERE = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(HERE)
R = {r["n"]: r for r in json.load(open(os.path.join(RUN, "records.json")))["records"]}
C = {int(k): v for k, v in json.load(open(os.path.join(RUN, "work", "web", "sqproj_cases.json"))).items()}
rec = {n: float(F(R[n]["upper"])) for n in R}
def g(k, j):
    n = k * k + j
    if n not in rec or j < 1 or j > 2 * k: return None
    return rec[n] - k
rows = []
for n in sorted(R):
    r = R[n]
    if r["proven_optimal"]: continue
    k = math.isqrt(n - 1); j = n - k * k           # n = k^2 + j, 1 <= j <= 2k+1
    if k < 2: continue
    gv = rec[n] - k
    trivial = abs(rec[n] - round(rec[n])) < 1e-12
    ru = C[n]["reported_upper_bound"]
    year = ru.get("found_year"); who = ", ".join(ru.get("found_by") or []) or "(extension/trivial)"
    sd = str(ru.get("source_date") or "")
    recent = sd.startswith("2026-09") or sd.startswith("2026-10") or sd.startswith("2026-11")
    # neighbours
    up = g(k + 1, j); dn = g(k - 1, j) if j <= 2 * (k - 1) else None
    lf = g(k, j - 1) if j > 1 else 0.0
    rt = g(k, j + 1)
    est = []
    if up is not None and dn is not None: est.append((up + dn) / 2)
    if lf is not None and rt is not None: est.append((lf + rt) / 2)
    resid = gv - (sum(est) / len(est)) if est else None
    plateau_k = dn is not None and abs(dn - gv) < 1e-9       # pure L-extension of the k-1 entry
    same_as_next = rt is not None and abs(rt - gv) < 1e-9
    step_next = (rt - gv) if rt is not None else None
    rows.append(dict(n=n, k=k, j=j, rec=rec[n], g=gv, lower=float(r["lower"]), gap=rec[n] - float(r["lower"]),
                     who=who, year=year, recent=recent, trivial=trivial, resid=resid, plateau=plateau_k,
                     same_as_next=same_as_next, step_next=step_next, method=ru.get("construction_method")))
json.dump(rows, open(os.path.join(RUN, "work", "targets_table.json"), "w"), indent=1)
if __name__ == "__main__":
    nt = [r for r in rows if not r["trivial"]]
    print(len(rows), "open n;", len(nt), "with a non-trivial record;", sum(r["recent"] for r in nt), "of those set since 2026-09")
    print("\nnon-trivial, NOT improved since Sep 2026, sorted by residual above neighbour trend:")
    old = [r for r in nt if not r["recent"]]
    old.sort(key=lambda r: -(r["resid"] if r["resid"] is not None else -9))
    for r in old:
        print(f"n={r['n']:3d} k={r['k']:2d} j={r['j']:2d} rec={r['rec']:.6f} g={r['g']:.4f} resid={r['resid'] if r['resid'] is None else round(r['resid'],4)} "
              f"plateau={int(r['plateau'])} same_next={int(r['same_as_next'])} step_next={None if r['step_next'] is None else round(r['step_next'],4)} gapLB={r['gap']:.3f} {r['who']} {r['year']} {r['method']}")
