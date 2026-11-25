#!/bin/bash
set -euo pipefail

run_dir="$(cd "$(dirname "$0")" && pwd)"
cd /Users/herh/MyFiles/games/keynes-wt-day13
export GIT_ALLOW_PROTOCOL=file
export GIT_OPTIONAL_LOCKS=0
export HOME="$run_dir/user-home"
export CFFIXED_USER_HOME="$HOME"
export XDG_DATA_HOME="$HOME/data"
export XDG_CACHE_HOME="$HOME/cache"
export XDG_CONFIG_HOME="$HOME/config"
export TMPDIR="$run_dir/tmp"
export PYTHONDONTWRITEBYTECODE=1

python3 tools/perf/perf_change_check.py \
  --repo "$run_dir/repo" --home "$run_dir/perf" \
  compare 9ddb127342622cc1230b4690d2ea07b96e2c7be7 ec9a22ce2ec349504c474fef3099f01c8b79d3c0 \
  --tier quick \
  --unmeasured 'Issue #66 counts full elevation and wind overlay builds and texture uploads while each overlay is open. The headless recorder leaves the overlays closed, so csv.tail_overlay_refresh_count.mean is zero in all archived rounds and does not measure the claim.' \
  --out "$run_dir/report" 2>&1 | tee "$run_dir/comparison.log"
