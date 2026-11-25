# Day 14 retest: predictions

Written and committed before PR 87 is re-evaluated.

## Why a retest

On Day 14 neither PR showed the label working. The repository's merge automation was in `native_vote` mode, where the label action is skipped (`advisoryResult: skipped`), so "no label" said nothing about the guard. On 2026-11-25 the repository was switched to `output_mode: label_only`, `enabled: false`, `advisory_enabled: true`. The workspace keeps its own settings.

The workflow and the guard are unchanged:

- Workflow "Keynes quality gate: label PRs with no Medium+ findings": no findings at `>= remediation_recommended`, all categories and finding types, action: add the Qodo approved label.
- Guard "Never approve: changed paths": `hrhgit/Project.Keynes:tools/factory/**`.

## Outside the guard: PR 89 (control, already observed)

[PR 89](https://github.com/hrhgit/Project.Keynes/pull/89) changes `docs/` and `tools/ci/` only. Head `96e7e8e01` had a complete review with no open findings and green CI. After the switch it was re-evaluated and labelled. See `retest-pr89.md`.

## Inside the guard: PR 87 (prediction)

[PR 87](https://github.com/hrhgit/Project.Keynes/pull/87) changes `tools/factory/config.json`, `tools/factory/qodo.py` and `tools/factory/tests/test_factory.py`.

- Head `aab667278`: complete Qodo review (run 2155517), one open informational finding, nothing at Medium or higher. CI green.
- It meets the workflow's conditions, so only the guard can stop the label.

**Prediction:** after re-evaluation the guard matches, the decision is not `approve`, and no Qodo approved label is added. PR 87 stays for me to review and merge.
