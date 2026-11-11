#!/usr/bin/env python3
"""Clarify reconstructed basin-hopping log lines whose 7-decimal progress value coincides with the record:
they are NOT below the record (the progress log prints 7 decimals). Idempotent."""
import json
import os
from fractions import Fraction as F

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = {r["n"]: r for r in json.load(open(os.path.join(RUN, "records.json")))["records"]}
p = os.path.join(RUN, "attempts.jsonl")
rows = [json.loads(l) for l in open(p) if l.strip()]
TAG = " [value read from a progress log printed to 7 decimals: equal to the record within rounding, not below it]"
k = 0
for r in rows:
    b = r.get("best_float_S")
    if b is None or r["n"] not in R or "reconstructed from the progress log" not in str(r.get("note", "")):
        continue
    rec = float(F(R[r["n"]]["upper"]))
    if abs(float(b) - rec) < 6e-8 and TAG not in r["note"]:
        r["note"] = r["note"].replace("BELOW RECORD", "no improvement") + TAG
        k += 1
with open(p, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print("annotated", k, "lines")
