# Day 19 evidence: one question about Qodo's silent-fallback findings

**Question:** Qodo keeps flagging silent fallbacks (a failure that returns quietly instead of reporting an error). Do they share one code shape a deterministic check could catch, or is the gap in what the factory tells Codex before it writes code?

**Data source:** Qodo Analytics is not available in this trial workspace (no sidebar entry, `/analytics` redirects home, no "Grant Analytics access" in Settings for the admin account). The Findings page and `qodo read pr-review-session findings` were used instead.

## Scope (`findings-page/`)

- Filters: Repository = Project.Keynes, Category = Reliability, last 30 days by when Qodo raised the finding (2026-10-27 to 2026-11-26). Severity, type, state and author left at All.
- Captured 2026-11-26, about 09:30–09:55 UTC. `scope.png` is cropped to the filter bar and table (the sidebar with the account email is removed).
- `reliability-last-30-days.txt`: all 69 rows (index | title | PR | repo | state | severity | category | type).
  - 69 findings on 25 PRs. High 25, Medium 37, Low 7. Bug 39, Rule violation 28, Requirement Gap 2.
  - States: Resolved 50, Dismissed 7, Ignored 2, Pending 10. The 10 pending are on review PRs 19–21, closed unmerged.
- `extended/pr*.json`: `qodo read pr-review-session findings --extended` for every PR with a rule-violation row. With `--extended`, each rule citation carries the rule name and URL; without it some citations show only a number.
  - 22 of the 28 rule violations cite "errors fail loudly instead of falling back silently" (rule 4948321). They are on 12 PRs: 2, 7, 20, 36, 38, 52, 59, 73, 74, 85, 86, 88. Five of them (36, 38, 73, 85, 88) are factory issue runs.
  - An earlier count without `--extended` gave 19 findings on 10 PRs, because some citations showed only the rule's number. The correction is [PR 92](https://github.com/hrhgit/Project.Keynes/pull/92) (`docs/factory/corrections.md`) and the note added to PR 90's description.

## Findings read (`inspected/`)

| Finding | PR | Code at review | Outcome |
|---|---|---|---|
| `41b96796` Invalid frame reads as unexplored fog | 74 | `vision_solver.gd:317` at `41d3b5156` | Resolved, fixed in `fe4ee78e0` |
| `665d91a0` Failed map reads drop out with no error | 88 (factory) | `mapgen_native_daily_runtime.gd:69` at `99f5d9b48` | Resolved, fixed in `0e0395aae` |
| `963d6938` Missing ecology data falls back silently | 73 (factory) | `cell_lut_baker.gd:562` at `9fad268f5` | Resolved, fixed in `db8a24660` |
| `d99e4f8c` Failed ps lookup goes unlogged (counterexample) | 86 | `perf_change_check.py:524` at `2c3a01c22` | Dismissed after Codex showed the reviewed code already raised on `ps` failure |

Files for PRs 36, 38, 52 and 59 are the other findings checked in the lint experiment.

## Lint experiment (`lint-experiment/`)

`guard_scan.py` flags an `if`/`elif` guard in GDScript whose short body (at most 3 lines) returns a value without logging (`push_error`, `push_warning`, `printerr`, `assert(` and similar). `run_experiment.py` runs it at the commit Qodo reviewed for each PR and counts flags on added lines, and flags within 3 lines of a fail-loudly finding. Output: `experiment-output.txt`.

| PR | Flags on added lines | Next to a finding |
|---|---|---|
| 36 | 0 | 0 |
| 38 | 0 | 0 |
| 52 | 55 | 1 |
| 59 | 7 | 1 |
| 73 | 9 | 0 |
| 74 | 19 | 3 (one finding) |
| 88 | 4 | 1 |
| Total | 94 | 6 |

On the 7 finding locations the scan catches 4 (74, 88, 59, 52; the hit on 38 is a line that existed before the PR). It misses 73 (a flag variable cleared) and 36 (an error downgraded to `push_warning`). Decision: no lint.

## The change (`pr90/`)

[PR 90](https://github.com/hrhgit/Project.Keynes/pull/90), merged as `5e2653cd2`. Every factory prompt that lets Codex change code now carries all 14 rules from `docs/factory/qodo-rules.json` with their examples; only the read-only plan prompt is exempt (`agent.PROMPTS_WITHOUT_RULES`).

- `pr90.diff`: the merged change.
- `qodo-review-1.json`: review of the first version (`c9cac7365`), 4 findings, all fixed in `420853cc6`: fix prompts without rules, a test that checked names only, examples dropped, the validator missing from `test_gates_refuse.py`.
- `qodo-review-2.json`: review of `420853cc6`, complete, no new findings. CI green.
- 245 factory tests pass. Negative controls: removing the placeholder from `fix-pr.md` fails 14 tests; dropping examples or truncating rule content fails 84.

## Replay (`replay/`)

Issue 83 (originally PR 88) re-run from PR 88's base with the same plan, model and effort, using the new implement prompt (first version: rule text without examples).

- `implement-prompt.md`: the prompt Codex got (local paths shortened to `~/`).
- `codex-report.md`, `replay.diff`: Codex's report and the change at `fe92d5b74` (22 files, +877/−55).
- `qodo-local-review-attempt1.json`, `attempt2.json`: `qodo review` failed both times (base checkout timed out after 120 s), so the replay went to [PR 91](https://github.com/hrhgit/Project.Keynes/pull/91), closed unmerged.
- `qodo-review-pr91.json`: review of `fe92d5b74`, complete, 4 findings. No fail-loudly finding. `8b8d3138` (remediation, observability): the first failed map read is logged with `push_error`, repeated failures are not. Two action-required bugs unrelated to the rule (`1753dff8`, `c9e920ed`) and one informational.
- `qodo-review-pr88-original.json`: the original PR 88 review at `99f5d9b48`, with the action-required fail-loudly finding `665d91a0`.

One sample. Codex could not run the visible-window acceptance check in the replay.

## AI assistance

Claude Code read the findings, ran the lint experiment and wrote PR 90 under the author's direction. Codex ran the replay. Qodo reviewed PRs 90 and 91.
