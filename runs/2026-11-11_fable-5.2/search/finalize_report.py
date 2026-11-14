#!/usr/bin/env python3
"""Fill the generated tables of REPORT.md from the data: work/REPORT.template.md -> REPORT.md.
PASS_TABLE comes from the mirrored pass logs, PERN_TABLE and ATTEMPT_COUNT from attempts.jsonl."""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
PASSES = [  # (pod, log name, operation, sources)
    ("B", "diag_all", "diagonal", "324 records, first pass (remove and insert, p ≤ 6)"),
    ("B", "diag_fine", "diagonal", "324 records, finer cut positions"),
    ("A", "diag_wide", "diagonal", "324 records, p ≤ 12"),
    ("A", "diag_ext2", "diagonal", "324 records, insertions only, improved fill"),
    ("A", "diag_small", "diagonal", "185 alternative published versions with n ≤ 324 (Squares Project web resources)"),
    ("B", "diag_big", "diagonal", "655 published packings with n > 324 (Squares Project web resources)"),
    ("A", "diag_bigtriv", "diagonal", "the same 655 packings, targets with integer records only; stopped early"),
    ("B", "diag_more", "diagonal", "275 further published packings (Squares Project web resources)"),
    ("B", "diag_huge", "diagonal", "550 published packings with large n, p = 9..21; stopped with 4 leads hanging"),
    ("A", "diag_couzo2", "diagonal", "4,416 certificates from F. Couzo's repository"),
    ("B", "diag_evand", "diagonal", "461 certificates from E. Daniel's repository"),
    ("A", "diag_ext", "diagonal", "1,234 packings from three more repositories (Minuii 1,000; TheSnakeFang 194; de Winter 40); stopped with 3 leads hanging"),
    ("A", "diag_own", "diagonal", "the candidate packings themselves (n = 147, both n = 228)"),
    ("A", "cross_rec", "cross-cut", "144 non-trivial records, p ≤ 8"),
    ("A", "cross_ext", "cross-cut", "1,234 packings from three more repositories"),
    ("A", "cross_big", "cross-cut", "655 published packings with n > 324; stopped with 1 lead hanging"),
    ("B", "cross_b", "cross-cut", "1,286 published packings (the 275, the 550 and E. Daniel's 461); the 12,000 most promising of 86,301 screened leads"),
]


def pass_table():
    out = ["| operation | sources | leads repaired and polished | below the catalogues |", "|---|---|---|---|"]
    tot = 0
    for pod, name, op, desc in PASSES:
        f = os.path.join(RUN, "work", "remote", pod, "work", "logs", name + ".log")
        if not os.path.exists(f):
            continue
        txt = open(f, errors="replace").read()
        n = len(re.findall(r"-> m=\d+ S=", txt))
        sel = re.search(r"optimising (\d+) leads", txt)
        done = re.search(r"done: (\d+)/(\d+) leads optimised", txt)
        below = sorted(set(int(m) for m in re.findall(r"-> m=(\d+) S=[\d.]+ record [\d.]+ diff -0\.\d+ .*BELOW", txt)))
        cnt = int(done.group(1)) if done else n
        tot += cnt
        frac = f"{cnt:,}" + ("" if done or not sel else f" of {int(sel.group(1)):,}")
        out.append(f"| {op} | {desc} | {frac} | {', '.join('n = %d' % m for m in below) if below else 'none'} |")
    out.append(f"| | **total** | **{tot:,}** | n = 147 and n = 228 only |")
    return "\n".join(out)


def pern_table():
    ns = "147 228 290 234 151 201 125 203 226 257 66 83 89 53 39 86 88 102 130 266 177 199 172 230 300".split()
    r = subprocess.run([sys.executable, os.path.join(HERE, "report_table.py")] + ns, capture_output=True, text=True)
    lines = []
    for l in r.stdout.strip().split("\n"):
        l = re.sub(r"(, )?(blockscan-note|closure2|insert)(×\d+)?", "", l)
        l = l.replace("| , ", "| ")
        lines.append(l)
    return "\n".join(lines)


tpl = open(os.path.join(RUN, "work", "REPORT.template.md")).read()
nlines = sum(1 for l in open(os.path.join(RUN, "attempts.jsonl")) if l.strip())
txt = tpl.replace("PASS_TABLE", pass_table()).replace("PERN_TABLE", pern_table()).replace("ATTEMPT_COUNT", f"{nlines:,}")
open(os.path.join(RUN, "REPORT.md"), "w").write(txt)
print("REPORT.md written;", nlines, "attempt lines")
