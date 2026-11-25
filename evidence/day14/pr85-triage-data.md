# PR 85 in PR Triage: the data behind the page

Read on 2026-11-25 at about 11:40Z from the responses the PR Triage page loads for PR 85 (`git_integration/v1/pull-requests/github/<repo>/<pr>` and `.../timeline`), captured in the browser. Only these fields are copied; nothing was changed.

Timeline entries (`kind`, time, commit, `findingCount`):

| Time | Entry | Commit | Findings |
|---|---|---|---|
| 08:49:29 | opened | | |
| 08:54:28 | review_completed | `b1b52c489` | 6 |
| 10:19:38 | pushed | `2ba168376` | |
| 10:20:05 | findings_resolved ×5 | `2ba168376` | |
| 10:25:04 | review_completed | `2ba168376` | 0 |
| 10:56:36 | pushed | `45d866b22` | |
| 10:59:40 | review_completed | `45d866b22` | 0 |
| 11:04:08 | review_completed | `45d866b22` | 0 |
| 11:05:12 | pushed | `1b8b12241` | |
| 11:07:43 | review_completed | `1b8b12241` | 0 |

The timeline response has `approvalWorkflowsConfigured: true`. The PR record has the workflow's latest evaluation:

```json
"mergeAutomation": {
  "availability": "recorded",
  "freshness": "unknown",
  "eventType": "merge_policy_evaluated",
  "eventTimestamp": "2026-11-25T11:07:35Z",
  "reviewedGitSha": null,
  "decision": "unknown",
  "reasonCode": "incomplete_review",
  "trigger": "initial_review",
  "criterionCount": 0,
  "traceComplete": false,
  "criteria": [],
  "requestedAction": "withdraw_approval",
  "providerResult": "unknown"
},
"approvalEligibility": {
  "state": "unknown",
  "reasonCode": "incomplete_review",
  "evaluatedAt": "2026-11-25T11:37:34.487881Z",
  "reviewedGitSha": "1b8b122418c17a10d3a182704ac314e9c6b3aa21",
  "reviewRunId": "2153392",
  "automationEnabled": true,
  "approvalProhibited": false,
  "criterionResults": null
}
```

What this shows: on the current head the workflow did not decide (`decision: unknown`) because Qodo's review of that head was incomplete (`reasonCode: incomplete_review`). The Qodo CLI agrees: run 2153392 on `1b8b12241` has `review_effort: skip`, `review_complete: false`. The heads after `2ba168376` change only `docs/architecture/feature-status.md` and merge master. Compare PR 84 ([data](pr84-triage-data.md)): a complete review with 0 findings, evaluated and surfaced to a person (`decision: surface`, `ineligible`).
