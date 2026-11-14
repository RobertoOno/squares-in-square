#!/usr/bin/env python3
"""Follow-up: files for a registration request at The Squares Project (drafts only; nothing is sent).

For n = 147 and n = 228 this writes, under evidence/registration/:
  nN.strict.json / nN.strict.cert   the same packing moved by (d, d) inside a square of side S + 2d,
                                    d = 1e-15, so that every wall margin is positive as well
  issue_nN.md                       the draft of the request, with every number computed here from the
                                    certificate, the public tables and the Kaggle per-puzzle table

Options: --credit NAME, --commit FULL_ID (known only after the branch is pushed), --post-dir DIR
(also writes the bodies and titles to post, outside the repository).
"""
import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(RUN))
OUT = os.path.join(RUN, "evidence", "registration")
REL = "runs/2026-11-11_fable-5.2"
D = F(1, 10 ** 15)
CREDIT = "<CREDIT NAME>"          # set with --credit
COMMIT = "<COMMIT>"               # set with --commit (known only after the branch is pushed)
POSTDIR = None                    # set with --post-dir: also write the bodies to post, without the draft header


def dec(x, places):
    q = x.numerator * 10 ** places // x.denominator
    s = str(q).rjust(places + 1, "0")
    return s[:-places] + "." + s[-places:]


def up(x, places=12):
    q = -((-x.numerator * 10 ** places) // x.denominator)
    s = str(q).rjust(places + 1, "0")
    return s[:-places] + "." + s[-places:]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def kaggle(n):
    with open(os.path.join(RUN, "work/web/kaggle_perpuzzle/per_puzzle_v31.tsv"), encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] == str(n):
                return p[1], p[2], p[3]


def strict_variant(name, n):
    src = os.path.join(RUN, "certificates", name)
    d = json.load(open(src))
    S = F(d["side"]) + 2 * D
    sq = [{"cx": str(F(s["cx"]) + D), "cy": str(F(s["cy"]) + D), "t": s["t"]} for s in d["squares"]]
    js = os.path.join(OUT, f"n{n}.strict.json")
    json.dump({"n": n, "side": str(S), "squares": sq}, open(js, "w"), indent=0)
    rel = lambda q: os.path.relpath(q, ROOT)          # repository-relative paths, so the saved outputs carry no local path
    r = subprocess.run([sys.executable, rel(os.path.join(HERE, "fu_strict_check.py")), rel(js), "--export", rel(os.path.join(OUT, f"n{n}.strict.cert"))],
                       capture_output=True, text=True, cwd=ROOT)
    open(os.path.join(OUT, f"strict_check_n{n}.strict.txt"), "w").write(r.stdout)
    v = subprocess.run([sys.executable, "verify.py", rel(js)], capture_output=True, text=True, cwd=ROOT)
    open(os.path.join(OUT, f"frozen_verifier_n{n}.strict.txt"), "w").write(v.stdout)
    assert "STRICT VALID" in r.stdout and v.stdout.startswith("VALID"), (r.stdout, v.stdout)
    return S


def margins(n):
    t = open(os.path.join(OUT, f"strict_check_n{n}.txt")).read()
    pair = t.split("smallest pair margin: ")[1].split(" ")[0]
    close = t.split(" in all; ")[1].split(" ")[0]
    return pair, close


def draft(n, name, registry, registry_note, start, lineage, extra_disclosure, title_tail):
    d = json.load(open(os.path.join(RUN, "certificates", name)))
    S = F(d["side"])
    Sstrict = strict_variant(name, n)
    kL, kteam, kdate = kaggle(n)
    pair, close = margins(n)
    body = f"""**Leaderboard disclosure first.** This packing improves the registry but does **not** beat the Kaggle per-puzzle leaderboard, which lists side {dec(F(kL), 24)}… for team {kteam} (submitted {kdate}; notebook version 31, read 2026-11-14 19:22 UTC) with no packing. Our exact side is {float(S - F(kL)):.3e} larger. The side-only entry supplies nothing we can check. As far as we know this is the first public packing at that side.{extra_disclosure}

**Credit name.** {CREDIT} (https://github.com/RobertoOno).

**Claim.** s({n}) ≤ **{up(S)}** (exact rational side rounded up at 12 places; the exact side in the certificate is {dec(S, 30)}…). {registry_note} The improvement over the registry is {dec(F(registry) - S, 15)}. This is feasibility only: no optimality, KKT or rigidity claim.

**Certificate.** Repository https://github.com/RobertoOno/squares-in-square at revision `{COMMIT}`:
- `{REL}/certificates/{name}`: exact rational certificate; each unit square is its centre (cx, cy) and t = tan(θ/2), so cos θ and sin θ are rational; the side is a fraction. SHA-256 `{sha(os.path.join(RUN, "certificates", name))}`.
- `{REL}/evidence/registration/n{n}.cert`: the same packing as text, line 1 `n S`, then `x y t` per square. SHA-256 `{sha(os.path.join(OUT, f"n{n}.cert"))}`.
- `{REL}/evidence/registration/n{n}.strict.cert` (and `.strict.json`): the same packing moved by (10⁻¹⁵, 10⁻¹⁵) in a square of side S + 2·10⁻¹⁵ = {dec(Sstrict, 18)}…, for checkers that require positive wall margins. In the first two files the packing touches the four walls (wall margin exactly 0), because the side is the extent of the packing. SHA-256 `{sha(os.path.join(OUT, f"n{n}.strict.cert"))}`.

**Checking.** All three run in under a second on a laptop; outputs are in `{REL}/evidence/registration/`.
- `python3 verify.py {REL}/certificates/{name}`: the repository's verifier, frozen before the search (its SHA-256 is in `VERIFIER.sha256`). Exact `fractions.Fraction`; every vertex in [0, S]², interiors of all {n * (n - 1) // 2} pairs disjoint by the separating axis theorem, touching allowed. Result: VALID.
- `python3 {REL}/search/indep_check.py {REL}/certificates/{name}`: exact rational polygon clipping; the intersection area is exactly 0 for each of the {close} pairs whose centres are closer than √2, and every vertex is inside. Shares no code with the verifier. Result: PASSED.
- `python3 {REL}/search/fu_strict_check.py {REL}/evidence/registration/n{n}.strict.json`: exact; every pair with centres closer than √2 strictly separated along one of the four edge normals, every wall margin positive. Result: STRICT VALID; smallest pair margin {pair}, smallest wall margin 10⁻¹⁵.

**What the checkers share.** The first and third both use the separating axis theorem and the half-angle parametrisation; the second uses polygon clipping instead. The second and third were written by the same AI agent that found the packing; the first was fixed before the search began. None is the registry's own verifier, and no third party has run them.

**Not done.** `packing-witness verify` was not run. No proof assistant. No optimality or rigidity analysis. No review by anyone but the submitter. Kaggle discussions, Discord and public notebooks newer than 2026-11-02 were not searched for a public copy of this packing.

**Lineage and credit.** {lineage} Please credit {start} as the start. The repository's `REPORT.md` records that the run first reported this as an improvement and then corrected itself when the side-only entry was found.

**AI assistance.** The packing was found, certified and checked by an AI coding agent (Claude, by Anthropic) working in the harness of this repository. A person set up the harness, directed the work and read this request before it was posted. This text was drafted by the agent.
"""
    title = f"s({n}) ≤ {up(S)}: {title_tail} (registration request)"
    path = os.path.join(OUT, f"issue_n{n}.md")
    note = "the full commit id is filled in when the request is posted" if COMMIT == "<COMMIT>" else "as posted"
    open(path, "w", encoding="utf-8").write(f"<!-- Text of the registration request ({note}). Title: {title} -->\n\n{body}")
    if POSTDIR:
        open(os.path.join(POSTDIR, f"body_n{n}.md"), "w", encoding="utf-8").write(body)
        open(os.path.join(POSTDIR, f"title_n{n}.txt"), "w", encoding="utf-8").write(title)
    return title, path, S, kL


def main():
    global CREDIT, COMMIT, POSTDIR
    a = sys.argv[1:]
    if "--credit" in a:
        CREDIT = a[a.index("--credit") + 1]
    if "--commit" in a:
        COMMIT = a[a.index("--commit") + 1]
    if "--post-dir" in a:
        POSTDIR = a[a.index("--post-dir") + 1]
        os.makedirs(POSTDIR, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    # the open request #983 for n = 228
    r983 = F("15.6008017348117538028514559173910014808630264")
    d228 = json.load(open(os.path.join(RUN, "certificates", "n228_S59604312.json")))
    S228 = F(d228["side"])
    sq1000 = F("15.59604311664627229390668802682613932021971821107903")
    extra228 = (f" An earlier side-only entry, {dec(sq1000, 24)}… for team square1000 (2026-10-29 14:18:39 UTC), is {float(S228 - sq1000):.3e} below ours."
                f" The open request #983 (side 15.600801734812, Doğa Özden) is {dec(r983 - S228, 12)} above this packing; we have not compared the two arrangements.")
    out = []
    out.append(draft(
        147, "n147_S65104355.json", "12.65685424949238",
        "The registry holds 12.65685424949238 (= 7 + 4√2) for n = 147 (case n-147, reviewed 2026-11-04, main @fa980f8e); no request is open for this count.",
        "Evan Daniel's n = 229 packing",
        "Start: the registry's n = 229 record (Evan Daniel, 2026-10-20, side 15.6501615138764…, witness W-known-best-n229): a three-wide diagonal band of tilted squares between two corner-anchored grids. "
        "Operation: delete every square whose centre has 13 ≤ x + y < 19 and translate the squares beyond by (−3, −3), which removes one period of the band. 147 squares remain, overlapping by at most 0.010. "
        "A penalty step and an exact-constraint sequential-LP polish (our own code, `search/opt.py`) remove the overlaps at a cost of 0.00088 in side. "
        "Other cut positions and seven other published copies or versions of the n = 229 packing give sides between 12.651043557 and 12.651056453. "
        "The registry's current n = 147 packing, the 45° arrangement shared with n = 148, is a different arrangement.",
        "", "first public packing below 7 + 4√2"))
    out.append(draft(
        228, "n228_S59604312.json", "15.60460147572967429",
        "The registry holds 15.60460147572967429 for n = 228 (Francisco Couzo, improved by PingYou Ltd, 2026-10-13; case n-228, main @fa980f8e).",
        "Francisco Couzo's n = 404 packing",
        "Start: Francisco Couzo's packing of n = 404 (`packing/resources/web/couzo-issue763-2026-10-23/source/certificates/best/n404.cert` in this registry, SHA-256 `8c8c8b45f40cfb1d1261baa479be41f9de89d83ceabc03f9ce72a1d42bb67f2e`, side 20.5914), a member of the band family of the records for n = 123, 259 and 292. "
        "Operation: mirror it, delete every square whose centre has 13.8 ≤ x + y < 23.8 and translate the rest by (−5, −5), which removes five periods of the band. 228 squares remain with overlaps up to 0.101. "
        "A penalty step and an exact-constraint sequential-LP polish give side 15.597084912 (also certified: `certificates/n228_S59708491.json`); Couzo's n = 906 packing with fifteen periods removed gives the same value. "
        "Basin hopping with moves that re-seat cells at the ends of the band (our own code, `search/attack.py`) then reaches the side claimed here; two further runs from it found nothing lower.",
        extra228, "first public packing at the leaderboard side"))
    for title, path, S, kL in out:
        print(title)
        print("  draft:", os.path.relpath(path, ROOT))
        print("  side", dec(S, 24), "| Kaggle", kL[:26], "| ours - Kaggle", f"{float(S - F(kL)):.4e}")


if __name__ == "__main__":
    main()
