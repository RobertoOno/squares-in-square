#!/usr/bin/env python3
"""Append the attempt lines written on the remote pods (work/remote/{A,B}/attempts.jsonl, pulled by
work/remote/sync.sh) to the run's attempts.jsonl exactly once (a marker file remembers how many
lines of each remote log were already merged). The note of each merged line is tagged with the pod."""
import json
import os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
marker = os.path.join(RUN, "work", "remote", "merged_counts.json")
done = json.load(open(marker)) if os.path.exists(marker) else {}
added = 0
with open(os.path.join(RUN, "attempts.jsonl"), "a") as out:
    for pod in ("A", "B"):
        p = os.path.join(RUN, "work", "remote", pod, "attempts.jsonl")
        if not os.path.exists(p):
            continue
        lines = [l for l in open(p).read().split("\n") if l.strip()]
        for l in lines[done.get(pod, 0):]:
            d = json.loads(l)
            d["note"] = f"[RunPod pod {pod}] " + str(d.get("note", ""))
            out.write(json.dumps(d) + "\n")
            added += 1
        done[pod] = len(lines)
json.dump(done, open(marker, "w"))
print("merged", added, "remote attempt lines; totals", done)
