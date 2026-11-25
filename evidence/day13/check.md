# Day 13 check: skill `project-keynes-perf-change-check` on PR 72

Task: PR 72 (merged, head `ec9a22ce2ec3`), ticket issue 66. Claim: the elevation and wind overlays are rebuilt only when their own data changes.

Agent: Codex CLI (gpt-6.2-sol, effort high) in new app-server threads started in `keynes-wt-day13`. The threads have no fork or parent (`forkedFromId: null`, `parentThreadId: null`). Each run first searched `~/.codex/memories/MEMORY.md` for this task and found nothing (exit 1). Invocation: `use $project-keynes-perf-change-check to check PR 72` (`$name` is Codex's explicit skill mention).

| Run | Skill at | What happened | Result |
|---|---|---|---|
| 1 | `2801758` | Read SKILL.md. Found that `merge-base master` returns the head once a PR is merged, and used the merge's first parent `9ddb127`. Found that no headless metric measures the claim (`csv.tail_overlay_refresh_count.mean` is 0 on both sides). Stopped at step 1. | No check ran. The skill tied the daily-results check to `--claim` |
| 2 | `b05f8fc` | Used the new merged-PR base command and `--unmeasured`. My prompt said not to modify the repository, so it built a private clone with its own HOME and archive. That hid SCons, and the base build failed. After a steer it stopped to ask before the script's automatic worktree pruning | `fail` (build), no report |
| 2 retry | `b71345d` | Same thread. Shared archive. The first attempt was `deferred` (10-minute budget, two cold builds). The second reused both builds and ran 6 rounds | `fail`: head round 3, recorder exit 6, 49 of 50 CSV rows |

Run 2 retry report (`pr72-report.md`):
- The same-input repeat check passed on both sides. Daily per-domain hashes are identical between base and head.
- The claim is not measured headlessly; the reason is in the report.
- All 6 headline metrics are within noise. 409 metrics: 2 improved, 3 regressed, 140 unchanged, 264 within noise. Head has 2 valid rounds.

What I verified myself, from `~/.keynes-perf/records/*/record.json`:
- Base record `complete`; head record `invalid`. Golden passed on both sides.
- The two golden candidates are equal: 8 days, 8 domains.
- The head round-3 `godot.log` ends with `CSV row count mismatch: got 49 expected 50`.
- The checkout was clean at `b71345d` after the run.

Not done: the claim (overlay build and upload counts with each overlay open), windowed frame time and GPU work. Per the skill, the invalid round was not rerun until it passed.

Qodo on PR 75:
- Run 2148197 on `b05f8fc`: one new finding. `--unmeasured` and `--claim` were mutually exclusive, so a mixed claim lost its measurable part. Fixed.
- A finding open since `1e60041` was confirmed by the CI log: `Start directory is not importable: 'tools/perf/tests'`. Fixed.
- Run 2148233 on `b71345d`: standard, `review_complete: true`, no new findings. All 13 findings are implemented. CI passes, and the performance tool tests now run (88 OK).
