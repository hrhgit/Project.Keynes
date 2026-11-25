# PR 84 in PR Triage: the data behind the page

Read on 2026-11-25 at about 07:10Z from the responses the PR Triage page loads for PR 84 (`git_integration/v1/pull-requests/github/<repo>/<pr>` and `.../timeline`), captured in the browser. Only these fields are copied; nothing was changed.

The visible timeline has two entries: `opened` at 06:54:06Z and `review_completed` at 06:55:09Z on `cc56ceeb5ec7102308071ff11bc1bf8c9c70264f` with `findingCount: 0`. Neither carries a `workflows` or `mergeAutomation` value, so the page shows no workflow or guard event. The timeline response has `approvalWorkflowsConfigured: true`.

The PR record itself has the workflow's evaluation:

```json
"mergeAutomation": {
  "availability": "recorded",
  "freshness": "current",
  "eventType": "merge_policy_evaluated",
  "eventTimestamp": "2026-11-25T06:55:00Z",
  "reviewedGitSha": "cc56ceeb5ec7102308071ff11bc1bf8c9c70264f",
  "decision": "surface",
  "reasonCode": "surfaced",
  "trigger": "initial_review",
  "criterionCount": 0,
  "traceComplete": true,
  "criteria": [],
  "requestedAction": "withdraw_approval",
  "providerResult": "unknown"
},
"approvalEligibility": {
  "state": "ineligible",
  "reasonCode": "surfaced",
  "evaluatedAt": "2026-11-25T07:02:51.327075Z",
  "reviewedGitSha": "cc56ceeb5ec7102308071ff11bc1bf8c9c70264f",
  "reviewRunId": "2149029",
  "automationEnabled": true,
  "approvalProhibited": false,
  "criterionResults": null
}
```

What this shows: the workflow evaluated the reviewed head and decided not to label or approve it (`ineligible`, `decision: surface`, i.e. surfaced to a person), although the review had 0 findings. What it does not show: the record names no guard and lists no criteria (`criteria: []`), and `approvalProhibited` is `false`, so it does not say in words that the `tools/factory/**` guard was the reason. The outside-path PR is the comparison: same workflow, no guarded path.
