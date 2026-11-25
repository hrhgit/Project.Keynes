# Day 14 retest: PR 89, outside the guard

[PR 89](https://github.com/hrhgit/Project.Keynes/pull/89) changes `docs/visual-optimization/*.md`, `tools/ci/check_doc_links.py`, its baseline and tests, and `.github/workflows/runtime-checks.yml`. Nothing under `tools/factory/**`.

Head `96e7e8e01bfdb1a053864c065dd4f788b0672663`: Qodo review run 2165894, `review_complete: true`, no open findings. CI `architecture-guards` and `authoring-and-thread-lifetime` passed.

## Before the switch (repository in `native_vote` mode)

Qodo PR Triage timeline, `workflow_evaluated` entries for this head:

| Time (UTC) | Trigger | Guard | Keynes quality gate | Decision | Label action |
|---|---|---|---|---|---|
| 21:28:04 | initial_review | unmatched | matched | surface | `advisoryAction: none`, `advisoryResult: skipped` |
| 21:55:36 | other_reevaluation | unmatched | matched | surface | `advisoryAction: none`, `advisoryResult: skipped` |

No label was added. The workflow matched; only the label action was skipped.

## The cause

The web app's own validation accepts two modes: `native_vote` needs `enabled: true` and `advisory_enabled` not true; `label_only` needs `enabled` not true and `advisory_enabled: true`. The repository was in `native_vote`, so the label action never ran.

Repository settings changed (repository scope only):

| Key | Before | After |
|---|---|---|
| `merge_automation.output_mode` | `native_vote` (inherited) | `label_only` |
| `merge_automation.enabled` | `true` | `false` |
| `merge_automation.advisory_enabled` | `false` (inherited) | `true` |

## After the switch

Draft/ready toggles at 22:12, 22:18 and 22:28 produced no new evaluation. Closing and reopening the PR (22:30:06, 22:30:25) did.

Qodo PR Triage timeline:

```
22:30:46Z  kind: labeled   eventType: merge_policy_reevaluated   sha: 96e7e8e01
trigger: other_reevaluation   decision: approve   reasonCode: approved_clean
criterionCount: 2, both matched   outputMode: label_only
advisoryAction: apply   advisoryResult: confirmed
```

GitHub issue events:

```
2026-11-25T22:30:50Z  labeled  qodo-code-review[bot] (Bot)  Qodo approved
```

The label covers head `96e7e8e01` only; Qodo removes it on a new push. It means the PR met the workflow's conditions, not that every check passed: CI, tests and the factory's merge gate remain separate requirements.
