# Performance change check: 9ddb12734262 → ec9a22ce2ec3

- Status: **fail** — head round 3: godot exit=6; result rows=49 expected 50; perf csv has 49 data rows, expected 50
- Base: `9ddb12734262` Merge pull request #71 from hrhgit/agent/issue-65 (measured now)
- Head: `ec9a22ce2ec3` Issue #66: address Qodo findings 27869f53-480d-4cea-a233-0b07420b4ac6, 3195290e-3206-4d64-8fd3-ec332de7e805, 4dc07bbd-e8dd-4644-8f5e-ca149dd14bb7 (measured now)
- Scenario: {"days": 50, "speed": 50, "seed": 20260718, "width": 60, "height": 40, "foreign_count": 3}; tier quick; base 3 rounds, head 3 rounds
- Machine: Mac14,2 Apple M2 8 cpus 24 GiB; toolchain: godot 4.6.3.stable.official.7d41c59c4; Apple clang version 21.0.0 (clang-2100.3.34.2); Darwin 27.2.0
- Noise threshold for timings: ±15% and no overlap between the two sides' ranges

## Results unchanged

- Same-input repeat check passed on both sides, and the daily per-domain hashes of base and head are identical.

## Headline

| metric | base median | head median | change | base range | head range | status |
|---|---:|---:|---:|---|---|---|
| `result.run_ms` | 1,318 | 1,347 | +2.2% | 1,215–1,412 | 1,343–1,351 | within_noise |
| `auth.authoritative_days_per_second` | 96.79 | 96.93 | +0.1% | 96.07–97.32 | 96.4–97.45 | within_noise |
| `harness.adjusted_days_per_second` | 96.79 | 96.93 | +0.1% | 96.07–97.32 | 96.4–97.45 | within_noise |
| `result.generation_ms` | 2.046e+04 | 2.038e+04 | -0.4% | 1.854e+04–2.051e+04 | 2.006e+04–2.069e+04 | within_noise |
| `rusage.maxrss_mb` | 998.3 | 997.8 | -0.1% | 994.2–999.2 | 997.2–998.4 | within_noise |
| `rusage.cpu_s` | 13.75 | 13.96 | +1.5% | 13.37–13.82 | 13.85–14.08 | within_noise |

## Beyond noise (5)

| metric | base median | head median | change | base range | head range | status |
|---|---:|---:|---:|---|---|---|
| `csv.runtime_graph_day_work_units.mean` | 1.153e+05 | 1.463e+05 | +26.9% | 5.661e+04–1.157e+05 | 1.165e+05–1.761e+05 | regressed |
| `csv.runtime_graph_climate_pod_replay_ms.p95` | 0.005875 | 0.004375 | -25.5% | 0.004792–0.005958 | 0.004208–0.004542 | improved |
| `csv.sched_proc_resource_ms.max` | 0.125 | 0.103 | -17.6% | 0.114–0.137 | 0.102–0.104 | improved |
| `csv.engine_process_ms.max` | 30.2 | 35.24 | +16.7% | 30.05–33.27 | 34.53–35.96 | regressed |
| `csv.engine_process_ms.p95` | 30.2 | 35.24 | +16.7% | 30.05–33.27 | 34.53–35.96 | regressed |

## Coverage

- 409 metrics compared: 2 improved, 3 regressed, 140 unchanged, 264 within_noise
- Excluded from the statistics: head round 3: godot exit=6; result rows=49 expected 50; perf csv has 49 data rows, expected 50
- Claim not measured headlessly: Issue #66 counts full elevation and wind overlay builds and texture uploads while each overlay is open. The headless recorder leaves the overlays closed, so csv.tail_overlay_refresh_count.mean does not measure the claim.
- Not measured: windowed frame time and GPU work (needs an unlocked screen).
- Raw data: base `/Users/herh/.keynes-perf/records/9ddb12734262/days50_foreign_count3_height40_seed20260718_speed50_width60/20261124-212101-fd50095c6e657082`, head `/Users/herh/.keynes-perf/records/ec9a22ce2ec3/days50_foreign_count3_height40_seed20260718_speed50_width60/20261124-212149-fd50095c6e657082`
- Run time: 262s of a 10-minute budget
