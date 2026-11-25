---
name: project-keynes-perf-change-check
description: Verify a Project.Keynes performance change before it is called done. Use when a ticket, PR or commit claims the simulation got faster or cheaper, or when a change touches a hot loop, scheduling, caching, publishing or display refresh. It proves the daily results did not change, then compares every headless performance metric between the base and head commits on a quiet machine, and stores each measurement in a long-lived archive so later checks reuse it. Do not use it for windowed frame time or GPU work.
---

# Performance change check

One script does the measuring and decides the result: `tools/perf/perf_change_check.py`.
The verdict is the script's `PERF_CHECK_RESULT=` line and `report.md`, not your reading of the
numbers. This skill says when to run it, with what, and when to stop and ask.

The check uses only git, Godot, a C++ toolchain and Python. It does not need Qodo or network access.

## Inputs

| Input | Where it comes from | If missing |
|---|---|---|
| Base commit | The PR's merge base with `master`, or the commit before the change | Stop and ask |
| Head commit | The commit to verify. Commit first: the script measures commits, not a dirty tree | Commit, then run |
| Claimed metric(s) | The ticket's acceptance criteria, as a regex over metric names (`--claim`) | Stop and ask which metric the change should improve |
| Tier | `quick` for every performance PR; `full` for scheduling or threading changes and for large refactors | Use `quick` |
| Scenario | Default 60×40, seed 20260718, 3 foreign countries, 50× speed, 50 days | Keep the default so archive records stay comparable |

Tools: `godot` 4.6 on PATH or `--godot`/`$GODOT_BIN`; `scons` on PATH or `--scons`; Python 3.10+.

## Steps

1. **Find the metric names for the claim.** Metrics are named `result.*`, `auth.*`, `harness.*`
   (from the recorder's summary lines), `csv.<column>.mean|p95|max|per_day` (every numeric column of
   `perf_record_*.csv`), `waterfall.*` (full tier) and `rusage.*` (wall, CPU, peak memory).
   Run `python3 tools/perf/perf_change_check.py history` to see earlier records. A claim such as
   "economy market stage is cheaper" becomes `--claim 'household_market.*_ms'`.

2. **Run the comparison** from the repository root:

   ```sh
   python3 tools/perf/perf_change_check.py compare <base> <head> --tier quick \
     --claim '<regex>' [--claim '<regex>'...]
   ```

   The script compiles each commit's `template_debug` library (the one the headless editor loads)
   in one long-lived build tree, `~/.keynes-perf/build/` (or `$KEYNES_PERF_HOME`), so SCons only
   recompiles what changed since the last build. It copies the library into a per-commit worktree
   under `~/.keynes-perf/worktrees/`, imports the project, and then:
   - checks the machine first: it waits while the 1-minute load average is above 0.5 per CPU or
     another Godot, scons, compiler or linker process is busy, and gives up after 30 minutes
     (`--max-wait`), exiting 75 with status `deferred`;
   - runs `tools/ci/check_golden_determinism.py` twice on each side and compares base and head
     daily per-domain hashes field by field (full tier also runs
     `tools/ci/check_runtime_load_consistency.py`);
   - runs `tests/game/headless_perf_record.gd` three rounds per side, alternating, and rejects any
     round with a non-zero exit, a missing or short CSV, `fatal=true`, ledger failures, no economy,
     a synthetic start or too few countries;
   - compares every metric and writes `report.json` and `report.md`.

   The first build on a machine compiles godot-cpp and every source; later builds are incremental.
   When the archive already holds a record for a commit with the same scenario, machine,
   toolchain and method version, that record is reused and the commit is not built or run again.
   This is the normal case when a PR comes back from review: only the new head is measured.

3. **Read the verdict line** `PERF_CHECK_RESULT={"status": ..., "reasons": [...], "report": ...}`.

   | Status | Exit | Meaning | What you do |
   |---|---|---|---|
   | `pass` | 0 | Results unchanged, every claimed metric improved, no headline metric regressed | Report it as below |
   | `needs_human` | 2 | A claim matched no metric or did not improve, or a headline metric regressed beyond noise | Stop. Report the reasons and the report; do not reword the claim to fit |
   | `fail` | 1 | Daily results differ, a repeat check failed, a round was invalid or a build failed | Stop. A result difference is a correctness bug, not a performance question; fix the root cause (AGENTS.md rule 1, rule 4) |
   | `deferred` | 75 | The machine stayed busy | Run again later; never lower `--max-load` to get through |

4. **Run the change's own targeted test** (for example a byte-for-byte fixture named in the PR)
   separately and record its command and output. The script does not run PR-specific tests.

5. **Report** in the PR or hand-off: status, base and head commits, which side was reused from the
   archive, the claimed metrics' rows, the headline table, the counts of metrics improved, regressed
   and within noise, and the path of `report.md`. Say plainly that windowed frame time and GPU work
   were not measured.

## How the numbers are judged

- Timings (`*_ms`, `*_us`, rates, waits, `rusage.*`) count as improved or regressed only when the
  medians differ by more than 15% **and** the two sides' ranges do not overlap. Everything else is
  `within_noise`. One round per side is refused.
- Work counters (`bd_economy_scan_*`, `scan_steps*`, `*_epoch`, as per-day increases) and memory or
  capacity values (names with `bytes`, `memory`, `_mb`, `_kb`) that repeat exactly within
  each side are compared exactly: `less_work`, `more_work`, `unchanged`. A memory value that varies
  between rounds is judged like a timing. Other gauges have no better direction and are only
  `changed` or `unchanged`.
- Headline metrics: `result.run_ms`, `auth.authoritative_days_per_second`,
  `harness.adjusted_days_per_second`, `result.generation_ms`, `rusage.maxrss_mb`, `rusage.cpu_s`.

## Stop and ask instead of continuing

- No base commit, or the ticket names no metric to improve.
- The base itself fails the repeat check: the baseline is already broken; report it, do not compare.
- Daily results differ between base and head, even if the change was meant to change behavior:
  this check is for pure performance changes, and a behavior change needs a person's decision.
- The build or import fails on the base commit.
- The claim depends on windowed frame time, GPU work or a real player window.
- You are tempted to raise `--noise`, lower `--rounds`, edit the archive or delete a record to get
  a pass.

## Evidence kept

Records live under `~/.keynes-perf/records/<commit12>/<scenario>/<time-machine>/`: `record.json`
(identity, golden result, every round's metrics, machine load before each round), build and import
logs, golden logs and candidate, and per-round `godot.log`, `perf.csv`, `headless_session.json`
and `waterfall.csv`. Every record is appended to `~/.keynes-perf/index.jsonl`. Comparisons are in
`~/.keynes-perf/comparisons/<base>..<head>-<time>/`. Records are never overwritten; a changed
scenario, machine, toolchain or method version produces a new record.

## Sources

The headless recorder and its validity rules come from the `project-keynes-headless-perf` skill;
the timing-noise and counter conventions come from `compare_perf.py` in the
`project-keynes-runtime-hotloop-optimization` skill. Both were written before this check.
