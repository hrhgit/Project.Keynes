# Investigate one failed CI job (read-only)

You are investigating why one GitHub Actions job failed on Project.Keynes. The repository is at `~/MyFiles/games/keynes` (use `git -C` on it; its working tree is unrelated, read commits only). Your working directory is a scratch directory. Do not modify any file, do not commit, do not push, do not run network commands. Use only `git show`, `git ls-tree`, `git log`, reading files and running local Python on files you extract to the scratch directory below.

## Facts already checked against the source log

- PR: https://github.com/hrhgit/Project.Keynes/pull/75
- Failed job: https://github.com/hrhgit/Project.Keynes/actions/runs/45551042722/job/138992020271 (workflow "Runtime quick checks", job `architecture-guards`, attempt 1)
- Failed commit: `b05f8fc9e` (full SHA b05f8fc9e is in the local repo)
- Source log excerpt (verified):
  - step "Static architecture guards": all guards ran, no `::error::` lines
  - step "Factory tests": `Ran 211 tests in 7.910s` / `OK`
  - step "Performance tool tests", command `python -m unittest discover -s tools/perf/tests -v`:
    ```
    ImportError: Start directory is not importable: 'tools/perf/tests'
    ##[error]Process completed with exit code 1.
    ```
- Qodo CI failure feedback: none was produced; see "Qodo feedback" at the end.

## What to do

1. Investigate ONE cause: why `tools/perf/tests` was not importable in this job. Read `.github/workflows/runtime-checks.yml` and the repository tree **at `b05f8fc9e` only** (`git show b05f8fc9e:<path>`, `git ls-tree b05f8fc9e -- tools/perf`). Do not read commits after `b05f8fc9e`; the point is to diagnose from the failed commit and the log.
2. Decide which of these the evidence supports, and say why: (a) the code under test is broken, (b) the workflow environment does not contain the files, (c) a transient runner problem, (d) something else.
3. If you can, reproduce locally without touching the repository: e.g. export the tree of `b05f8fc9e` restricted to the workflow's sparse-checkout patterns into the scratch directory, then run the same unittest command there; and run it on the full tree for contrast. Report the actual commands and output.
4. Qodo produced no CI feedback (below). Do not guess what it would have said.
5. Propose a change only if the evidence justifies one: give the exact diff (do not apply it) and the check that would confirm it.

Scratch directory you may write to: `<scratch>/`.

## Reply format

- Diagnosis (one paragraph), labelled: what the log shows vs what you infer.
- Evidence: file:line references at `b05f8fc9e`, commands run and their output.
- Anything in the log or code that a CI summary would need to mention.
- Proposed change (diff) or "no change", and the confirming check.
- What you did not check.

## Qodo feedback

Comment `/checks "<job URL>"` on PR 75 at 2026-11-26T07:33:43Z. Qodo's reply (2026-11-26T07:33:54Z), verbatim:

> The `/checks` command by Qodo was deprecated on the 1st of October 2026 and is no longer available. We recommend switching to the latest Qodo review capabilities.

So there is no Qodo CI summary to compare against.
