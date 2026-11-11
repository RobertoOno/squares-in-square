#!/usr/bin/env bash
# Create a run directory and its filled-in opening prompt.
# Usage: scripts/new_run.sh <model-label> <agent-harness> [budget]
#   e.g. scripts/new_run.sh fable-5.2 "Claude Code" "8 hours"
#        scripts/new_run.sh gpt-5.x "Codex CLI" "8 hours"
set -euo pipefail
cd "$(dirname "$0")/.."
model="${1:?model label}"; harness="${2:?agent harness}"; budget="${3:-8 hours}"
label="$(date +%Y-%m-%d)_${model// /-}"
dir="runs/$label"
[ -e "$dir" ] && { echo "exists: $dir"; exit 1; }

if command -v sha256sum >/dev/null; then SHA="sha256sum"; else SHA="shasum -a 256"; fi
$SHA -c VERIFIER.sha256 >/dev/null || { echo "verifier hash mismatch, aborting"; exit 1; }
cpus=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "?")
if command -v free >/dev/null; then ram="$(free -g | awk '/Mem:/{print $2}') GB RAM"
else ram="$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 )) GB RAM"; fi
others=$(find runs -mindepth 1 -maxdepth 1 -type d | wc -l)
[ "$others" -gt 0 ] && echo "WARNING: other runs present in runs/. For a clean, independent run start from a fresh clone of the harness tag: git clone --branch harness-v1 ..."

mkdir -p "$dir"/{certificates,search,work}
touch "$dir/attempts.jsonl" "$dir/certificates/.gitkeep" "$dir/search/.gitkeep"
cat > "$dir/records.json" <<JSON
{
  "_doc": "Filled by the agent in phase 1. Entry: n, upper (string, as published), lower (optional), proven_optimal, source (URL), retrieved (date), note.",
  "records": []
}
JSON
cat > "$dir/RUN.md" <<MD
# Run $label

| field | value |
|---|---|
| model | $model |
| agent harness | $harness |
| budget | $budget |
| harness commit | $(git rev-parse --short HEAD) |
| verifier sha256 | $($SHA verify.py | cut -c1-16)… |
| machine | $cpus CPUs, $ram, $(uname -sm) |
| started | $(date +%Y-%m-%dT%H:%M:%S%z) |
| ended | _fill in_ |
| human interventions | _none (list any message sent after the opening prompt)_ |
| tokens / cost | _fill in if available_ |
MD
sed -e "s#{{RUN_DIR}}#$dir#g" -e "s#{{BUDGET}}#$budget#g" PROMPT.md > "$dir/PROMPT.md"
echo "Run directory: $dir"
echo "Paste $dir/PROMPT.md into the agent, started at the repo root."
