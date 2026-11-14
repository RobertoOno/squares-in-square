#!/usr/bin/env python3
"""Write attempts.jsonl lines for basin-hopping runs that the agent stopped before they finished
(a finished run logs itself). Summaries are reconstructed from the periodic progress lines in
work/logs/*.log. Idempotent: a marker file lists the logs already handled."""
import glob
import json
import os
import re
import time

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
marker = os.path.join(RUN, "work", "logs", "_stopped_hops_logged.json")
done = set(json.load(open(marker))) if os.path.exists(marker) else set()
added = 0
for path in sorted(glob.glob(os.path.join(RUN, "work", "logs", "*.log"))):
    name = os.path.basename(path)
    if name in done:
        continue
    txt = open(path, errors="replace").read()
    rows = re.findall(r"\[hop n=(\d+) seed=(\d+) t=(\d+)s\] cur=([\d.]+) best=([\d.]+) rec=([\d.]+) nloc=(\d+)", txt)
    if not rows:
        continue
    if re.search(r"^n=\d+ best [\d.]+ record [\d.]+ wall", txt, flags=re.M):
        done.add(name)                      # finished normally: it logged itself
        continue
    n = int(rows[0][0])
    best = min(float(r[4]) for r in rows)
    rec = float(rows[0][5])
    last = {}
    for r in rows:
        last[r[1]] = (int(r[2]), int(r[6]))
    tmax = max(v[0] for v in last.values())
    nloc = sum(v[1] for v in last.values())
    line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n": n,
            "method": "hop: basin hopping (penalty continuation + SLP polish per step) (search/attack.py hop), run stopped early by the agent",
            "best_float_S": best, "certified_S": None, "wall_seconds": tmax * len(last),
            "note": f"log {name}: {len(last)} chains, last progress at {tmax}s, >= {nloc} local optimisations; best {best:.7f} vs record {rec:.7f}; "
                    + ("BELOW RECORD" if best < rec - 1e-7 else "no improvement") + " (summary reconstructed from the progress log)"}
    with open(os.path.join(RUN, "attempts.jsonl"), "a") as f:
        f.write(json.dumps(line) + "\n")
    done.add(name)
    added += 1
json.dump(sorted(done), open(marker, "w"))
print("logged", added, "stopped runs")
