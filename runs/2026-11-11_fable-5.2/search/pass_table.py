#!/usr/bin/env python3
"""Markdown table of the closure passes (diagper / crossper / diagcuts) from their logs.
Usage: pass_table.py LOGDIR [LOGDIR ...]"""
import glob
import os
import re
import sys

rows = []
for d in sys.argv[1:]:
    pod = "A" if "/A/" in d + "/" else ("B" if "/B/" in d + "/" else "local")
    for f in sorted(glob.glob(os.path.join(d, "*.log"))):
        name = os.path.basename(f)[:-4]
        if not re.match(r"(diag_|cross_|cuts)", name):
            continue
        txt = open(f, errors="replace").read()
        src = re.search(r"(\d+) certificate sources from (\S+)", txt)
        srcx = re.search(r"cross-cut screen over (\d+) sources", txt)
        loaded = re.search(r"loaded (\d+) screened leads", txt)
        scr = re.search(r"screen: (\d+) leads", txt)
        opt = re.search(r"optimising (\d+) leads", txt)
        done = re.search(r"done: (\d+)/(\d+) leads optimised; below record: (\d+); wall (\d+)s", txt)
        nline = len(re.findall(r"-> m=\d+ S=", txt))
        below = sorted(set(int(m) for m in re.findall(r"-> m=(\d+) S=[\d.]+ record [\d.]+ diff -0\.\d+ .*BELOW", txt)))
        sources = (src.group(1) + " files (" + os.path.basename(src.group(2).rstrip("/")) + ")") if src else (srcx.group(1) + " sources" if srcx else ("saved leads" if loaded else "records"))
        rows.append((pod, name, sources, scr.group(1) if scr else (loaded.group(1) if loaded else "-"),
                     opt.group(1) if opt else "-", (done.group(1) if done else f"{nline} (stopped or running)"),
                     ", ".join(f"n={m}" for m in below) if below else "none", (done.group(4) + " s") if done else "-"))
print("| pod | pass (log) | sources | screened leads | selected | optimised | below record | wall |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(r) + " |")
