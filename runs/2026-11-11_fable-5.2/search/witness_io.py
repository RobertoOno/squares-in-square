"""Load the published best-known packings (Squares Project witnesses, downloaded into
work/web/sqproj/witnesses/) as float arrays. Used ONLY in phase 3 as baselines / starting
points and for table-consistency checks. Phase 2 (calibration) never touches these.
"""
import math
import os
from fractions import Fraction as F

import numpy as np
import yaml

try:
    from yaml import CSafeLoader as _L
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as _L

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WDIR = os.path.join(RUN, "work", "web", "sqproj", "witnesses")


def _alpha(scalar):
    """Real root of the field's minimal polynomial inside its isolating interval (mpmath, 60 digits)."""
    import mpmath as mp
    mp.mp.dps = 60
    coef = [F(c) for c in scalar["minimal_polynomial"]]
    lo, hi = [F(v) for v in scalar["isolating_interval"]]
    best = None
    for cs in (coef, coef[::-1]):           # highest-first or lowest-first: keep the one with a root in the interval
        try:
            roots = mp.polyroots([mp.mpf(c.numerator) / c.denominator for c in cs], maxsteps=500, extraprec=200)
        except Exception:
            continue
        for r in roots:
            if abs(mp.im(r)) < mp.mpf(10) ** -30:
                rr = mp.re(r)
                if mp.mpf(lo.numerator) / lo.denominator - mp.mpf(10) ** -25 <= rr <= mp.mpf(hi.numerator) / hi.denominator + mp.mpf(10) ** -25:
                    best = rr
        if best is not None:
            break
    if best is None:
        raise ValueError("no root in isolating interval")
    return best


def _val(e, alpha):
    """Element -> float. e is a rational/decimal string, a number, or a list of field coefficients (low order first)."""
    if isinstance(e, list):
        import mpmath as mp
        acc = mp.mpf(0)
        p = mp.mpf(1)
        for c in e:
            fc = F(str(c))
            acc += mp.mpf(fc.numerator) / fc.denominator * p
            p *= alpha
        return float(acc)
    s = str(e)
    if "/" in s:
        f = F(s)
        return f.numerator / f.denominator if max(f.numerator.bit_length(), f.denominator.bit_length()) > 900 else float(f)
    return float(s)


def load_witness(n):
    """Return (side, x, y, th) as floats (numpy arrays), exactly as published (no cleanup)."""
    w = yaml.load(open(os.path.join(WDIR, f"n-{n:03d}.yaml")), Loader=_L)["witness"]
    rep = w["representation"]
    scalar = w.get("scalar") or {}
    alpha = _alpha(scalar) if scalar.get("kind") == "algebraic-number-field" else None
    side = _val(w["side"], alpha)
    xs, ys, ts = [], [], []
    unit = (w.get("coordinates") or {}).get("angle_unit")
    for sq in w["squares"]:
        if rep == "corners":
            c = [(_val(p[0], alpha), _val(p[1], alpha)) for p in sq["corners"]]
            cx = sum(p[0] for p in c) / 4.0
            cy = sum(p[1] for p in c) / 4.0
            th = math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0])
        elif rep == "center-angle":
            cx, cy = _val(sq["center"][0], alpha), _val(sq["center"][1], alpha)
            a = float(str(sq["angle"]))
            th = math.radians(a) if unit == "degrees" else a
        elif rep == "center-basis":
            cx, cy = _val(sq["center"][0], alpha), _val(sq["center"][1], alpha)
            bx, by = _val(sq["basis"][0], alpha), _val(sq["basis"][1], alpha)
            th = math.atan2(by, bx)
        else:
            raise ValueError(rep)
        xs.append(cx); ys.append(cy); ts.append(th)
    assert len(xs) == w["n"] == n
    return side, np.array(xs), np.array(ys), np.array(ts)


if __name__ == "__main__":
    import json
    import sys
    import time
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sqgeom import max_violation, normalize
    recs = {r["n"]: r for r in json.load(open(os.path.join(RUN, "records.json")))["records"]}
    out = {}
    bad = 0
    t0 = time.time()
    for n in range(1, 325):
        side, x, y, th = load_witness(n)
        mo, mw = max_violation(x, y, th, side)
        xn, yn, tn, sb = normalize(x.copy(), y.copy(), th.copy())
        out[n] = dict(side=side, x=x.tolist(), y=y.tolist(), th=th.tolist())
        flag = ""
        if mo > 1e-7 or mw > 1e-7:
            flag = " <<< VIOLATION"
            bad += 1
        if flag or abs(sb - side) > 1e-7 or n % 40 == 0:
            print(f"n={n:3d} side={side:.12f} bbox={sb:.12f} max_overlap={mo:.2e} max_wall={mw:.2e} rec={recs[n]['upper']}{flag}")
    json.dump(out, open(os.path.join(RUN, "work", "witness_float.json"), "w"))
    print("loaded 324 witnesses in %.1fs; violations: %d" % (time.time() - t0, bad))
