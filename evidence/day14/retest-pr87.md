# Day 14 retest: PR 87, inside the guard

[PR 87](https://github.com/hrhgit/Project.Keynes/pull/87) changes `tools/factory/config.json`, `tools/factory/qodo.py` and `tools/factory/tests/test_factory.py`. The prediction in `retest-predictions.md` (committed before the run) was: the guard matches, no Qodo approved label.

**Result.** With the guard as the web app stores it, the prediction failed: one form never matched the path, the other stopped all evaluation in the repository. A third form, a bare path pattern written to the settings API, did what the prediction said (state C below). Every run is listed, including mine that broke things.

## Guard states tried

The workspace guard is stored as `merge_automation.guards`. The web app writes "repository X, only these paths P" as a `deny_repos` entry for X plus a `deny_paths` entry `X:P`.

| State | `deny_repos` | `deny_paths` | How it got there |
|---|---|---|---|
| A | `[]` | `hrhgit/Project.Keynes:tools/factory/**` | At 12:41 UTC I removed the repository entry in the guards panel, reading it as a whole-repository guard. The panel then showed no guard, but this path entry stayed stored. |
| B | `hrhgit/project.keynes` | `hrhgit/Project.Keynes:tools/factory/**` | Re-added in the guards panel at about 23:02 (the panel's own save). |
| C | `[]` | `tools/factory/**` | Written to `PATCH /config/v1/settings` at 00:11:00 on 2026-11-26. |

## What Qodo did in each state

Qodo PR Triage timeline and GitHub issue events (UTC; rows from 22:30 to 23:45:50 are on 2026-11-25, rows from 00:11 on are on 2026-11-26):

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
| 00:11:00 | C | – | – | – | – |
| 00:11:44 | C | 87 (inside) | reopen | `held_back`: surface / surfaced; both workflows `matched`; guard **`matched`**; label action skipped | no label |
| 00:12:48 | C | 89 (outside) | reopen | approve / approved_clean; both workflows `matched`; guard `unmatched` | 00:12:51 labelled (after the routine reconciliation removal at 00:12:43) |

## What this shows

- In state A the path entry never matched, so PR 87 was labelled like any clean PR.
- In state B no PR in the repository was evaluated at all, the control PR 89 included. PR 87 had no label, but there was no evaluation behind it, so the missing label is not the guard holding PR 87.
- Nothing else changed between the runs: repository `output_mode: label_only`, both workflows enabled, workspace settings untouched (checked by reading the settings before and after each change).
- In state C the same clean-review conditions gave opposite outcomes by path: PR 87 (`tools/factory/**`) was held back with the guard matched, PR 89 (`docs/`, `tools/ci/`) was labelled with the guard unmatched.

State C is the guard now in force. Two limits: a bare pattern applies to every repository in the workspace, and the guards panel shows no entry for it (checked after a page reload at 00:13), so saving from that panel could overwrite it; the stored setting is the thing to check. PR 87 waits for me to review and merge it.
