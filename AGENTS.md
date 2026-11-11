# Squares in a square: certified record hunt (agent rules)

These rules apply to any coding agent (Codex, Claude Code, Gemini CLI, ...).
`CLAUDE.md` only imports this file.

**Problem.** s(n) is the side of the smallest square that holds n non-overlapping unit squares
(any positions, any rotations). For many n the optimum is unknown. The best known upper bounds
are tabulated publicly (Erich Friedman's *Packing Center*, "Squares in Squares", plus later
literature). The goal is to find a packing with a side strictly smaller than the best known
upper bound for some n, and to prove it with an exact certificate.

**Your run directory** (`RUN_DIR`, e.g. `runs/<label>/`) is named in your opening prompt.
Write *only* inside it. Below, every path without a leading `/` is relative to `RUN_DIR`
unless it names a top-level harness file.

## Ground rules (non-negotiable)

1. **`verify.py` (top level) is the only judge.** It uses exact rational arithmetic. It is frozen:
   never edit, move, wrap, monkey-patch or shadow `verify.py`, `tests/`, or `VERIFIER.sha256`.
   Do not create files named `verify*.py` or `fractions.py` anywhere. Before any claim run,
   from the repo root:
   ```
   sha256sum -c VERIFIER.sha256 && python3 -m unittest discover -s tests
   ```
2. **A result exists only if**
   `python3 verify.py RUN_DIR/certificates/<file>.json --compare RUN_DIR/records.json`
   prints `CERTIFIED IMPROVEMENT`. Float scores, plots and "this should work" are not results.
   Use `certify.py` to turn a float packing into an exact certificate.
3. **`records.json` must be sourced.** Every entry needs `upper` (string, exactly as published),
   `source` (URL), `retrieved` (date), and `proven_optimal: true` where the literature proves
   optimality. Never change a record value without a source. A human reviews this file; an
   unsourced or inflated record invalidates every claim that depends on it.
   Set `upper_truncated_down: true` only if you computed the record's exact closed form and
   wrote its decimal expansion truncated toward zero (say so in `note`).
4. **Log everything** to `attempts.jsonl`, one JSON object per line, negative results included:
   `{"ts", "n", "method", "best_float_S", "certified_S", "wall_seconds", "note"}`.
5. **Layout inside RUN_DIR.** Scratch in `work/`. Only certificates that verify go in
   `certificates/`, named `n<N>_S<first 8 decimals>.json`. Reusable search code in `search/`.
6. **Independence.** Never read, copy or run anything from other directories under `runs/`.
   Each run must be the work of one agent from the shared harness alone.
7. **Before calling anything an improvement, try to break it:** re-verify from a clean
   checkout; confirm the record from a second source (the record may have been improved
   recently, and the table you read may be stale); check you are not inside the rounding of
   the published value; check n is not proven optimal. Until a human confirms, call it a
   *candidate*.
8. **Budget discipline.** Do not sink the whole budget into one n. If an n shows no
   progress over a reasonable slice of the budget, log it and move on.
9. You may install packages (`pip install --break-system-packages ...`) and write any search
   method you like. The verifier constrains only what counts as a result, not how you search.

## Harness files (top level, read-only for agents)
- `verify.py`: frozen exact verifier (certificate format in its docstring)
- `certify.py`: float packing → exact certificate (sound: rounding is repaired by scaling
  centres apart, which can never create overlaps)
- `tests/`, `VERIFIER.sha256`: verifier tests and integrity hashes
- `PROMPT.md`: the opening prompt template, identical for every model
