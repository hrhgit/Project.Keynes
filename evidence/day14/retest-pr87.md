# Day 14 retest: PR 87, inside the guard

[PR 87](https://github.com/hrhgit/Project.Keynes/pull/87) changes `tools/factory/config.json`, `tools/factory/qodo.py` and `tools/factory/tests/test_factory.py`. The prediction in `retest-predictions.md` (committed before the run) was: the guard matches, no Qodo approved label.

**Result: the prediction failed, and the guard as Qodo stores it cannot hold one path while labelling the rest of the repository.** Every run is listed below, including mine that broke things.

## Guard states tried

The workspace guard is stored as `merge_automation.guards`. The web app writes "repository X, only these paths P" as a `deny_repos` entry for X plus a `deny_paths` entry `X:P`.

| State | `deny_repos` | `deny_paths` | How it got there |
|---|---|---|---|
| A | `[]` | `hrhgit/Project.Keynes:tools/factory/**` | At 12:41 UTC I removed the repository entry in the guards panel, reading it as a whole-repository guard. The panel then showed no guard, but this path entry stayed stored. |
| B | `hrhgit/project.keynes` | `hrhgit/Project.Keynes:tools/factory/**` | Re-added in the guards panel at about 23:02 (the panel's own save). |

## What Qodo did in each state

Qodo PR Triage timeline and GitHub issue events (all times UTC, 2026-11-25):

| Time | State | PR | Trigger | Qodo record | GitHub |
|---|---|---|---|---|---|
| 22:30:46 | A | 89 (outside) | reopen | approve / approved_clean; guard `unmatched` | 22:30:50 labelled by `qodo-code-review[bot]` |
| 22:55:48 | A | 87 (inside) | reopen | approve / approved_policy; guard `unmatched` | 22:55:51 labelled |
| 23:03:38 | B | 87, 89 | reopen | `label_removed`, reconciliation, `incomplete_review` (new review runs started) | 23:03:40 unlabelled on both |
| 23:07–23:16 | B | 87, 89 | reviews completed; reopen again at 23:13 | no workflow evaluation on either PR | no label |
| 23:20:45 | B | 87 | new commit `b1020baeb` (fixes Qodo finding 305f0a27; review run 2167180 complete 23:23:37; CI green) | finding marked implemented, review completed, **no workflow evaluation** | no label |
| 23:44:10 | A (set for this test) | – | – | – | – |
| 23:44:59 | A | 89 | reopen | approve / approved_clean; both workflows `matched`; guard `unmatched` | 23:45:02 labelled |
| 23:45:50 | B (restored) | – | – | – | – |

## What this shows

- In state A the path entry never matched, so PR 87 was labelled like any clean PR.
- In state B no PR in the repository was evaluated at all, the control PR 89 included. PR 87 had no label, but there was no evaluation behind it, so the missing label is not the guard holding PR 87.
- Nothing else changed between the runs: repository `output_mode: label_only`, both workflows enabled, workspace settings untouched (checked by reading the settings before and after each change).

So far I have not found a stored guard that labels PR 89 and holds PR 87. The guard is restored to state B. In that state Qodo evaluates no PR in this repository, so no new label is added anywhere (PR 89 keeps the one it got at 23:45:02 in state A). PR 87 waits for me to review and merge it.
