# Day 14 check: approval workflow and guard

All times UTC, 2026-11-25. Every value below is copied from a tool output, the GitHub API, the Qodo CLI or the factory's run records; nothing is estimated.

## Configuration
| Step | Evidence |
|---|---|
| Predictions committed before either PR existed | [predictions.md](predictions.md) |
| Workflow "Keynes quality gate: label PRs with no Medium+ findings" filled in: scope `hrhgit/Project.Keynes`; If no findings at Medium or higher, all categories and finding types; Then add the Qodo approved label; no auto-approve | [workflow-form.png](workflow-form.png) |
| Saved inactive, re-read, then activated | [workflow-active.png](workflow-active.png) |
| Approval guard, first save: the portal stored "Whole repository" and dropped the path. Caught on reopening, before any test PR was reviewed | [guard-first-save-whole-repo.png](guard-first-save-whole-repo.png) |
| Guard re-saved with path `tools/factory/**` and reloaded | [guard-saved.png](guard-saved.png) |

## Inside the guarded path: PR 84
- Change: `judge()` in `tools/factory/verdict.py` sends a closed finding with an unknown severity to a person. Files: `tools/factory/verdict.py`, two test files, `docs/factory/quality-gate.md`. Written by Claude Code.
- Opened 06:54:06Z; `no-auto-merge` added 06:54:08Z.
- Qodo review run 2149029 on `cc56ceeb5`: `review_complete: true`, 0 findings ([pr84-review.json](pr84-review.json)).
- GitHub label events: only `no-auto-merge`; no Qodo approved label, no approval ([pr84-label-events.json](pr84-label-events.json)).
- PR Triage: the page shows "opened" and "Review completed: No new findings" ([pr84-triage.png](pr84-triage.png)). The data behind it records `merge_policy_evaluated`, decision `surface`, eligibility `ineligible` ([pr84-triage-data.md](pr84-triage-data.md)).
- Merged by me at 09:49:30Z as `17393b470`, after a complete clean review of its head and green CI.

## Outside the guarded path: issue 82 and PR 85
Issue 82: the headless perf recorder sometimes exports 49 of 50 rows. The factory (Codex) worked it; three runs, each stopped with `NEEDS_HUMAN` in the factory's run record:

| Run (local start) | Factory's reason | What I did |
|---|---|---|
| 82-20261124-225757 | "the ticket has no '## Acceptance criteria' section" | Added the criteria to the issue, re-labelled |
| 82-20261124-230802 | "the plan check was rejected by the allowlist: tools/ci/check_golden_determinism.py --runs 3 --write-candidate ..." (and `--compare-to`) | Did not widen the allowlist; added guidance to the ticket and re-labelled. The next plan passed |
| 82-20261124-234845 | Opened PR 85, then "the fix-and-review loop stalled on the same findings" | Took over (below) |

Qodo reviews of PR 85, from `qodo read pr-review-session findings --extended`:

| Head | Run | Complete | Findings |
|---|---|---|---|
| `b1b52c489` | 2150657 | true | 5 remediation-recommended, 1 informational |
| `2ba168376` | 2152440 | true | 5 marked implemented by the factory's fixes; 1 open: "Committed-fix quick measurement is still pending" |
| `45d866b22` (docs only) | 2153199 | false (skipped) | same |
| `45d866b22` after `/review` | 2153312 | false (skipped) | same |
| `1b8b12241` (master merged in) | 2153392 | false (skipped) | same; then I closed the open one (below) |

Saved: [pr85-review-1b8b122.json](pr85-review-1b8b122.json).

The open finding asked for the PR's acceptance criterion 2: a 50-day run on the committed fix exporting 50 rows. The factory cannot run it inside its job, so its loop repeated. I ran it with `tools/perf` on `2ba168376` (the head's code; later heads change only the PR body and a merge of master): `python3 tools/perf/perf_change_check.py measure HEAD --tier quick --budget 0`, exit 0, three rounds of 50 rows each (days 6–55, contiguous), golden-day check passed. Posted as a PR comment and ticked in the PR body.

Then, at about 11:37Z, I marked that finding implemented in Qodo with the measurement as the explanation. The call returned `implemented` with `failed_effects: ["merge_policy"]`; a retry returned the same.

Result for the outside-path PR:
- GitHub label events: `no-auto-merge` and `agent-needs-help` only; no Qodo approved label, no approval ([pr85-label-events.json](pr85-label-events.json)).
- PR Triage data: the workflow's latest evaluation is `decision: unknown`, `reasonCode: incomplete_review` on `1b8b12241` ([pr85-triage-data.md](pr85-triage-data.md)).
- Prediction was "Qodo approved label if Qodo's complete review of the head leaves no open High or Medium finding". That condition was never met on a head: the last complete review (`2ba168376`) left one open finding (action level `remediation_recommended`), and the later reviews were skipped as incomplete. So no label, as the prediction's own condition says, and Qodo records the reason as an incomplete review, not the guard.
- CI green on `1b8b12241` (architecture-guards, authoring-and-thread-lifetime). Merged by me at 11:38:55Z as `62ba798d6`, on my instruction, knowing the head's review was skipped; the last complete review covered the same PR code. Issue 82 closed by the merge.

## The two PRs side by side
| | PR 84 (inside `tools/factory/**`) | PR 85 (outside) |
|---|---|---|
| Last review of the head | complete, 0 findings | skipped, incomplete |
| Workflow record | `surface`, `ineligible` | `unknown`, `incomplete_review` |
| Qodo approved label | no | no |
| Merged by | me, after a complete clean review | me, on my decision, with an incomplete head review |
