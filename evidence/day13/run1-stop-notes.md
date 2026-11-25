# PR 72 performance check

Stopped at skill step 1. Issue 66 calls for counting overlay generations and texture upload calls separately while each overlay is open. The standard comparison invokes the simulation recorder, which does not open either overlay. The archive has no per-overlay generation or upload metric. Its generic refresh counter and bake timings are all zero in the newest archived comparison. Windowed frame time and GPU work were not measured.

## Inputs

- PR head: `ec9a22ce2ec349504c474fef3099f01c8b79d3c0`.
- PR merge: `5fc4c7114914bd3653ef3ee6cec47bf45a3d6295`, found on local master's first-parent history.
- Pre-merge base: `9ddb127342622cc1230b4690d2ea07b96e2c7be7`, the first parent of the merge and the merge base of that parent with the PR head. The saved PR plan names the same baseline. Comparing the PR head with today's master as a merge base returns the PR head because it is already merged.
- Skill copies in `.agents` and `.codex` compare byte for byte. The normal tier would be quick. The default scenario was left as written.

## Commands and evidence

```sh
git log master --first-parent --format='%H %P %s' --grep='Merge pull request #72 '
git merge-base 5fc4c7114914bd3653ef3ee6cec47bf45a3d6295^1 ec9a22ce2ec349504c474fef3099f01c8b79d3c0
python3 tools/perf/perf_change_check.py history
```

```text
5fc4c7114914bd3653ef3ee6cec47bf45a3d6295 9ddb127342622cc1230b4690d2ea07b96e2c7be7 ec9a22ce2ec349504c474fef3099f01c8b79d3c0 Merge pull request #72 from hrhgit/agent/issue-66
9ddb127342622cc1230b4690d2ea07b96e2c7be7
2026-11-25T00:27:10Z 6ce469e952a2 invalid  quick run_ms=1413 days/s=96.38 rss_mb=1031  Merge pull request #52 from hrhgit/codex/absorb-upstream-changes
2026-11-25T01:10:03Z 7ebdf9d20ac6 complete quick run_ms=1380 days/s=93.76 rss_mb=998  Merge pull request #56 from hrhgit/agent/issue-53
2026-11-25T01:17:11Z 6ce469e952a2 complete quick run_ms=1279 days/s=97.39 rss_mb=1030  Merge pull request #52 from hrhgit/codex/absorb-upstream-changes
```

```sh
python3 - <<'PY'
import json
from pathlib import Path
archive = Path('/Users/herh/.keynes-perf')
for path in sorted((archive / 'comparisons').glob('*/report.json')):
    rows = json.loads(path.read_text())['metrics']
    names = [row['metric'] for row in rows]
    print(path, f'({len(names)} metrics)')
    print('overlay/elevation/wind/texture/bake/upload:', [name for name in names if any(word in name.lower() for word in ('overlay', 'elevation', 'wind', 'texture', 'bake', 'upload'))])
PY
python3 - <<'PY'
import json
from pathlib import Path
path = Path('/Users/herh/.keynes-perf/comparisons/6ce469e952a2..7ebdf9d20ac6-20261124-183817/report.json')
report = json.loads(path.read_text())
for row in report['metrics']:
    if 'overlay' in row['metric']:
        print(json.dumps(row, sort_keys=True))
PY
git show ec9a22ce2ec349504c474fef3099f01c8b79d3c0:Project/project-keynes/tests/game/headless_perf_record.gd | sed -n '138,162p;241,269p'; git grep -n -i -E 'overlay_kind|overlay_key|set_map_overlay|PK_OVERLAY|OVERLAY_.*COUNT' ec9a22ce2ec349504c474fef3099f01c8b79d3c0 -- Project/project-keynes/tests/game/headless_perf_record.gd Project/project-keynes/tests/game/player_scene_handoff_probe.gd Project/project-keynes/scripts/game/world_runtime_overlay.gd
git --no-optional-locks status --short --branch
```

- All three earlier reports contain 409 metrics. Related generic metrics include `csv.tail_overlay_refresh_count.mean` and `csv.tail_overlay_last_bake_ms.{mean,p95,max}`. The latest report has three zeros per side for each.
- The source read shows the recorder creates a `WorldRuntimeHost` and generates the world. The overlay-symbol search matched the overlay implementation and did not match the recorder.
- The final checkout status was `## HEAD (no branch)` with no tracked or untracked changes listed.

## Handoff

Steps 2 through 4 were not run. There is no comparison verdict, report, new daily result check, or targeted test result. Issue 66's generation and upload counts can be checked in a separate headless player-scene run if approved. To proceed with the standard skill comparison, supply a supported metric that measures the requested improvement with the applicable workload enabled.
