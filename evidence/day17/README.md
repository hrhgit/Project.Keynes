# Day 17 evidence: Agent Session Review of PR 85

- Ticket: [issue 82](https://github.com/hrhgit/Project.Keynes/issues/82) (headless perf recorder intermittently exports 49 of 50 rows, exit 6)
- PR: [PR 85](https://github.com/hrhgit/Project.Keynes/pull/85), implemented by Codex (gpt-6.2-sol) through the factory, merged as `62ba798d6`
- Reviewed commit: `1b8b122418c17a10d3a182704ac314e9c6b3aa21` (PR head, the commit Qodo reviewed)
- Test commit: `2ba1683769f983dfe7a6ad8314f227f5dd59d7a5`. `git diff 1b8b12241 -- perf_recorder.gd headless_perf_record.gd perf_recorder_test.gd` is empty, so the three files under review are identical at both commits.

## Expected behavior and its source

Issue 82, item 2: "Fix the cause so a completed run always exports exactly one row per measured day.
Do not relax the check: exit 6 must still fire when rows really are missing."

## Decision followed

"Exit 6 fires on a short count or on any gap or reordering in the committed-day column"
(Agent Session Review, Decisions page, status "According to plan", source: ticket).

Code map path (`builder.json`, flow "A missing day reaches exit 6"):

1. `scripts/ui/perf_recorder.gd:577` `_on_day_records` appends one row per published day; line 583 skips a day already published.
2. `tests/game/headless_perf_record.gd:529` `_run` calls `_check_csv(output_path, first_measured_day, days)`.
3. `tests/game/headless_perf_record.gd:764-777` `_check_csv` reads `runtime_graph_simulation_committed_day` and requires `first_day, first_day+1, ...`; line 777 returns exit 6 unless the dates are in order and the count matches. It replaces the count-only `_csv_data_row_count` (base lines 810-822).
4. `tests/game/headless_perf_record.gd:721-727` prints the count message or "CSV days must be ordered from N through M" and exits 6.

## Observable consequence checked

`tests/game/perf_recorder_test.gd:368-383` (`_test_missing_committed_day`) publishes days 6 and 8, then 9 after the
window closes, and expects `_check_csv(path, 6, 3) == {rows: 2, exit_code: 6}` and `_check_csv(path, 6, 2) == {rows: 2, exit_code: 6}`.
The second call is the case the decision adds: the count matches, a day is missing, and the run still fails.

| Run | Command | Result |
|---|---|---|
| As merged | `python3 tools/ci/run_regression_checks.py --import tests/game/perf_recorder_test.gd --log-dir <dir>` | `93 checks, 0 failures` (`logs/perf_recorder_test.log`) |
| Mutant (`mutation.diff`: drop `ordered and`) | same | `93 checks, 1 failures`; the one failure is `[FAIL] matching row count still fails when the dates have a gap` (`logs-mutant/perf_recorder_test.log`) |

The mutation was reverted after the run. The test therefore fails if the date check is removed.

## Conclusion

Accept. The decision matches the ticket's instruction and a test guards it. The Accepted mark is a local
Agent Session Review mark (`decisions-accepted.png`); nothing was published to GitHub or to Qodo from the tool.

## Not covered

- Qodo's review at `1b8b12241` reports status completed with `review_complete=false`; all six of its findings are resolved, but that is not a complete review.
- Only this one decision was followed in depth. The session reports 618 of 799 meaningful changed lines outside any review layer; `tools/perf/perf_change_check.py`, `perf_recorder_graph.gd`, the docs and the other runner changes were not read in depth.
- PR 85's body leaves acceptance criteria 1 (full regression run: the agent reports 128 PASS but no aggregate exit) and 3 (the diff also touches `tools/perf`, docs and an ideology test) unchecked.

## Files

| File | What it is |
|---|---|
| `decisions.png` | Decisions page with the decision expanded: human instruction (issue 82 item 2), agent decision, consequence |
| `decisions-accepted.png` | Same page after Accept: Answer column reads "Accepted" |
| `codemap.png` | Code map, Code changes for `HeadlessPerf._check_csv`, diff at `headless_perf_record.gd:764-777` |
| `pr85-agent-session-review.html` | Agent Session Review HTML export of the session |
| `enrich.json`, `builder.json` | The story, decision, layers and Code map input given to Agent Session Review |
| `logs/`, `logs-mutant/` | Test output for the two runs above |
| `mutation.diff` | The one-line mutation used for the mutant run |

Redaction: the local home directory in logs and the export is replaced with `~/`. No access key or local review URL is included.

AI use: PR 85 was written by Codex in the factory; this review, the Code map input and these notes were made with Claude Code
under the author's direction; Agent Session Review is Qodo's tool. Project.Keynes is a pre-existing project with a collaborator (HkingAuditore).
