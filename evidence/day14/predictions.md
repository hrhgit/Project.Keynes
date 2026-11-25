# Day 14 predictions (written before either PR is opened or reviewed)

Workflow (to be configured): scope `hrhgit/Project.Keynes`; If: no findings at Medium or higher, all categories and finding types; Then: add the Qodo approved label.
Approval guard (to be added): `hrhgit/Project.Keynes`, path `tools/factory/**`.

| PR | Change | Touches the guarded path | Predicted outcome |
|---|---|---|---|
| Outside | Issue 82: the headless perf recorder sometimes exports 49 of 50 rows (exit 6). Written by the factory (Codex) from the issue | No (recorder under `Project/`) | If Qodo's complete review of the head leaves no open High or Medium finding: Qodo approved label. If it finds a valid High/Medium: no label until it is fixed and the new head is reviewed clean |
| Inside | `tools/factory/verdict.py`: `judge()` sends a closed finding with an unknown level to a person, as the merge path already does (Day 9 open item). Written by Claude Code | Yes | No Qodo approved label even with a clean review; the guard sends it to a person, who reviews and merges |

Both PRs carry `no-auto-merge`, so the factory does not merge them; a person decides.
