# Targets (phase 1) — written 2026-11-11, before any attack run

## What the record table looks like today

`records.json` covers n = 1..324 and takes, for every n, the **smaller** of two public catalogues,
both retrieved 2026-11-11:

| source | state | role |
|---|---|---|
| Erich Friedman's Packing Center, "Squares in Squares" | now a redirect | points to the page below |
| David Ellsworth, *Squares in Squares* (`kingbird.myphotos.cc/packing/squares_in_squares.html`) | HTTP Last-Modified 2026-09-24 | long-standing hobbyist catalogue, 14-digit values, attribution history |
| *The Squares Project* frontier (`jlevy.github.io/squares/frontier.html`, case files in `github.com/jlevy/squares`) | repo head 2026-11-11 11:02 UTC | newer catalogue with exact certificates; **lower than Kingbird at 79 values of n** |

Who updates the tables and when (from the two sources' own attributions):

- 1979–2014: hand constructions (Göbel, Trump, Stenlund, Hämäläinen, Friedman, Bidwell, Cantrell, DeVincentis …).
- Sep 2024 – Feb 2025: Hajba, Cantrell and Ellsworth extend the hand constructions to n ≤ 324.
- Dec 2025 – Mar 2026: Thomas Schadt's simulated annealing "from randomness" and Ellsworth's variants
  take 28, 29, 39, 41, 50, 51, 55, 68, 71, 103, 105 and many large n.
- Jun – Sep 2026: AI-assisted hobbyists (Stead, de Winter, Chang, Wang, Dyachkov, Loyd …).
- Sep – Nov 2026: a crowd around The Squares Project (Xu, Couzo, Daniel, Chaoweeraprasit, Ostashev,
  Özden, PingYou …) replaces 80 of the 146 open non-trivial records; **entries dated 2026-11-09/10/11
  exist** (n = 156, 172, 180, 199, 232, 268, 269, 270, 299, 303, 307). The table moves daily.
- Proofs: n = 11 proved optimal (Ahmed et al., Sep 2026); proofs reported for 12, 17 and others.
  All are flagged `proven_optimal` in `records.json` (91 values of n), so no claim can be made there.

Consequences for targeting:

1. Every open record I polished (233 of them, `work/polish_baseline.json`) is a converged local optimum:
   no record has numerical slack. An improvement needs a **different arrangement**.
2. The table is closed under the cheap consequences (`search/closure.py`: delete-a-square, add-an-L,
   clean strip removal): 0 hits. No free improvement exists.
3. Small n (≤ 55) has been searched from random starts by several independent programs with
   "statistics gathered"; yet n = 51 still fell on 2026-10-08 to a structured packing
   ((16+5√2)/3). So random restarts saturate there, structure does not.
4. Softness is therefore judged by **who last touched the entry and how it sits against its neighbours**.
   Write n = k² + j and g(k, j) = record − k. Adding an L gives g(k+1, j) ≤ g(k, j), and deleting a square
   gives g(k, j−1) ≤ g(k, j). An entry that still equals its 1979–2024 construction while all four
   neighbours fell in 2026 is suspect. `search/targets_table.py` computes this for all 233 open n.

## Ranking (most plausible first)

| # | n | record | holder | why it looks soft |
|---|---|---|---|---|
| 1 | 147 | 7+4√2 = 12.65685 | Göbel-pattern 45° diamond (1979 pattern), never improved | Identical to the n = 148 record: it is the 148 diamond with one square deleted. g(12,3) = 0.657, while g(12,2) = 0.584 (Daniel, Oct 2026) and g(13,3) = 0.615, g(15,3) = 0.605, g(16,3) = 0.591. The step j = 2→3 is 0.03–0.04 for k = 13..16 but 0.073 here. Expected value ≈ 12.62; neighbour-trend residual +0.029, the largest of any entry with j > 1. |
| 2 | 290 | 14+5√2/2 = 17.53553 | composition of two Göbel packings | Same side as n = 291, so one whole square is spare. All analogous pairs (232/233, 264/265, 295/296) were split in Oct–Nov 2026 by 0.003–0.017. |
| 3 | 234 | 29/2+√7/2 = 15.82288 | Ellsworth 2024, two-wide diagonal band | "√7/2 family": the siblings 86, 127, 176, 204, 299 all fell by 0.002–0.027 in Oct–Nov 2026 to tilted-block arrangements. n = 235 is only 0.0037 above it. Residual +0.021. |
| 4 | 151 | 23/2+√7/2 = 12.82288 | Ellsworth/Cantrell 2024, same band | Same family; n = 152 is only 0.008 above; g(13,7) = 0.796 and g(11,7) = 0.825 bracket it at 0.811. Residual +0.015. Smallest of the suspects, so the cheapest to search. |
| 5 | 201 | 14+√2/2 = 14.70711 | Göbel strip (1979 pattern) | Pure L-extension of 174 and 149. g(14,4) = 0.657 and g(14,6) = 0.728 bracket it at 0.692; g(15,5) = 0.683. Residual +0.013. |
| 6 | 125 | 11+√2/2 = 11.70711 | Göbel strip (1979 pattern) | Pure L-extension of 104. Neighbours 124 (0.657) and 126 (0.743, Xu Oct 2026) and g(12,4) = 0.657 put the trend at 0.69. Residual +0.016. Small enough for many restarts. |
| 7 | 203 | 7+11√2/2 = 14.77817 | Ellsworth 2024 | Sits between 202 (0.728) and 204 (0.804, Daniel 2026-11-05); residual +0.006. |
| 8 | 226, 257 | k+0.53553 | L-extensions of Göbel's 65 | k² + 1 has kept the 1979 value 5√2/2−3 for every k = 8..17 while g(k,2) dropped to 0.5636/0.5634 at k = 15/16. Either k²+1 is special or nobody has looked. Large n, expensive. |
| 9 | 66, 83, 89 (band k = 8, 9) | 3+4√2, 9.63476, 5+7√2/2 | Stenlund 1980; Hajba 2024; Stenlund 1980 | Mid-size n where a from-scratch search is still affordable, and whose neighbours 68, 70, 84, 86, 88 all fell in Oct 2026. Residuals +0.015, +0.011, +0.003. |
| 10 | 53, 39 | 13/2+√7/2, 6.81072 | Cantrell 2002 / Schadt 2026 | Positive residuals (+0.028, +0.044) but these are the most-searched sizes in the whole table; listed for completeness, low odds. |

Not targeted: anything flagged proven (including reported proofs at 12, 17); the trivial entries
(n = k²+k… where the record is an integer) — the first non-integer entry of each band has only just
appeared for k ≥ 10 and the crowd is working exactly there; n > 324 (no public record to compare with).

## How I intend to attack

- Baseline: load the published record packings (`search/witness_io.py`), confirm each is a local optimum
  (done), use them as seeds.
- Transfer seeds: for a target n = k²+j, build starting points from (a) the records at n±1 (add/delete a
  square), (b) the records at (k±1)²+j with an approximate L removed/added and repaired, (c) parametrised
  tilted-block arrangements, then compress with the penalty method and finish with the exact SLP polish.
- Basin hopping around the best seeds; log every attempt to `attempts.jsonl`.
- Budget rule (AGENTS.md rule 8): no single n gets more than about a quarter of the attack time unless it
  is producing progress.

## Honest prior

Dozens of people, several with stronger tooling and weeks of compute, are attacking exactly this table
right now. My prior for a certified improvement that survives until a human checks it is low
(roughly 10–20 %), concentrated on targets 1–4, where the softness evidence is structural rather than
statistical.
