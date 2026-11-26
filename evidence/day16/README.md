# Day 16 evidence: Arnica security scan

## What was scanned

- Repository: `keynes-factory/Project.Keynes`, an organization-owned copy of `hrhgit/Project.Keynes`
  (Arnica connects to GitHub organizations, so the personal fork was copied into an org created for this).
- Branch: `master`, commit `e8dad5fb942bcac65b414f755368eb405a787cd6`, the same commit as `hrhgit/Project.Keynes` `master` at scan time.
- Arnica setup: scan only. No PR checks, bots or notifications were enabled for this run.

## Scan result (Arnica, Admin > Jobs > Tasks, 2026-11-25)

| Scan | Finished (local time) | Status | Findings |
|---|---|---|---|
| IaC | 7:39:02 PM | Completed | 0 |
| SCA | 7:40:34 PM | Completed | 0 |
| Secrets | 7:49:12 PM | Completed | 95 |
| SAST | 7:50:41 PM | Completed | 97 |

Task counts on the page: Completed 9, Failed 0, Running 0 (`arnica-scan-tasks.png`).
No finding was rated High or Critical. The SAST list sorted by risk starts with Medium findings (`arnica-sast-list.png`).

## Finding investigated

**Arnica SAST, Medium, CWE-469 (use of pointer subtraction to determine size)**,
`gdext/src/runtime_economy_pod_save.cpp` line 530 (`arnica-sast-L530.png`):

```cpp
static_cast<size_t>(end - p) % receipt_wire_size != 0) {
```

The concern behind CWE-469 is subtracting pointers that do not point into the same object, or a negative difference
turned into a huge `size_t`. Checked at `e8dad5fb9` in `restore_ecp1(const uint8_t *data, size_t size, std::string &error)`:

1. Same buffer. Lines 209-210: `const uint8_t *p = data; const uint8_t *end = data + size - 8;`. Both pointers come from `data`.
2. `end` is inside the buffer. Line 198 returns `economy_pod_ecp1_truncated` when `data == nullptr || size < 24`, so `size - 8` cannot underflow.
3. `p` never passes `end`.
   - Every read helper in `gdext/src/runtime_economy_pod_save_internal.h` (`read_u32` line 43, `read_u64` line 61, and the `read_i32`/`read_i64` wrappers) checks the signed difference `end - p < n` before it advances `p`.
   - Every bulk advance is guarded by `static_cast<size_t>(end - p) < X_payload_size`, which returns an error first (lines 367, 392, 430, 469, 506).
   - The one raw byte read, `epoch_active = *p++` (line 500), is preceded by `|| p >= end` (line 496).
4. Line 530 is itself a guard. Lines 528-533 reject the save with `economy_pod_ecp1_receipt_size_mismatch` unless the remaining bytes are an exact multiple of the 24-byte receipt size and match `receipt_count`.

So at line 530 `end - p` is a difference between two pointers into the same buffer with `p <= end`, and the cast to `size_t` cannot wrap.

**Decision: dismiss as a false positive.** No code change. The status was not changed inside Arnica.

Not established: `runtime_economy_pod_selftest.cpp` restores only valid bytes; no test feeds truncated or corrupted save bytes to
`restore_ecp1` (its caller is the save loader, `native_simulation_host_persistence.cpp:832`). The argument above rests on reading the guards, not on a fuzz or truncation test.

## Secrets: one spot check

`arnica-secrets-list.png`, `arnica-finding-L2900.png`: the finding at
`Project/project-keynes/data/economy/family_official_buffs.json` line 2900 is the line `"key": "i034_nuclear",`,
a content id field named `key`, not a credential. Lines 1280, 3173 and 4043 in the same file, also listed, are the same kind of `"key":` id line.
This is one spot check; the 95 secret findings were not reviewed one by one.

## Not covered

- 97 SAST and 95 secret findings were listed; one SAST finding was investigated in depth and one secret finding was spot-checked.
- A scan with no High or Critical findings does not show that the code is secure.
- PR-time checks were not enabled; the factory diagram shows them as planned (`factory-diagram.png`, `factory-diagram.md`).

## Files

| File | What it is |
|---|---|
| `arnica-scan-tasks.png` | Arnica task list: Secrets and SAST scans completed, Failed 0 |
| `arnica-sast-list.png` | SAST code risks sorted by risk, Medium CWE-469 rows on top |
| `arnica-sast-L530.png` | The CWE-469 finding at `runtime_economy_pod_save.cpp` line 530 |
| `arnica-secrets-list.png` | Secret findings list |
| `arnica-finding-L2900.png` | The secret finding at `family_official_buffs.json` line 2900 |
| `factory-diagram.png`, `factory-diagram.md`, `diagram.py` | The Day 14 factory diagram with the Arnica scan added |

Redaction: commit-author emails and a local machine identity shown in Arnica's detail panels are blacked out.
No secret values appear in these files; the only secret finding shown is a field name.

AI use: Claude Code ran the Arnica setup and scan in the browser, read the code and wrote these notes under the author's direction.
Project.Keynes is a pre-existing project with a collaborator (HkingAuditore); the code in the investigated file was in the repository before this scan.
