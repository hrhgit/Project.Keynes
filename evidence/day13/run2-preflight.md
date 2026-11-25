# PR 72 performance check

The saved PR and issue name reductions in full overlay generation and texture upload calls while each overlay is open. The headless recorder leaves the overlays closed. The historical report
`/Users/herh/.keynes-perf/comparisons/6ce469e952a2..7ebdf9d20ac6-20261124-183817/report.json`
contains 409 metric rows. `csv.tail_overlay_refresh_count.mean`, `csv.tail_overlay_last_bake_ms.mean`, and `csv.render_draw_calls_in_frame.mean` were all zero in every archived round. The comparison therefore uses `--unmeasured`.

## Skill and inputs

The commands below ran from `/Users/herh/MyFiles/games/keynes-wt-day13`.

```sh
cat .agents/skills/project-keynes-perf-change-check/SKILL.md
cmp .agents/skills/project-keynes-perf-change-check/SKILL.md .codex/skills/project-keynes-perf-change-check/SKILL.md
cat '/private/tmp/claude-501/-Users-herh--claude-spares-spare-NE9wOt/14c5315e-8201-4bb1-a2ca-50a3f3b05ee0/scratchpad/d13/inputs/pr-72.md' '/private/tmp/claude-501/-Users-herh--claude-spares-spare-NE9wOt/14c5315e-8201-4bb1-a2ca-50a3f3b05ee0/scratchpad/d13/inputs/issue-66.md'
git log master --first-parent --merges --format='%H %P' --grep='Merge pull request #72 '
python3 tools/perf/perf_change_check.py --home ~/.keynes-perf history
python3 -c 'import json; from pathlib import Path; p=Path.home()/".keynes-perf/comparisons/6ce469e952a2..7ebdf9d20ac6-20261124-183817/report.json"; d=json.loads(p.read_text()); print(*(r for r in d["metrics"] if r["metric"] in ("csv.tail_overlay_refresh_count.mean", "csv.tail_overlay_last_bake_ms.mean", "csv.render_draw_calls_in_frame.mean")), sep="\n")'
```

The two skill copies were identical. The merge lookup returned these hashes in order (merge, base, head).

```text
5fc4c7114914bd3653ef3ee6cec47bf45a3d6295 9ddb127342622cc1230b4690d2ea07b96e2c7be7 ec9a22ce2ec349504c474fef3099f01c8b79d3c0
```

The archive listed records for `6ce469e952a2` and `7ebdf9d20ac6`. Neither requested commit had a record.

## Initial isolated run

```sh
/bin/bash -o pipefail -c 'bash "$1/prepare.sh" 2>&1 | tee "$1/setup.log"' _ '/private/tmp/claude-501/-Users-herh--claude-spares-spare-NE9wOt/14c5315e-8201-4bb1-a2ca-50a3f3b05ee0/scratchpad/d13/run2'
/bin/bash '/private/tmp/claude-501/-Users-herh--claude-spares-spare-NE9wOt/14c5315e-8201-4bb1-a2ca-50a3f3b05ee0/scratchpad/d13/run2/compare.sh'
```

`prepare.sh` and `compare.sh` preserve the precise setup and invocation. The comparison exited 1 during the base build. Its full verdict is in `comparison.log`. The isolated home hid the installed SCons package. The subsequently clarified procedure uses the default archive and the normal home.

## Default archive preflight

```sh
scons --version
rg -n '^MAX_WORKTREES' tools/perf/perf_change_check.py
sed -n '606,635p;704,744p' tools/perf/perf_change_check.py
ls -1tr ~/.keynes-perf/worktrees
git --no-optional-locks rev-parse HEAD
git --no-optional-locks status --short --branch
```

SCons 4.11.1 works in the normal environment. The archive already has three cached worktrees, with `7ebdf9d20ac6` and `6ce469e952a2` the oldest in that order. The script caps the cache at three and removes the oldest worktree before adding a new one. The original checkout remains clean and detached at `b05f8fc9e336bf055b02b870e2c75917cc9bc875`.
