# Day 18 evidence: one failed GitHub Actions job on PR 75

## The failed job

- PR: [PR 75](https://github.com/hrhgit/Project.Keynes/pull/75) (perf change check skill, merged 2026-11-25)
- Failed job: [run 45551042722 / job 138992020271](https://github.com/hrhgit/Project.Keynes/actions/runs/45551042722/job/138992020271), workflow "Runtime quick checks", job `architecture-guards`, attempt 1, 2026-11-25 05:04 UTC
- Failed commit: `b05f8fc9e` (PR head at the time)
- Kind: test step failure (not lint)

Source log (`source-log/job-138992020271-attempt1.log`):

| Step | Result in the log |
|---|---|
| Static architecture guards | all guards ran, no `::error::` |
| Factory tests | `Ran 211 tests in 7.910s` / `OK` |
| Performance tool tests (`python -m unittest discover -s tools/perf/tests -v`) | `ImportError: Start directory is not importable: 'tools/perf/tests'`, then `##[error]Process completed with exit code 1.` |

The same error ends four other failed `architecture-guards` jobs on 2026-11-25 (three on PR 75 at `1e600414e`, `7a08465fe`, `2801758a5`; one on PR 76's branch at `ac4bfbd9a`): `source-log/other-failures-same-error.txt`.

## Qodo CI failure feedback

Commented `/checks "https://github.com/hrhgit/Project.Keynes/actions/runs/45551042722/job/138992020271"` on PR 75 at 2026-11-26 07:33:43 UTC.
Qodo replied 11 seconds later ([comment](https://github.com/hrhgit/Project.Keynes/pull/75#issuecomment-7185593065), `qodo-checks-reply.json`):
the `/checks` command was deprecated on 1 October 2026 and is no longer available. Qodo's sunset page lists `checks` with "No direct replacement".
**No CI failure summary was produced, so there is none to check against the log.**

What Qodo did say about this failure came from its code review, not from CI feedback: finding `9f64a900` on `1e600414e`
(`qodo-finding-9f64a900.json`, [inline comment](https://github.com/hrhgit/Project.Keynes/pull/75#discussion_r4689311731), posted 02:08:43 UTC, 1 min 40 s after the first of these jobs failed at 02:07:03):
"The new test step fails on every pull request", action required, at `runtime-checks.yml:60`:
"the job's sparse checkout does not include `tools/perf/`. On every pull request, the start directory is absent". It cites lines 17-33 (the checkout list) and 58-60 (the step).

Checked against the source logs:

| Qodo finding says | Source log / tree at the failed commit |
|---|---|
| the Performance tool tests step fails | yes: that step, exit 1 |
| because the start directory is absent | yes: `Start directory is not importable: 'tools/perf/tests'`; the directory exists in the commit (`git ls-tree b05f8fc9e -- tools/perf`) |
| the sparse checkout lacks `tools/perf/` | yes: `runtime-checks.yml` at `b05f8fc9e` lists `/tools/ci/`, `/tools/factory/`, ... and no `/tools/perf/` |
| on every pull request | consistent: all five failed jobs end with the same error; a run on another PR (76) fails the same way |
| (not stated) | the earlier steps passed: guards clean, 211 factory tests OK, so the job failed only on this step |

Its finding status is now `implemented`; Qodo's review session for PR 75 is `completed`, `review_complete: true`, at `b71345d39`.

## What the coding agent got and found

Codex (`gpt-6-luna`, high, via Claude Code) got: the job URL, the failed commit, the verified log lines above, Qodo's `/checks` reply,
and an instruction to read only the failed commit (not later commits), test one cause, reproduce locally and propose a diff without applying it (`codex/prompt-1.md`).
It did not get Qodo's code-review finding.

- First reply (`codex/reply-1.md`, in Chinese): cause (b), the workflow checkout does not contain the files; proposed adding `/tools/perf/` to the sparse checkout. It skipped the reproduction.
- After a follow-up asking for it (`codex/prompt-2-resume.md`, `codex/reply-2.md`): exported `b05f8fc9e`, built a tree with only the job's checkout paths, and ran the step's command:

| Tree | Exit | Last lines |
|---|---|---|
| sparse (the job's checkout list) | 1 | `ImportError: Start directory is not importable: 'tools/perf/tests'` |
| full commit | 0 | `Ran 88 tests` / `OK` |
| sparse + `tools/perf/` (the proposed diff) | 0 | `Ran 88 tests` / `OK` |

I reran the same three commands in Codex's trees: same exit codes (`repro/my-rerun-*.log`).

Diagnosis: a workflow configuration problem (the checkout omits the tested directory), not broken code and not a transient runner problem.
Codex's proposed diff is the same one-line change as the actual fix (`fix-workflow.diff`).

## The fix and the follow-up run

The fix had already landed on 2026-11-25, before this investigation: commit `b71345d39` ("... CI checks out tools/perf") adds `/tools/perf/` to the `architecture-guards` sparse checkout.

- Follow-up run at the fix: [run 45551668939 / job 138994037751](https://github.com/hrhgit/Project.Keynes/actions/runs/45551668939/job/138994037751), attempt 1, commit `b71345d39`, **success**. Performance tool tests: `Ran 88 tests` / `OK` (`source-log/job-138994037751-fix-commit.log`), the same count as the local reproduction.
- Qodo review of the fix commit: review session `completed`, `review_complete: true` at `b71345d39`; finding `9f64a900` `implemented`.

Rerun of the failed job itself (to see the unchanged commit fail again today): `gh run rerun 45551042722 --job 138992020271` at 2026-11-26 07:37 UTC was accepted,
but the run stayed `queued` with no attempt-2 job for 27 minutes (checked until 08:04:10 UTC). `gh run cancel` was then refused with "Cannot cancel a workflow run that is completed"
while the API still reported `status: queued`. Inference, not checked: PR 75 is merged and its branch deleted, so the pull-request ref the rerun needs may be gone.
So there is no attempt 2; the deterministic failure is shown by the five failed jobs across four commits and by the local reproduction.

## Not established

- Qodo's CI failure feedback could not be tested: `/checks` is gone and has no replacement. Automatic CI feedback (`enable_auto_checks_feedback`) was not tried; Qodo settings were left unchanged.
- A passing job shows only that these checks ran green at `b71345d39`, not that the perf tool works end to end.

## Files

| File | What it is |
|---|---|
| `source-log/job-138992020271-attempt1.log` | Full log of the failed job |
| `source-log/other-failures-same-error.txt` | The final error lines of the four other failed jobs |
| `source-log/job-138994037751-fix-commit.log` | Full log of the passing job at the fix commit |
| `qodo-checks-reply.json` | Qodo's reply to `/checks` |
| `qodo-finding-9f64a900.json` | Qodo's code-review finding on the failing step, with its citations, and the review session state |
| `codex/` | The two prompts given to Codex and its two replies |
| `repro/` | Codex's reproduction outputs and my reruns |
| `fix-workflow.diff` | The workflow change between the failed commit and the fix |

Redaction: local paths replaced with `~/` or `<scratch>`. The job logs are GitHub's own; tokens in them are already masked as `***`.

AI use: Codex investigated the failure; Claude Code picked the job, checked the logs, wrote the prompts, reran the reproduction and wrote these notes under the author's direction; Qodo reviewed the PR.
Project.Keynes is a pre-existing project with a collaborator (HkingAuditore).
