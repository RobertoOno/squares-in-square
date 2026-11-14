#!/usr/bin/env python3
"""Rule-7 helper: re-read the public sources for one n right now and print what they say.
(Network access; no secrets; the user's identity is never sent.)  Usage: recheck_sources.py N"""
import json
import os
import re
import subprocess
import sys
import time
from fractions import Fraction as F

import yaml

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
n = int(sys.argv[1])
UA = "Mozilla/5.0 (research-bot)"
out = os.path.join(RUN, "work", "web", f"recheck{n}")
os.makedirs(out, exist_ok=True)


def get(url, dst=None, params=None):
    cmd = ["curl", "-sL", "-A", UA, "-w", "\n%{http_code}"]
    if params:
        cmd += ["-G"]
        for k, v in params.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    if dst:
        open(os.path.join(out, dst), "w").write(body)
    return code.strip(), body


print("checked at", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
R = {r["n"]: r for r in json.load(open(os.path.join(RUN, "records.json")))["records"]}
print(f"records.json: n={n} upper={R[n]['upper']} (kingbird {R[n]['upper_kingbird']}, squares project {R[n]['upper_squares_project']}) proven={R[n]['proven_optimal']}")
code, body = get(f"https://raw.githubusercontent.com/jlevy/squares/main/packing/frontier/n-{n:03d}.md", f"n-{n:03d}.md")
if code == "200":
    d = yaml.safe_load(body.split("\n---\n", 1)[0][4:])["packing"]
    ru = d["reported_upper_bound"]
    print(f"Squares Project case: status {d['status']}/{d['reported_status']}; reported upper {ru['value']}; found_by {ru.get('found_by')}; "
          f"improved_by {ru.get('improved_by')}; source_date {ru.get('source_date')}; reviewed {d.get('source_reviewed')}; verified lower {d['verified_lower_bound'].get('value')}")
else:
    print("Squares Project case: HTTP", code)
code, body = get("https://api.github.com/repos/jlevy/squares/commits?per_page=1")
try:
    c = json.loads(body)[0]
    print("Squares Project repo head:", c["sha"][:10], c["commit"]["committer"]["date"])
except Exception:  # noqa: BLE001
    print("repo head: ?")
code, body = get(f"https://raw.githubusercontent.com/franciscouzo/square-packing/HEAD/certificates/best/n{n}.cert", f"couzo_n{n}.cert")
if code == "200":
    rows = [l for l in body.split("\n") if l and not l.startswith("#")]
    try:
        print("Couzo repository best/n%d.cert: side %.12f" % (n, float(F(rows[0].split()[1]))))
    except Exception as e:  # noqa: BLE001
        print("Couzo best: parse error", e)
else:
    print("Couzo best: HTTP", code)
code, body = get(f"https://raw.githubusercontent.com/evand/square-packing/HEAD/lean/Sqpack/Exact/Packs/N{n}.lean", f"evand_N{n}.lean")
m = re.search(r"s\(%d\)[^\n]*" % n, body) if code == "200" else None
print("Daniel repository N%d.lean:" % n, m.group(0)[:140] if m else f"HTTP {code}")
for q in (f'"s({n})"', f'"n={n}"'):
    code, body = get("https://api.github.com/search/issues", params={"q": f"repo:jlevy/squares {q}", "per_page": "5", "sort": "updated"})
    try:
        d = json.loads(body)
        print(f"tracker query {q}: {d.get('total_count')} hits; most recent:", [(it["number"], it["state"], it["title"][:70], it["updated_at"][:10]) for it in d.get("items", [])[:3]])
    except Exception:  # noqa: BLE001
        print("tracker query failed")
    time.sleep(2)
