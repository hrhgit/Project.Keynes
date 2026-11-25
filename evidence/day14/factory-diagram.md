# Ticket to master, with the Day 14 approval step

![Ticket to master with the Day 14 approval step](factory-diagram.png)

The Day 10 diagram ([evidence/day10](../day10/factory-diagram.png)) with only the "Before merge" band changed on Day 14. New: the Qodo workflow, the approval guard on `tools/factory/**` and the route to me when it applies. The checks before it (18 static guards, tests, golden replay, C++ runtime, Qodo local review) and CI, the review re-read and the merge gate after it are unchanged and still required; the Qodo approved label does not replace them.

Pink boxes are configured in Qodo, not in the factory's code. The factory's merge gate does not read the label; it re-reads the review, findings and CI itself, so the label and the merge gate check the same review independently.

The image was edited by Codex's image model from the Day 10 image; I checked every label and arrow against the text version below.

## Text version

```mermaid
flowchart TD
  ME0(["🏷️ Add ready-for-agent"]):::me
  subgraph S0["Before work"]
    G0{"G0 ticket check: acceptance criteria items,<br/>no blocked / needs-investigation label"}:::gate
    CW["Codebase Wisdom checks the ticket"]:::planned
    B["Base checks on master<br/>(failures recorded as pre-existing)"]:::agent
    P{"Codex read-only plan:<br/>open questions, or checks<br/>outside the allowlist?"}:::gate
  end
  subgraph S1["Uncommitted"]
    I["🏷️ agent-working<br/>Codex implements"]:::agent
    K{"Required: static guards, tests, golden replay;<br/>C++ changed: rebuild + Debug/Release runtime.<br/>New failure vs master?"}:::gate
    LR{"Qodo local review:<br/>staged + unstaged + untracked"}:::gate
  end
  subgraph S2["Before merge"]
    PR["Commit, push, open PR"]:::agent
    RV{"Qodo PR review completed on the current head?<br/>High/Medium open?"}:::gate
    F["Codex fixes, or disputes<br/>with file:line evidence"]:::agent
    subgraph AP["Approval step (Qodo workflow, Day 14)"]
      QW{"Workflow 'Keynes quality gate':<br/>no findings at Medium or higher,<br/>all categories and finding types?"}:::qodo
      AG{"Approval guard:<br/>PR touches tools/factory/** ?"}:::qodo
      LBL["Qodo approved label<br/>(criteria met; not proof that checks passed)"]:::qodo
    end
    PERSON(["🏷️ No label: I review the factory change<br/>and merge it myself"]):::me
    CI{"Required separately: CI green on the head"}:::gate
    M{"🏷️ agent-done + factory-handoff<br/>Merge gate: review and CI re-read at head,<br/>C++ rerun, protected paths?"}:::gate
    PF["Perf check on base..head<br/>(PR 76, not merged)"]:::planned
    MAIN[("master")]:::done
  end
  HELP(["🏷️ agent-needs-help<br/>Fix the ticket or decide,<br/>then re-add ready-for-agent"]):::me

  ME0 --> G0
  G0 -- fail --> HELP
  G0 -- pass --> B
  G0 -.-> CW
  CW -.-> P
  B --> P
  P -- yes --> HELP
  P -- no --> I
  I --> K
  K -- "yes, rounds left" --> I
  K -- "still failing" --> HELP
  K -- no --> LR
  LR -- "High/Medium, up to 2 rounds" --> I
  LR -- "open after the limit" --> HELP
  LR -- "clean or incomplete" --> PR
  PR --> RV
  RV -- "High/Medium, under 3 rounds" --> F
  F -- fix --> K
  F -- "dispute: dismissed in Qodo" --> RV
  RV -- "same findings again, or 3 rounds" --> HELP
  RV -- "clean; Low listed for me" --> QW
  QW -- no --> F
  QW -- yes --> AG
  AG -- "yes: guard applies" --> PERSON
  AG -- no --> LBL
  LBL --> CI
  CI -- "pending or failed" --> F
  CI -- green --> M
  M -- "protected path" --> HELP
  M -- "performance claim" --> PF
  PF -.-> MAIN
  M -- pass --> MAIN
  PERSON --> MAIN
  HELP -. "re-label" .-> ME0

  classDef me fill:#ede9fe,stroke:#6d28d9,stroke-width:3px,color:#2e1065
  classDef gate fill:#fef3c7,stroke:#b45309,color:#451a03
  classDef agent fill:#e0f2fe,stroke:#0369a1,color:#082f49
  classDef qodo fill:#fce7f3,stroke:#be185d,stroke-width:2px,color:#500724
  classDef done fill:#dcfce7,stroke:#15803d,color:#052e16
  classDef planned fill:#f1f5f9,stroke:#64748b,color:#334155,stroke-dasharray:5 5
```
