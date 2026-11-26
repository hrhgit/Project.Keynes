# Performance change check: c81ebf871878 → 62ba798d6a85

- Status: **fail** — base round 3: godot exit=6; result rows=51 expected 50; perf csv has 51 data rows, expected 50; incompatible recorder methods: unversioned:fdcd453dd9e3 vs day_records_worker_v1
- Base: `c81ebf871878` Merge pull request #76 from hrhgit/factory/perf-merge-gate (measured now)
- Head: `62ba798d6a85` Merge pull request #85 from hrhgit/agent/issue-82 (measured now)
- Scenario: {"days": 50, "speed": 50, "seed": 20260718, "width": 60, "height": 40, "foreign_count": 3}; tier quick; base 3 rounds, head 3 rounds
- Machine: Mac14,2 Apple M2 8 cpus 24 GiB; toolchain: godot 4.6.3.stable.official.7d41c59c4; Apple clang version 21.0.0 (clang-2100.3.34.2); Darwin 27.2.0
- Noise threshold for timings: ±15% and no overlap between the two sides' ranges

## Results unchanged

- Same-input repeat check passed on both sides, and the daily per-domain hashes of base and head are identical.

## Coverage

- 0 metrics compared: 
- Excluded from the statistics: base round 3: godot exit=6; result rows=51 expected 50; perf csv has 51 data rows, expected 50
- Claim not measured headlessly: PR 85 claims no speedup; this run only checks what a comparison across the recorder change reports
- Not measured: windowed frame time and GPU work (needs an unlocked screen).
- Raw data: base `~/.keynes-perf/records/c81ebf871878/days50_foreign_count3_height40_seed20260718_speed50_width60/20261125-221857-fd50095c6e657082`, head `~/.keynes-perf/records/62ba798d6a85/days50_foreign_count3_height40_seed20260718_speed50_width60/20261125-222005-fd50095c6e657082`
- Waited for a busy machine 1 time(s) before measuring.
- Run time: 259s
