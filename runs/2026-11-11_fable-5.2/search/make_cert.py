#!/usr/bin/env python3
"""Float packing (our JSON: n, x, y, th) -> exact certificate via the frozen top-level certify.py,
then judged by the frozen top-level verify.py. This file only prepares input and moves files;
it contains no acceptance logic of its own.

Usage: make_cert.py packing.json [--den 10**14] [--method "text"] [--note "text"] [--wall SECONDS]
Writes RUN_DIR/certificates/n<N>_S<first 8 decimals>.json if (and only if) verify.py prints VALID,
and appends one line to RUN_DIR/attempts.jsonl.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(RUN))
sys.path.insert(0, HERE)
from opt import tighten  # noqa: E402
from sqgeom import max_violation, normalize  # noqa: E402


def log_attempt(n, method, best_float_S, certified_S, wall_seconds, note):
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n": n, "method": method,
           "best_float_S": best_float_S, "certified_S": certified_S,
           "wall_seconds": wall_seconds, "note": note}
    with open(os.path.join(RUN, "attempts.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def certify(path, den="10**14", margin=2e-13):
    d = json.load(open(path))
    x, y, th = np.array(d["x"], float), np.array(d["y"], float), np.array(d["th"], float)
    n = len(x)
    x, y, th, S = normalize(x, y, th)
    x, y, th, S = tighten(x, y, th, S, margin=margin)
    mo, mw = max_violation(x, y, th, S)
    work = os.path.join(RUN, "work", "certtmp")
    os.makedirs(work, exist_ok=True)
    fin = os.path.join(work, f"n{n}_{os.getpid()}_float.json")
    fout = os.path.join(work, f"n{n}_{os.getpid()}_cert.json")
    json.dump({"n": n, "squares": [{"x": float(a), "y": float(b), "theta": float(c)} for a, b, c in zip(x, y, th)]},
              open(fin, "w"))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "certify.py"), fin, fout, "--den", den],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        return dict(ok=False, msg=r.stdout + r.stderr, float_S=S)
    v = subprocess.run([sys.executable, os.path.join(ROOT, "verify.py"), fout, "--compare", os.path.join(RUN, "records.json")],
                       capture_output=True, text=True, cwd=ROOT)
    out = v.stdout.strip()
    m = re.search(r"VALID\s+n=(\d+)\s+S=([0-9.]+)", out)
    if v.returncode != 0 or not m:
        return dict(ok=False, msg=out, float_S=S)
    Sdec = m.group(2)
    name = f"n{n}_S{Sdec.split('.')[1][:8]}.json"
    dst = os.path.join(RUN, "certificates", name)
    shutil.copyfile(fout, dst)
    os.remove(fin); os.remove(fout)
    return dict(ok=True, msg=out, float_S=S, cert_S=Sdec, path=dst, improvement=("CERTIFIED IMPROVEMENT" in out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("packing")
    ap.add_argument("--den", default="10**14")
    ap.add_argument("--method", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--wall", type=float, default=None)
    ap.add_argument("--nolog", action="store_true")
    a = ap.parse_args()
    res = certify(a.packing, a.den)
    print(res["msg"])
    if res["ok"]:
        print("certificate:", os.path.relpath(res["path"], ROOT))
    if not a.nolog:
        d = json.load(open(a.packing))
        log_attempt(len(d["x"]), a.method, res.get("float_S"), res.get("cert_S") if res["ok"] else None,
                    a.wall if a.wall is not None else d.get("t"), a.note + (" | " + res["msg"].splitlines()[-1] if res["msg"] else ""))
    sys.exit(0 if res["ok"] else 1)
