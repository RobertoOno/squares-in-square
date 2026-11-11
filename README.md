# Squares in a square: certified record hunt

Setup for an autonomous agent (Claude Code) trying to beat best-known packings of n unit
squares in a square, with an exact-arithmetic verifier as the only judge.

    python3 -m unittest discover -s tests -v     # verifier tests (stdlib only)
    sha256sum -c VERIFIER.sha256                  # integrity of the frozen verifier

Start the agent with the contents of `PROMPT.md`. Rules for the agent: `CLAUDE.md`.

Human checklist after the run:
1. `sha256sum -c VERIFIER.sha256` and compare hashes with the ones you saved before the run
2. `git diff <start-commit> -- verify.py tests/` must be empty
3. review the `records.json` sources by hand, especially for any n with a claimed improvement
4. re-run `verify.py --compare` on every certificate in `certificates/`
