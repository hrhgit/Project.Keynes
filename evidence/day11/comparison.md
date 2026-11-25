# Day 11 comparison: PR 72 reviews before and after the custom instructions

Code under review: base `9ddb127`, head `ec9a22c` (PR 72). Replay PRs 77 and 78 point at the same two
commits; `gh pr diff 72` and `git diff 9ddb127 ec9a22c` have the same sha256
(`79d69856…92a12e`).

## Runs

| Run | PR | Commit | Instructions | Status | Findings |
|---|---|---|---|---|---|
| 2142920 (original) | 72 | ec9a22c (findings raised at 45a701a, then incremental) | none | completed | 5 (3 Medium, 2 Low) |
| 2147611 | 72 | ec9a22c | yes | skipped, `review_complete: false` | none new |
| 2147635 | 72 | ec9a22c, with `smart_router_extra_instructions` asking not to skip | yes | skipped, `review_complete: false` | none new |
| 2147650 | 77 (replay) | ec9a22c | yes | completed | 4 (1 Medium, 3 Low) |
| 2147703 (control) | 78 (replay) | ec9a22c | cleared (all three fields empty, "Reset to workspace") | completed, `review_complete: true` | 2 (2 Low) |

Medium = `remediation_recommended`, Low = `informational`. After the control run the Issue finding agent text
was restored (1,878 characters, Overridden at repository scope), checked after a page reload.

## Finding by finding

| Topic | Original (no instructions) | With instructions (run 2147650) | Control, no instructions (run 2147703) | Checked against the code |
|---|---|---|---|---|
| Overlay test bypasses refresh timing | Medium; factory marked implemented in ec9a22c | Low "Overlay unit test skips the real refresh wait" | not raised | True at ec9a22c: `_refresh()` (test lines 292-301) still writes `_map_overlay_last_refresh_msec`; ec9a22c added a "waits for the refresh interval" assert first. Only the player smoke test waits for real, for the biology layer. |
| Wind refresh rescans unchanged columns | Medium; fixed in ec9a22c | not raised | not raised | Fixed: reader compares storage or publisher signature, no per-cell scan at refresh. |
| Window frame time | Medium "Wind speed-up has no window frame timing"; dismissed by factory dispute | Low; text: "This is the known factory gap: the PR lists it as pending and does not claim a frame-time gain." | Low, merged with marker cost: "Wind-overlay frame cost and marker cost are unmeasured" | PR and feature-status record window timing as pending; no frame-time gain is claimed. Low in both replays, so the drop from Medium is not attributable to the instructions. |
| Count table will not render | Low; marked resolved | not raised | Low "Overlay evidence table renders as plain text" | **Still broken at ec9a22c**: `feature-status.md` header has 9 columns, delimiter row 10. The instructions' "no findings on table formatting" line is the likely reason it was not raised. |
| Wind marker cost | Low "not documented" | Low "Wind marker cost goes unmeasured": `validate_values` adds three hash updates per cell on every daily climate solve | Low (same finding as frame time; also names the three per-cell hash updates) | True: `runtime_climate_physics_state.cpp` lines 60-63 at ec9a22c. The instructed run says "the ticket asks for" the trade-off; issue 66 does not, the withdrawn #61 did. |
| Savings figures disagree | not raised | **Medium** "Overlay savings figures disagree" | not raised | True: PR 72 body says requests 33→35 / 29→38, generations 9→1 / 9→6 (8 and 3 fewer); feature-status at ec9a22c says 50 requests, 10→1 / 10→6 (9 and 4 fewer). At 45a701a the doc table matched the body; ec9a22c re-measured and updated the doc, not the PR body. The PR merged with the stale body. |

Not raised by any run: a missing input in the skip check. My own check found none: the elevation bake reads only
`elevation_arr`, the wind bake only `wind_x/y/speed_arr`, plus cell count and LUT size, and the skip check
compares each (storage or signature, `cell_index_revision`, `cell_lut_layout_revision`, image and texture size,
mode, texture binding).

## Attributable to the instructions (one run each)
- Gained: the stale-figures Medium (matches "numbers from a different input"), the test-bypass Low (matches
  "tests loosened to pass"), and the frame-time reasoning text quoting the known gap.
- Lost: the valid table-render Low, suppressed by "do not spend findings on … table formatting".
- Not attributable: frame time at Low (Low in the control too); marker cost (raised in both).

## What else differed between runs
- The original findings were raised on 45a701a; ec9a22c fixed two of them (rescans; the test got an extra
  assert but still bypasses timing), so the rescan finding cannot reappear.
- The original run 2142920 on ec9a22c was incremental after fixes (the Workflow tab's fix-loop optimization is on);
  the replays are first full reviews of ec9a22c.
- PR 77/78 bodies have one extra line saying they are replays; PR 78's also says the instructions were cleared.
- Reviews are not deterministic; each configuration ran once.
- Display settings did not change; the comment layout is the same (grouped by severity, Low collapsed).

## Decision applied (2026-11-24)
After the comparison the Issue finding agent text was adjusted (1,960 characters, saved and checked after a reload): `issue-finding-instructions-adjusted.txt`. Two edits: loosened tests are raised as Medium, and formatting that breaks how evidence renders is flagged.
