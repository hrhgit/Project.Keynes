# Day 12: one expectation from #61 checked against PR 69

## Source and expectation
- Ticket: https://github.com/hrhgit/Project.Keynes/issues/61 (saved: `issue61.json`), closed by PR 69's merge on
  2026-11-24 05:26 UTC.
- PR: https://github.com/hrhgit/Project.Keynes/pull/69, base merge-base `7a9fa73`, head `22ee108`, one file
  (`docs/architecture/feature-status.md`, +55). Merged as `14235fe`.
- Expectation (#61, 验收标准, third item): 在电脑的 50 倍速玩家窗口交替复测，列出未变/变化发布数、真正跳过的编码次数、
  标记维护成本和发布帧 P95。若整体表现稳定变差或标记成本抵消收益，记录数据并撤回该方案。
  The ticket's last line repeats it: 性能结果按实测桌面配置报告，工厂使用电脑完成全部验收。

## What I checked (2026-11-24)
| Part of the expectation | Check | Result |
|---|---|---|
| Withdraw the candidate | `git apply --check issue-61-candidate.patch` in a worktree at `22ee108`; `git grep` for the three identifiers it adds (`installed_wind_version`, `_set_fixture_wind_version`, `wind_writeback_reused`) at `22ee108` and at fork master `a5f5564` | Patch applies cleanly (its code is absent); 0 files contain any identifier at either commit. Met. |
| Record the data | Compared the doc table in `22ee108` with the raw `headless-trials/summary.json` (saved: `pr69-headless-trials-summary.json`) for all three rounds: unchanged/changed publications, copied arrays, encodes, uploads, skipped counts, marker cost, publish-frame and all-frame P95 | Every value matches. Met. |
| Measure in the player window | Same `summary.json`: `config.display = "headless"`, `window_size = (0, 0)`, `viewport_size = (64, 64)`, `all_draw_p95_ms_per_range = [null, null, null]` in every run; the doc says 真实窗口未完成测量 | **Not met.** All three rounds ran headless. The withdrawal rests on headless whole-frame P95, whose slowest 5% the doc places in frames with no weather publication, at a one-minute load of 5.58–8.23. |
| Ticket state | `gh issue view 61` | Closed by the merge although the window criterion is unchecked and unmet. |

## Qodo reviews of the same code
Replay PRs point at the same commits; `git diff 7a9fa73 22ee108` and `gh pr diff 69` have the same sha256
(`b3267ec0…8969f9`). Bodies differ only in the ticket reference (`pr79-vs-pr80-body.diff`): PR 80 drops
`Closes #61` and the `#61` in the agent report and the title. Both bodies still name parent ticket #60.
Repository custom instructions from Day 11 (adjusted text, 1,960 characters) were active for every replay run.

| Run | PR | Ticket reference | Effort | `review_complete` | Findings |
|---|---|---|---|---|---|
| 2126969 (original) | 69 | `Closes #61` | skip | false | 0 ("judged trivial") |
| 2147872 | 79 | `Closes #61` | skip | false | 0 |
| 2147871 | 80 | none | skip | false | 0 |
| 2147891 | 79 | `Closes #61`, `/agentic_review` | skip | false | 0 |
| 2147890 | 80 | none, `/agentic_review` | skip | false | 0 |
| 2147899 | 79 | `Closes #61`, `/agentic_review` + router instruction "do not skip it as trivial" | standard | true | 0, "Requirement gaps (0)" |
| 2147898 | 80 | none, same command | standard | true | 1 Medium Requirement gap, citing `source_type: ticket` #60 |

The PR 80 finding ("Speed test table omits sample counts and spread") is grounded in #60's third criterion
(报告……发布的帧间隔 P95、样本数和波动。注明有窗口或无窗口). True for the page: the table gives counts and P95 but no
frame sample count or spread; both are only in `summary.json` (spread not even there). It is not my expectation.

Neither full review raised the player-window criterion of #61. PR 79's review has no finding and no citation, so
nothing shows whether it read #61. PR 80 shows Qodo reads a ticket referenced in the body.

## What changed in the factory
The merge gate only read `status`; a `completed` session with `review_complete: false` merged PR 69. Fix:
https://github.com/hrhgit/Project.Keynes/pull/81 (`decide()` and `judge()` require `review_complete: true`;
refusal tests; with the old gate code the watcher test gives `'merge' != 'stop'`).

Qodo's review of PR 81 at `efd9603` (run 2147951, standard, `review_complete: true`; saved:
`pr81-review-run2147951.json`) had one action-required finding: "Changed gates can drop refusal coverage" —
`decide()` and `judge()` were not in `GATES` in `test_gates_refuse.py`, and their names did not match `NAME_PARTS`.
True. Fixed in `bfabbba`: both are registered with inputs they must refuse, the scan matches both names, and a
clean case must still merge and be READY. Against the old gate code the three `review_complete` cases for
`decide()` fail and every `judge()` case errors (the old `Facts` has no `review_complete`). 214 factory tests pass.
Qodo's review of `bfabbba` (run 2147994, `review_complete: true`; saved: `pr81-review-run2147994.json`) marks
that finding `implemented` and raises no new one.
