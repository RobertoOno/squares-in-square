#!/usr/bin/env python3
"""Write attempt lines for a closure pass that was stopped before it wrote its own (the pass logs one
line per target m only when it ends).  Values are reconstructed from the pass log (9 decimals).
Usage: log_stopped_pass.py LOGFILE --pod A --procs 10 --what "text" [--dry]"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("log"); ap.add_argument("--pod", default="A"); ap.add_argument("--procs", type=int, default=10)
ap.add_argument("--what", default=""); ap.add_argument("--dry", action="store_true")
a = ap.parse_args()
txt = open(a.log, errors="replace").read()
pat = re.compile(r"\[\s*(\d+)s\] src (\S+) (red|ext|cross) p=(\d+) c=([\d.]+)(?: b=([\d.]+))? -> m=(\d+) S=([\d.]+) record ([\d.]+) diff ([+-][\d.]+)")
sel = re.search(r"optimising (\d+) leads", txt)
rows = [m.groups() for m in pat.finditer(txt)]
if not rows:
    sys.exit("no optimised leads in " + a.log)
tmax = max(int(r[0]) for r in rows)
bym = {}
for t, src, kind, p, c, b, m, S, rec, diff in rows:
    m = int(m); S = float(S); rec = float(rec)
    e = bym.setdefault(m, dict(cnt=0, best=None))
    e["cnt"] += 1
    if e["best"] is None or S < e["best"][0]:
        e["best"] = (S, rec, src, kind, p, c)
core = tmax * a.procs
lines = []
for m in sorted(bym):
    S, rec, src, kind, p, c = bym[m]["best"]
    below = S < rec - 1e-8
    lines.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n": m,
                  "method": f"{'crossper' if kind == 'cross' else 'diagper'}: {a.what} (pass stopped before its own summary; line reconstructed from the pass log)",
                  "best_float_S": S, "certified_S": None, "wall_seconds": round(core * bym[m]["cnt"] / len(rows), 1),
                  "note": f"[RunPod pod {a.pod}] {bym[m]['cnt']} leads for this m ({len(rows)} of {sel.group(1) if sel else '?'} selected leads were optimised in {tmax}s on {a.procs} processes; "
                          f"wall_seconds is that core time apportioned by lead count); best from source {src} ({kind}, p={p}, c={c}): S={S:.9f} vs record {rec:.9f}; "
                          + ("BELOW RECORD: the same value as the certified candidate for this n, reached from another published source" if below else "no improvement")})
print(f"{a.log}: {len(rows)} leads, {len(bym)} targets, below record: {sorted(m for m in bym if bym[m]['best'][0] < bym[m]['best'][1] - 1e-8)}")
if not a.dry:
    with open(os.path.join(RUN, "attempts.jsonl"), "a") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")
    print("appended", len(lines), "lines")
