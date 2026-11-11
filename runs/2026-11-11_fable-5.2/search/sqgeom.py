"""Float geometry kernel for unit squares in a square (numba).

A square is (x, y, th): centre and rotation angle. Two unit squares with interiors disjoint
iff  max_k |D . u_k| >= R(delta),  where D = c_j - c_i, u_k runs over the 4 edge normals
(2 per square), delta = th_j - th_i and R = (1 + |cos delta| + |sin delta|) / 2.
(Separating axis theorem; for two unit squares all four axes have the same radius sum R.)

Nothing here is a judge: results only count after ../../verify.py accepts a certificate.
"""
import math

import numpy as np
from numba import njit


@njit(cache=True, fastmath=False)
def half_extent(th):
    return 0.5 * (abs(math.cos(th)) + abs(math.sin(th)))


@njit(cache=True)
def pair_sep(xi, yi, ti, xj, yj, tj):
    """Signed separation (>= 0 means interiors disjoint); also returns the best axis index 0..3
    (0,1: axes of i; 2,3: axes of j) and the sign of D.u on that axis."""
    dx = xj - xi
    dy = yj - yi
    d = tj - ti
    R = 0.5 * (1.0 + abs(math.cos(d)) + abs(math.sin(d)))
    ci, si = math.cos(ti), math.sin(ti)
    cj, sj = math.cos(tj), math.sin(tj)
    p0 = dx * ci + dy * si
    p1 = -dx * si + dy * ci
    p2 = dx * cj + dy * sj
    p3 = -dx * sj + dy * cj
    best = abs(p0)
    k = 0
    sg = 1.0 if p0 >= 0 else -1.0
    if abs(p1) > best:
        best = abs(p1); k = 1; sg = 1.0 if p1 >= 0 else -1.0
    if abs(p2) > best:
        best = abs(p2); k = 2; sg = 1.0 if p2 >= 0 else -1.0
    if abs(p3) > best:
        best = abs(p3); k = 3; sg = 1.0 if p3 >= 0 else -1.0
    return best - R, k, sg


@njit(cache=True)
def energy_grad(x, y, th, S, gx, gy, gt):
    """Penalty energy E = sum_pairs depth^2 + sum walls viol^2; fills gradients; returns (E, dE/dS)."""
    n = x.shape[0]
    E = 0.0
    gS = 0.0
    for i in range(n):
        gx[i] = 0.0
        gy[i] = 0.0
        gt[i] = 0.0
    c = np.empty(n)
    s = np.empty(n)
    for i in range(n):
        c[i] = math.cos(th[i])
        s[i] = math.sin(th[i])
    for i in range(n):
        # walls
        ac = abs(c[i]); as_ = abs(s[i])
        h = 0.5 * (ac + as_)
        # dh/dth = 0.5*(-sign(c) s + sign(s) c)
        dh = 0.5 * ((-s[i] if c[i] >= 0 else s[i]) + (c[i] if s[i] >= 0 else -c[i]))
        v = h - x[i]
        if v > 0:
            E += v * v; gx[i] -= 2 * v; gt[i] += 2 * v * dh
        v = x[i] + h - S
        if v > 0:
            E += v * v; gx[i] += 2 * v; gt[i] += 2 * v * dh; gS -= 2 * v
        v = h - y[i]
        if v > 0:
            E += v * v; gy[i] -= 2 * v; gt[i] += 2 * v * dh
        v = y[i] + h - S
        if v > 0:
            E += v * v; gy[i] += 2 * v; gt[i] += 2 * v * dh; gS -= 2 * v
        xi = x[i]; yi = y[i]; ci = c[i]; si = s[i]
        for j in range(i + 1, n):
            dx = x[j] - xi
            dy = y[j] - yi
            if dx * dx + dy * dy >= 2.0:
                continue
            cj = c[j]; sj = s[j]
            cd = cj * ci + sj * si      # cos(delta)
            sd = sj * ci - cj * si      # sin(delta)
            R = 0.5 * (1.0 + abs(cd) + abs(sd))
            p0 = dx * ci + dy * si
            p1 = -dx * si + dy * ci
            p2 = dx * cj + dy * sj
            p3 = -dx * sj + dy * cj
            a0 = abs(p0); a1 = abs(p1); a2 = abs(p2); a3 = abs(p3)
            best = a0; k = 0
            if a1 > best:
                best = a1; k = 1
            if a2 > best:
                best = a2; k = 2
            if a3 > best:
                best = a3; k = 3
            dep = R - best
            if dep <= 0:
                continue
            E += dep * dep
            # dR/d(delta)
            dR = 0.5 * ((-sd if cd >= 0 else sd) + (cd if sd >= 0 else -cd))
            w = 2.0 * dep
            # depth = R - sg * p_k ; gradient of p_k
            if k == 0:
                sg = 1.0 if p0 >= 0 else -1.0
                ux = ci; uy = si
                # dp0/dth_i = -dx*si + dy*ci = p1
                gt[i] += w * (-sg * p1)
            elif k == 1:
                sg = 1.0 if p1 >= 0 else -1.0
                ux = -si; uy = ci
                # dp1/dth_i = -dx*ci - dy*si = -p0
                gt[i] += w * (sg * p0)
            elif k == 2:
                sg = 1.0 if p2 >= 0 else -1.0
                ux = cj; uy = sj
                gt[j] += w * (-sg * p3)
            else:
                sg = 1.0 if p3 >= 0 else -1.0
                ux = -sj; uy = cj
                gt[j] += w * (sg * p2)
            # d depth / d c_j = -sg*u ; d c_i = +sg*u
            gx[j] -= w * sg * ux
            gy[j] -= w * sg * uy
            gx[i] += w * sg * ux
            gy[i] += w * sg * uy
            gt[j] += w * dR
            gt[i] -= w * dR
    return E, gS


@njit(cache=True)
def max_violation(x, y, th, S):
    """(max pair penetration depth, max wall violation); both <= 0 means valid."""
    n = x.shape[0]
    mo = -1e9
    mw = -1e9
    for i in range(n):
        h = 0.5 * (abs(math.cos(th[i])) + abs(math.sin(th[i])))
        mw = max(mw, h - x[i], x[i] + h - S, h - y[i], y[i] + h - S)
        for j in range(i + 1, n):
            dx = x[j] - x[i]; dy = y[j] - y[i]
            if dx * dx + dy * dy >= 2.0:
                continue
            sep, k, sg = pair_sep(x[i], y[i], th[i], x[j], y[j], th[j])
            if -sep > mo:
                mo = -sep
    return mo, mw


@njit(cache=True)
def bbox(x, y, th):
    n = x.shape[0]
    x0 = 1e18; x1 = -1e18; y0 = 1e18; y1 = -1e18
    for i in range(n):
        h = 0.5 * (abs(math.cos(th[i])) + abs(math.sin(th[i])))
        x0 = min(x0, x[i] - h); x1 = max(x1, x[i] + h)
        y0 = min(y0, y[i] - h); y1 = max(y1, y[i] + h)
    return x0, x1, y0, y1


def normalize(x, y, th):
    """Translate to touch x=0,y=0; return side of bounding square. Angles reduced to (-pi/4, pi/4]."""
    th = np.mod(th + np.pi / 4, np.pi / 2) - np.pi / 4
    x0, x1, y0, y1 = bbox(x, y, th)
    return x - x0, y - y0, th, max(x1 - x0, y1 - y0)
