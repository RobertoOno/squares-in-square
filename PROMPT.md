Read CLAUDE.md first; its ground rules bind everything below.

This repo has an exact verifier for packings of n unit squares into a square of side S.
The task: find a packing, for any n, whose certified side is strictly smaller than the best
known upper bound for s(n). You have about **8 hours** of wall-clock time. Work autonomously;
do not wait for me between phases.

**Phase 0 — orient (short).** Run the integrity check and tests. Read `verify.py` and
`certify.py` so you know exactly what is accepted.

**Phase 1 — state of the art.** Build `records.json` for every n the public tables cover
(at least n ≤ 100): best known upper bound, lower bound where known, proven-optimal flag,
source URL, date. Start from Erich Friedman's Packing Center ("Squares in Squares") and
check for later improvements in the literature or online (the tables get updated by
hobbyists; find out when and by whom). Then write `targets.md`: rank the n values where an
improvement looks most plausible (large gap to the lower bound, best packing that looks
unpolished or was found with an old or weak method, few independent attempts) and explain
your reasoning for the top 10.

**Phase 2 — calibrate.** Before attacking, show your search machinery can reproduce known
records: pick three non-trivial n with irregular best packings, rediscover packings within
1e-6 of the record from scratch (not by copying the published coordinates), and certify
them. If you can't get close to known records, improve the method before going on.

**Phase 3 — attack.** Spend most of the budget here, on your targets. Methods are your
choice. Log every attempt.

**Phase 4 — report.** Write `REPORT.md`: what you tried per n, what worked and what didn't,
best certified S per n vs. record, and any candidate improvements with the full checklist
from rule 6. Be calibrated: an honest null result with good calibration evidence is a
useful outcome; an inflated claim is not.
