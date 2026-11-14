#!/usr/bin/env python3
"""Render packings to PNG (diagnostic only). Usage: render.py out.png title:json_path_or_witness_n ..."""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)


def draw(ax, S, x, y, th, title=""):
    ax.set_xlim(-0.05, S + 0.05); ax.set_ylim(-0.05, S + 0.05); ax.set_aspect("equal")
    ax.add_patch(Polygon([(0, 0), (S, 0), (S, S), (0, S)], closed=True, fill=False, ec="k", lw=1.2))
    for i in range(len(x)):
        c, s = math.cos(th[i]), math.sin(th[i])
        pts = [(x[i] + a * c - b * s, y[i] + a * s + b * c) for a, b in ((.5, .5), (-.5, .5), (-.5, -.5), (.5, -.5))]
        t = (th[i] + math.pi / 4) % (math.pi / 2) - math.pi / 4
        if abs(t) < 1e-7:
            col = "#d9d9d9"
        elif abs(abs(t) - math.pi / 4) < 1e-7:
            col = "#9ecae1"
        else:
            col = plt.cm.autumn(min(1.0, abs(t) / (math.pi / 4)))
        ax.add_patch(Polygon(pts, closed=True, fc=col, ec="k", lw=0.4))
    ax.set_title(title, fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])


def load(spec):
    if spec.isdigit():
        W = json.load(open(os.path.join(RUN, "work", "witness_float.json")))[spec]
        return W["side"], np.array(W["x"]), np.array(W["y"]), np.array(W["th"])
    d = json.load(open(spec))
    if "squares" in d:
        x = np.array([q["x"] for q in d["squares"]]); y = np.array([q["y"] for q in d["squares"]])
        th = np.array([q["theta"] for q in d["squares"]])
        return d.get("S", float(max(x.max(), y.max()) + 0.71)), x, y, th
    return d["S"], np.array(d["x"]), np.array(d["y"]), np.array(d["th"])


if __name__ == "__main__":
    out = sys.argv[1]
    specs = sys.argv[2:]
    k = len(specs)
    cols = min(k, 3)
    rows = (k + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 5.4 * rows), squeeze=False)
    for a in axes.flat:
        a.axis("off")
    for i, sp in enumerate(specs):
        title, _, path = sp.partition(":")
        S, x, y, th = load(path)
        ax = axes[i // cols][i % cols]
        ax.axis("on")
        draw(ax, S, x, y, th, f"{title}  n={len(x)}  S={S:.6f}")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print("wrote", out)
