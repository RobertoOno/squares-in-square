#!/usr/bin/env python3
"""
Turn a floating-point packing into an exact certificate that verify.py accepts.

Input JSON (floats allowed here):
  {"n": 17, "squares": [{"x": 0.5, "y": 0.5, "theta": 0.0}, ...]}
  x, y = centre; theta = rotation in radians.

Method (sound, not heuristic):
  1. snap each centre to a rational and each angle to a rational t ~ tan(theta/2)
     (exact unit squares by construction);
  2. if snapping created overlaps, scale all centres about their centroid by a
     rational lambda >= 1. Scaling centres apart never creates an overlap: if
     d = x_i - x_j lies outside int(K_j - K_i) (a convex set containing 0), so
     does lambda*d for lambda >= 1. So a small lambda always repairs rounding;
  3. translate so the packing touches x=0 and y=0, set S = max extent (exact).

The resulting S is an exact, certified upper bound for s(n). It is slightly
larger than the float S; raise --den for tighter certificates.

Usage:
  python3 certify.py float.json out_cert.json [--den 10**12]
Then ALWAYS run: python3 verify.py out_cert.json --compare records.json
"""
from __future__ import annotations

import json
import math
import sys
from fractions import Fraction as F

from verify import Sq, check, decimal  # read-only reuse of the frozen verifier


def snap(sqs_float, den: int):
    out = []
    for s in sqs_float:
        t = F(math.tan(float(s["theta"]) / 2)).limit_denominator(den)
        out.append((F(float(s["x"])).limit_denominator(den), F(float(s["y"])).limit_denominator(den), t))
    return out


def realise(snapped, lam: F):
    n = len(snapped)
    gx = sum(x for x, _, _ in snapped) / n
    gy = sum(y for _, y, _ in snapped) / n
    sqs, raw = [], []
    for x, y, t in snapped:
        cx, cy = gx + lam * (x - gx), gy + lam * (y - gy)
        d = 1 + t * t
        sqs.append(Sq(cx, cy, (1 - t * t) / d, 2 * t / d))
        raw.append((cx, cy, t))
    minx = min(v[0] for sq in sqs for v in sq.verts)
    miny = min(v[1] for sq in sqs for v in sq.verts)
    maxx = max(v[0] for sq in sqs for v in sq.verts)
    maxy = max(v[1] for sq in sqs for v in sq.verts)
    S = max(maxx - minx, maxy - miny)
    shifted = [Sq(sq.cx - minx, sq.cy - miny, sq.c, sq.s) for sq in sqs]
    raw = [(cx - minx, cy - miny, t) for cx, cy, t in raw]
    return S, shifted, raw


def overlaps_only(n, S, sqs):
    return [e for e in check(n, S, sqs) if "overlap" in e]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    den = 10 ** 12
    if "--den" in argv:
        den = int(eval(argv[argv.index("--den") + 1], {"__builtins__": {}}))
    data = json.load(open(argv[1]))
    sqs_f = data["squares"]
    n = data.get("n", len(sqs_f))
    if n != len(sqs_f):
        print(f"n={n} but {len(sqs_f)} squares given")
        return 1
    snapped = snap(sqs_f, den)

    lam = F(1)
    S, sqs, raw = realise(snapped, lam)
    if overlaps_only(n, S, sqs):
        # exponential search for a repairing lambda, then bisect down
        step = F(1, den // 1000 or 1)
        hi = 1 + step
        while True:
            S, sqs, raw = realise(snapped, hi)
            if not overlaps_only(n, S, sqs):
                break
            step *= 4
            hi = 1 + step
            if step > 1:
                print("could not repair overlaps: the float solution itself overlaps (not a rounding issue)")
                return 1
        lo = F(1)
        for _ in range(40):
            mid = (lo + hi) / 2
            mid = mid.limit_denominator(den * 1000)
            S_m, sqs_m, _ = realise(snapped, mid)
            if overlaps_only(n, S_m, sqs_m):
                lo = mid
            else:
                hi = mid
        lam = hi
        S, sqs, raw = realise(snapped, lam)

    problems = check(n, S, sqs)
    if problems:
        print("internal error, certificate fails:", problems[:5])
        return 1
    cert = {
        "n": n,
        "side": f"{S.numerator}/{S.denominator}",
        "side_decimal_info_only": decimal(S, 20),
        "squares": [{"cx": f"{cx.numerator}/{cx.denominator}",
                     "cy": f"{cy.numerator}/{cy.denominator}",
                     "t": f"{t.numerator}/{t.denominator}"} for cx, cy, t in raw],
    }
    json.dump(cert, open(argv[2], "w"), indent=1)
    print(f"wrote {argv[2]}: n={n} S={decimal(S, 15)} (lambda-1 = {float(lam - 1):.3e})")
    print("now run: python3 verify.py", argv[2], "--compare records.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
