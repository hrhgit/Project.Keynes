# Ticket to master, with the Day 16 security scan

![Ticket to master with the Day 16 Arnica scan](factory-diagram.png)

The Day 10 diagram as updated on Day 14 ([evidence/day14](../day14/factory-diagram.md)), with one band added below `master` on Day 16. Nothing above `master` changed.

- **What ran:** one Arnica scan of `keynes-factory/Project.Keynes`, an organization-owned copy of `hrhgit/Project.Keynes` made because Arnica's GitHub app installs on organizations. Its `master` is the same commit as ours, `e8dad5f`. The integration is in the initial scan-only setup.
- **Where findings are read:** the Arnica dashboard, by me. No Arnica result feeds the factory's gates.
- **Planned, not running:** Arnica PR checks and notifications (no policy enabled).

The band was drawn with `diagram.py` (Pillow) onto the Day 14 image, so every label is typed text.

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
  subgraph S3["Security scan (Day 16)"]
    AR["Arnica scan, ran once:<br/>org copy keynes-factory/Project.Keynes,<br/>master @ e8dad5f, scan-only setup<br/>(secrets, SAST, SCA, IaC)"]:::arnica
    AF(["I read findings in the Arnica dashboard:<br/>fix, investigate or dismiss"]):::me
    APR["Arnica PR check + notifications<br/>(planned, per PR)"]:::planned
  end
  MAIN -- "copy of master" --> AR
  AR --> AF

  classDef me fill:#ede9fe,stroke:#6d28d9,stroke-width:3px,color:#2e1065
  classDef gate fill:#fef3c7,stroke:#b45309,color:#451a03
  classDef agent fill:#e0f2fe,stroke:#0369a1,color:#082f49
  classDef qodo fill:#fce7f3,stroke:#be185d,stroke-width:2px,color:#500724
  classDef done fill:#dcfce7,stroke:#15803d,color:#052e16
  classDef arnica fill:#ccfbf1,stroke:#0f766e,stroke-width:2px,color:#042f2e
  classDef planned fill:#f1f5f9,stroke:#64748b,color:#334155,stroke-dasharray:5 5
```
