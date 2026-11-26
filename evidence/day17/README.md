# Day 17 evidence: Agent Session Review of PR 85

- Ticket: [issue 82](https://github.com/hrhgit/Project.Keynes/issues/82) (headless perf recorder intermittently exports 49 of 50 rows, exit 6)
- PR: [PR 85](https://github.com/hrhgit/Project.Keynes/pull/85), implemented by Codex (gpt-6.2-sol) through the factory, merged as `62ba798d6`
- Reviewed commit: `1b8b122418c17a10d3a182704ac314e9c6b3aa21` (PR head). `git diff 1b8b12241 62ba798d6 -- tools/perf` is empty, so the code under review is the same at the merge commit, where the checks ran.

## Source and expectation

The plan the factory posted for issue 82 (PR 85 body, "Plan"):

- "The edit belongs in `headless_perf_record.gd`, `perf_recorder.gd`, and `perf_recorder_test.gd`."
- "The benchmark requires numeric `tick_idx`, `speed_multiplier`, and `t_sus_ms` on every row."
- Step 4: "Verify the diff contains only recorder and test files."

Expectation (an assumption to check, the plan does not say it outright): the shared comparison tool `tools/perf/perf_change_check.py` is untouched, and comparing a commit before PR 85 with one after it still yields metric results.

## Decision investigated

Agent Session Review, Decisions page (`decisions.png`): "The perf comparison refuses to compare runs recorded with different recorder methods: needs_human, no metric rows", status **Unplanned**.

Where it came from: commit `2ba168376` ("address Qodo findings ... 5844bc28 ...") answers Qodo's Medium finding on `b1b52c489`,
"Headline throughput changes meaning across this commit". Qodo's point: the new recorder takes throughput from worker commit stamps instead of the main-thread clock,
and archived records were keyed only by `METHOD_VERSION = 2`, so a before/after comparison would report a change caused by the method.
The agent's response, outside the plan:

1. `perf_change_check.py:45` `METHOD_VERSION = 3`.
2. `headless_perf_record.gd:556-562` prints `recorder_method=day_records_worker_v1` (`day_records_main_v1` with zero warmup).
3. `perf_change_check.py:840-848` labels a runner with no marker `unversioned:<sha256 of the runner script>`.
4. `perf_change_check.py:1052-1069` (`assess`): when base and head methods differ, `rows = []`, reason `incompatible recorder methods: <base> vs <head>`, status `needs_human` (or `fail` if there are other reasons). The daily result hashes are still compared.
5. `perf_change_check.py:111-141`: the daily CSV must leave `t_sus_ms` empty (answering Qodo finding `2c087197`, "Unmeasured t_sus_ms is written as a fake zero"), the opposite of the plan's "numeric `t_sus_ms` on every row".

Code map (`codemap.png`, flow "A base before PR 85 meets a head after it" in `builder.json`): runner `_run` → `perf_round` → `assess`, pinned by
`test_refuses_throughput_comparison_between_different_recorder_methods` (`tests/test_perf_change_check.py:571-585`).

## Consequence checked

**Real comparison across PR 85** (`compare/`):
`python3 tools/perf/perf_change_check.py compare c81ebf871 62ba798d6 --tier quick --budget 0 --unmeasured "..."`
with the tool from `62ba798d6`; base is PR 85's parent on master, head is its merge. Both sides measured fresh, 3 rounds each, 259 s.

- `PERF_CHECK_RESULT` status `fail`, exit 1. Reasons:
  - `base round 3: godot exit=6; result rows=51 expected 50; perf csv has 51 data rows, expected 50` (the old recorder miscounting rows, the class of bug issue 82 is about)
  - `incompatible recorder methods: unversioned:fdcd453dd9e3 vs day_records_worker_v1`
- `0 metrics compared`.
- "the daily per-domain hashes of base and head are identical": the correctness check still ran.

**The same two records judged without the refusal** (`compare/counterfactual.py`, `compare/counterfactual.txt`; both sides relabelled as one method, which is what the tool did before PR 85):
413 metric rows instead of 0. Headline medians shift:

| Metric | Base rounds | Head rounds | Change |
|---|---|---|---|
| `result.run_ms` | 1516.9, 1680.9 | 729.1, 631.2, 729.3 | -54% |
| `auth.authoritative_days_per_second` | 81.1, 65.4 | 80.4, 96.7, 83.6 | +14% |
| `result.generation_ms` | 10845, 12634 | 11252, 9615, 9765 | -17% |

PR 85 changes no native code (`native_changed=false`) and the daily hashes match, so the simulation is unchanged. Reading (inference): these shifts come from how the runner measures, which is what the refusal keeps out of a verdict.

**Unit tests** at `62ba798d6`: `python3 -m unittest tools.perf.tests.test_perf_change_check`, 75 tests, OK (`compare/unit-tests.log`).

## Conclusion

Accept. Without the refusal, a comparison spanning PR 85 would have reported a 54% faster run and 14% more throughput from a change that touched only the recorder and the runner.
The plan's file list and `t_sus_ms` requirement were written before Qodo found the problem; leaving the tool unchanged would have kept that misleading result.
Marked Accepted in Agent Session Review (`decisions-accepted.png`, local mark; Publish unused, nothing posted to GitHub).

## Not established

- The `needs_human` outcome was not observed in the real run: the old recorder's 51-row round made it `fail`. Only the unit test shows `needs_human` with no rows.
- What happens to a perf PR branched before PR 85 (its merge base predates the change) was read from the factory docs, not run.
- The factory config at master lists `tools/perf/` as off-limits to the agent (added in `2d1f9d651`), but the installed factory runner (`cf82edd53`) predates it, so its scope check did not stop this change. The factory stopped the run as NEEDS_HUMAN for a different reason (the fix-and-review loop stalled) and a person merged the PR.
- Qodo's review at `1b8b12241` reports `review_complete=false`; its six findings are resolved, but that is not a complete review.
- The `t_sus_ms` change was not followed further.

## Files

| File | What it is |
|---|---|
| `decisions.png` | Decisions page, the unplanned decision expanded: plan text, agent decision, consequence |
| `decisions-accepted.png` | Same page after Accept: Answer column reads "Accepted" |
| `codemap.png` | Code map, Code changes for `perf_change_check.py`, diff of `assess` at lines 1035-1071 |
| `pr85-agent-session-review.html` | Agent Session Review HTML export of the session |
| `enrich.json`, `builder.json` | The story, decisions, layers and Code map input given to Agent Session Review |
| `compare/` | Real comparison report and log, the counterfactual script and output, unit-test log |
| `exit6-decision/` | An earlier check of the planned exit 6 decision in the same PR: screenshots, test and one-line mutant logs (93 checks, 0 failures; mutant 1 failure) |

Redaction: the local home directory in logs and the export is replaced with `~/`. No access key or local review URL is included.

AI use: PR 85 was written by Codex in the factory; this review, the Code map input, the counterfactual script and these notes were made with Claude Code
under the author's direction; Agent Session Review and the findings it shows are Qodo's. Project.Keynes is a pre-existing project with a collaborator (HkingAuditore).
