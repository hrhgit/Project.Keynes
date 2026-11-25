#!/usr/bin/env python3
"""Measure Project.Keynes simulation performance per commit and compare two commits.

Every measurement is stored in a long-lived archive (default ~/.keynes-perf, or
$KEYNES_PERF_HOME) keyed by commit, scenario, machine, toolchain and measurement
method. A comparison reads two archive records; a record that already exists for
the same identity is reused, so re-checking a PR after review only measures the
new head.

Subcommands:
  measure REV            make sure the archive holds a record for REV
  compare BASE HEAD      measure both if needed, check results are unchanged,
                         compare every metric, write report.json and report.md
  history                list archived records

Exit codes: 0 pass, 1 fail (results changed, a run was invalid, a build failed),
2 needs a person (a claimed metric did not improve, a headline metric regressed),
75 deferred (the machine stayed busy or the run budget expired), 64 usage error.

Only headless measurements are taken. Windowed frame time needs an unlocked
screen and is reported as not measured.

Timing summaries follow the conventions of compare_perf.py from the
project-keynes-runtime-hotloop-optimization skill (+/-15% wall-clock noise,
cumulative scan counters as the deterministic evidence).
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

METHOD_VERSION = 3
DEFAULT_SCENARIO = {"days": 50, "speed": 50, "seed": 20260718, "width": 60, "height": 40,
                    "foreign_count": 3}
TIERS = ("quick", "full")
NOISE = 0.15
DEFAULT_ROUNDS = 3
GOLDEN_RUNS = 2
EXIT_PASS, EXIT_FAIL, EXIT_HUMAN, EXIT_DEFERRED, EXIT_USAGE = 0, 1, 2, 75, 64
HEADLINE = {
    "result.run_ms": "lower",
    "auth.authoritative_days_per_second": "higher",
    "harness.adjusted_days_per_second": "higher",
    "result.generation_ms": "lower",
    "rusage.maxrss_mb": "lower",
    "rusage.cpu_s": "lower",
}
COMPETING = re.compile(r"(^|/)(godot|Godot|scons|clang\+\+|clang|cc1plus|ld|ld64)(\s|$)")
COMPETING_CPU = 20.0
RESULT_PREFIX = "[headless-perf/result]"
AUTH_PREFIX = "[headless-perf/auth]"
HARNESS_PREFIX = "[headless-perf/harness]"
PERF_SCRIPT = "res://tests/game/headless_perf_record.gd"
REQUIRED_CSV_COLUMNS = ("tick_idx", "speed_multiplier", "t_sus_ms")
DAY_RECORDER_METHODS = {False: "day_records_worker_v1", True: "day_records_main_v1"}
DAY_CSV_COLUMNS = {*REQUIRED_CSV_COLUMNS, "row_idx", "runtime_graph_simulation_committed_day",
                   "runtime_graph_simulation_generation", "commit_produced_at_us", "commit_interval_ms"}
PROJECT = "Project/project-keynes"
GODOT_CPP = "gdext/godot-cpp"
LIBRARY_DIR = "addons/dots_ext/bin"
MAX_WORKTREES = 3


class Deferred(Exception):
    """The machine stayed busy or the run budget expired."""


class StepFailed(Exception):
    """A build, import or check could not produce valid evidence."""


# ---------------------------------------------------------------- pure helpers

def parse_kv_line(lines: list[str], prefix: str) -> dict[str, str]:
    """Return the key=value pairs of the single line starting with prefix."""
    found = [line for line in lines if line.startswith(prefix)]
    if len(found) != 1:
        raise ValueError(f"expected one {prefix} line, found {len(found)}")
    pairs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=(\S*)", found[0][len(prefix):])
    if not pairs:
        raise ValueError(f"{prefix} line has no key=value pairs")
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{prefix} line repeats a key")
    return dict(pairs)


def to_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def validate_day_csv(rows: list[dict], result: dict[str, str]) -> list[str]:
    """The daily format requires a real commit stamp for every measured day."""
    warmup = to_number(result.get("warmup_days"))
    if warmup is None or warmup < 0 or not warmup.is_integer():
        return ["invalid warmup_days for day recorder"]
    if result.get("recorder_method") != DAY_RECORDER_METHODS[warmup == 0]:
        return ["recorder method does not match the warmup clock"]
    previous = None
    for index, row in enumerate(rows):
        day = int(warmup) + index + 1
        if set(row) != DAY_CSV_COLUMNS:
            return ["daily perf csv columns do not match the recorder method"]
        if row["tick_idx"] != str(day) or row["runtime_graph_simulation_committed_day"] != str(day):
            return [f"daily perf csv expected ordered day {day}"]
        if row["t_sus_ms"] != "":
            return [f"day {day}: t_sus_ms must be empty in the daily CSV"]
        stamp = to_number(row["commit_produced_at_us"])
        if stamp is None or stamp <= 0 or not stamp.is_integer() or (previous is not None and stamp < previous):
            return [f"day {day}: invalid commit_produced_at_us"]
        interval = to_number(row["commit_interval_ms"])
        if day == 1:
            if row["commit_interval_ms"] != "":
                return ["day 1: commit_interval_ms has no preceding commit"]
        elif interval is None or interval < 0 or (
                previous is not None and interval != (stamp - previous) / 1000.0):
            return [f"day {day}: invalid commit_interval_ms"]
        previous = stamp
        for column in ("row_idx", "speed_multiplier", "runtime_graph_simulation_generation"):
            if to_number(row[column]) is None:
                return [f"day {day}: {column} is missing or nonnumeric"]
    return []


def validate_perf_run(exit_code: int, result: dict[str, str] | None, csv_rows: list[dict] | None,
                      scenario: dict) -> list[str]:
    """Errors that make a headless perf run unusable as evidence (empty list = valid)."""
    errors = []
    if exit_code != 0:
        errors.append(f"godot exit={exit_code}")
    if result is None:
        return errors + ["missing result line"]
    def number(key):
        value = to_number(result.get(key))
        if value is None:
            errors.append(f"result.{key} missing or not a number")
        return value
    days = scenario["days"]
    rows, expected = number("rows"), number("expected_rows")
    if rows is not None and rows != days:
        errors.append(f"result rows={rows:g} expected {days}")
    if expected is not None and expected != days:
        errors.append(f"result expected_rows={expected:g} expected {days}")
    csv_count = len(csv_rows) if csv_rows is not None else None
    if csv_count != days:
        errors.append(f"perf csv has {csv_count} data rows, expected {days}")
    method = result.get("recorder_method")
    if method is not None and method not in DAY_RECORDER_METHODS.values():
        errors.append(f"unknown recorder method {method!r}")
    elif csv_rows and method is not None:
        errors.extend(validate_day_csv(csv_rows, result))
    elif csv_rows:
        for column in REQUIRED_CSV_COLUMNS:
            if column not in csv_rows[0]:
                errors.append(f"perf csv missing required column {column}")
            elif any(to_number(row.get(column)) is None for row in csv_rows):
                errors.append(f"perf csv required column {column} has a missing or nonnumeric value")
    if result.get("fatal") != "false":
        errors.append(f"fatal={result.get('fatal')}")
    if result.get("economy_configured") != "true":
        errors.append(f"economy_configured={result.get('economy_configured')}")
    if result.get("formal_start") != "true":
        errors.append(f"formal_start={result.get('formal_start')}")
    ledger = number("ledger_failures")
    if ledger is not None and ledger != 0:
        errors.append(f"ledger_failures={ledger:g}")
    population = number("population")
    if population is not None and population <= 0:
        errors.append(f"population={population:g}")
    countries = number("country_count")
    if countries is not None and countries < scenario["foreign_count"] + 1:
        errors.append(f"country_count={countries:g} expected >= {scenario['foreign_count'] + 1}")
    return errors


COST_MARKS = ("bytes", "memory", "_mb", "_kb")


def metric_kind(name: str) -> str:
    """counter: cumulative work; cost: memory or capacity the run holds; timing: varies run to run;
    gauge: anything else, with no better direction."""
    if name.startswith("csv."):
        column = name.split(".")[1]
        if (column.startswith(("bd_economy_scan_", "scan_steps")) or column.endswith("_epoch")
                or column in ("research_full_scan_fallbacks", "bd_country_research_full_scan_fallbacks")):
            return "counter"
    if any(mark in name for mark in ("_ms", "_us", "per_second", "wait")):
        return "timing"
    if any(mark in name.lower() for mark in COST_MARKS):
        return "cost"
    return "timing" if name.startswith("rusage.") else "gauge"


def direction(name: str) -> str:
    return "higher" if "per_second" in name else "lower"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def csv_metrics(rows: list[dict[str, str]]) -> dict[str, float]:
    """Summarize numeric perf_record samples. The run validator checks required cells."""
    if not rows:
        return {}
    out = {}
    for column in rows[0]:
        if column == "commit_produced_at_us":
            continue  # Absolute timestamps identify samples. Only their intervals are measurements.
        samples = []
        populated = 0
        for day, row in enumerate(rows):
            cell = row.get(column)
            if cell == "":
                continue
            populated += 1
            value = to_number(cell)
            if value is not None:
                samples.append((day, value))
        if not samples:
            # Text labels and optional columns with no samples are part of the recorder's schema.
            continue
        if len(samples) != populated:
            raise ValueError(f"column {column} has {len(samples)}/{populated} numeric populated values")
        name = f"csv.{column}"
        if metric_kind(name + ".per_day") == "counter":
            # A sparse counter needs two readings. Keep the existing one-day summary.
            if len(samples) > 1 or len(rows) == 1:
                first_day, first_value = samples[0]
                last_day, last_value = samples[-1]
                out[f"{name}.per_day"] = (last_value - first_value) / max(last_day - first_day, 1)
            continue
        values = [value for _, value in samples]
        out[f"{name}.mean"] = statistics.fmean(values)
        if column.endswith(("_ms", "_us")):
            out[f"{name}.p95"] = percentile(values, 0.95)
            out[f"{name}.max"] = max(values)
    return out


def waterfall_metrics(rows: list[dict[str, str]]) -> dict[str, float]:
    """Per-day worker segment costs from PK_RUNTIME_WATERFALL_CSV."""
    if not rows:
        return {}
    fixed = {"day", "attempt", "committed", "mask"}
    days = {row.get("day") for row in rows}
    committed = [row for row in rows if row.get("committed") in ("1", "true")]
    out = {"waterfall.attempts_per_day": len(rows) / max(1, len(days)),
           "waterfall.failed_attempts": float(len(rows) - len(committed))}
    for column in rows[0]:
        if column in fixed:
            continue
        values = [to_number(row.get(column)) for row in committed]
        values = [v for v in values if v is not None]
        if values:
            out[f"waterfall.{column}_ms.mean"] = statistics.fmean(values)
            if column == "total":
                out["waterfall.total_ms.p95"] = percentile(values, 0.95)
    return out


def numeric_items(prefix: str, values: dict[str, str]) -> dict[str, float]:
    out = {}
    for key, value in values.items():
        number = to_number(value)
        if number is not None:
            out[f"{prefix}.{key}"] = number
    return out


def compare_metric(name: str, base: list[float], head: list[float], noise: float = NOISE) -> dict:
    """Classify one metric. Deterministic sides compare exactly; timings need a clear gap."""
    row = {"metric": name, "kind": metric_kind(name), "better": direction(name),
           "base": base, "head": head}
    if not base or not head:
        row["status"] = "only_in_head" if head else "only_in_base"
        return row
    med_b, med_h = statistics.median(base), statistics.median(head)
    row.update(base_median=med_b, head_median=med_h,
               change=None if med_b == 0 else (med_h - med_b) / abs(med_b))
    exact = len(set(base)) == 1 and len(set(head)) == 1
    if exact and row["kind"] != "timing":
        if med_b == med_h:
            row["status"] = "unchanged"
        elif row["kind"] in ("counter", "cost"):
            row["status"] = "less_work" if med_h < med_b else "more_work"
        else:
            row["status"] = "changed"
        return row
    if len(base) < 2 or len(head) < 2:
        row["status"] = "insufficient_rounds"
        return row
    change = row["change"]
    separated = max(head) < min(base) or min(head) > max(base)
    if change is None or abs(change) <= noise or not separated:
        row["status"] = "within_noise"
        return row
    faster = (med_h < med_b) if row["better"] == "lower" else (med_h > med_b)
    row["status"] = "improved" if faster else "regressed"
    return row


def compare_rounds(base_rounds: list[dict], head_rounds: list[dict], noise: float = NOISE) -> list[dict]:
    names = sorted({k for r in base_rounds + head_rounds for k in r})
    rows = []
    for name in names:
        base = [r[name] for r in base_rounds if name in r]
        head = [r[name] for r in head_rounds if name in r]
        row = compare_metric(name, base, head, noise)
        if base and head and (len(base) != len(base_rounds) or len(head) != len(head_rounds)):
            row["status"] = "missing_rounds"
        rows.append(row)
    return rows


def first_difference(expected, actual, path="golden"):
    if type(expected) is not type(actual):
        return {"path": path, "base": expected, "head": actual}
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return {"path": path, "base_keys": sorted(expected), "head_keys": sorted(actual)}
        for key in sorted(expected):
            found = first_difference(expected[key], actual[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path, "base_length": len(expected), "head_length": len(actual)}
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found:
                return found
        return None
    return None if expected == actual else {"path": path, "base": expected, "head": actual}


def record_reusable(record: dict | None, identity: dict, tier: str, rounds: int) -> tuple[bool, str]:
    """A stored record needs an identical identity, a sufficient tier and enough rounds."""
    if record is None:
        return False, "no record"
    if record.get("status") != "complete":
        return False, f"record status {record.get('status')}"
    stored = record.get("identity", {})
    for key in sorted(set(identity) | set(stored)):
        if stored.get(key) != identity.get(key):
            return False, f"identity differs: {key}"
    if TIERS.index(record.get("tier", "quick")) < TIERS.index(tier):
        return False, f"record tier {record.get('tier')} is below {tier}"
    samples = record.get("rounds")
    if not isinstance(samples, list):
        return False, "record has no rounds list"
    if len(samples) < rounds:
        return False, f"record has {len(samples)} rounds, need {rounds}"
    return True, "record matches"


def load_gate(idle: float | None, competing: list[str], min_idle: float,
              busiest: list[str] = ()) -> list[str]:
    """Reasons the machine is too busy to measure (empty list = go). idle is the CPU idle fraction
    over the last second: unlike the 1-minute load average it does not lag after a job ends.

    `busiest` only explains a low idle figure that no known competitor accounts for; it never
    decides on its own whether the machine is busy."""
    reasons = []
    if idle is None or not 0.0 <= idle <= 1.0:
        reasons.append("cpu idle unknown")
    elif idle < min_idle:
        reasons.append(f"cpu {idle:.0%} idle, below {min_idle:.0%}")
        if not competing and busiest:
            reasons.append("busiest processes: " + ", ".join(busiest))
    reasons += [f"competing process: {name}" for name in competing]
    return reasons


TOP_IDLE = re.compile(r"CPU usage:.*?([0-9.]+)% idle")


def parse_top_idle(text: str) -> float | None:
    """Idle fraction from `top -l 2`: the first sample counts since boot, so only the last counts."""
    found = TOP_IDLE.findall(text)
    if len(found) < 2:
        return None
    return to_number(found[-1]) / 100 if to_number(found[-1]) is not None else None


def parse_proc_stat_idle(before: str, after: str) -> float | None:
    """Idle fraction between two /proc/stat readings (idle + iowait over all jiffies)."""
    def totals(text):
        for line in text.splitlines():
            parts = line.split()
            if parts and parts[0] == "cpu" and len(parts) >= 6 and all(x.isdigit() for x in parts[1:]):
                values = [int(x) for x in parts[1:]]
                return sum(values), values[3] + values[4]
        return None
    a, b = totals(before), totals(after)
    if a is None or b is None or b[0] <= a[0]:
        return None
    return (b[1] - a[1]) / (b[0] - a[0])


def cpu_idle() -> float | None:
    if platform.system() == "Darwin":
        done = subprocess.run(["top", "-l", "2", "-n", "0", "-s", "1"], text=True, capture_output=True)
        return parse_top_idle(done.stdout)
    try:
        before = Path("/proc/stat").read_text()
        time.sleep(1)
        return parse_proc_stat_idle(before, Path("/proc/stat").read_text())
    except OSError:
        return None


def judge(correctness: list[str], invalid_runs: list[str], rows: list[dict],
          claims: list[str], unmeasured: str | None = None) -> tuple[str, list[str]]:
    """Overall status from facts: fail, needs_human or pass.

    `unmeasured` says why the claimed gain cannot be measured headlessly. The results check and
    the headline metrics are still judged, but such a run never passes: the claim needs a person.
    """
    reasons = list(correctness) + list(invalid_runs)
    if reasons:
        return "fail", reasons
    incomplete = ("only_in_base", "only_in_head", "missing_rounds", "insufficient_rounds")
    missing = [f"incomplete measurement for {row['metric']} ({row['status']})" for row in rows
               if row["status"] in incomplete]
    if missing:
        return "fail", missing
    if unmeasured is not None:
        human = [f"claim not measured headlessly: {unmeasured}"]
    else:
        human = [] if claims else ["no improvement claim supplied"]
    regressions = ("regressed", "more_work")
    for pattern in claims:
        matched = [row for row in rows if re.search(pattern, row["metric"])]
        if not matched:
            human.append(f"claim {pattern!r} matches no metric")
            continue
        if not any(row["status"] in ("improved", "less_work") for row in matched):
            states = sorted({row["status"] for row in matched})
            human.append(f"claim {pattern!r} not shown to improve ({', '.join(states)})")
        for row in matched:
            if row["status"] in regressions:
                human.append(f"claim {pattern!r} includes {row['metric']} ({row['status']})")
    for row in rows:
        if row["metric"] in HEADLINE and row["status"] in regressions:
            change = row.get("change")
            extent = f" {change:+.1%}" if change is not None else ""
            human.append(f"headline {row['metric']} {row['status']}{extent}")
    return ("needs_human", human) if human else ("pass", [])


# ---------------------------------------------------------------- environment

def run(args: list[str], cwd: Path | None = None, env: dict | None = None,
        log: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    if log is None:
        done = subprocess.run(args, cwd=cwd, env=full_env, text=True, capture_output=True, check=False)
    else:
        with log.open("w") as handle:
            done = subprocess.run(args, cwd=cwd, env=full_env, text=True, stdout=handle,
                                  stderr=subprocess.STDOUT, check=False)
    if check and done.returncode != 0:
        detail = log.read_text(errors="replace")[-2000:] if log else (done.stderr or done.stdout)[-2000:]
        raise StepFailed(f"{' '.join(map(str, args))} exited {done.returncode}\n{detail}")
    return done


def first_line(args: list[str]) -> str:
    try:
        done = subprocess.run(args, text=True, capture_output=True, check=False)
    except OSError:
        return "unavailable"
    return ((done.stdout or done.stderr).strip().splitlines() or ["unavailable"])[0]


def machine_identity() -> dict:
    if platform.system() == "Darwin":
        values = [first_line(["sysctl", "-n", key]) for key in
                  ("hw.model", "machdep.cpu.brand_string", "hw.ncpu", "hw.memsize")]
        label = f"{values[0]} {values[1]} {values[2]} cpus {int(values[3]) // 2**30} GiB"
    else:
        cpu = next((line.split(":", 1)[1].strip() for line in
                    Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),
                   platform.processor()) if Path("/proc/cpuinfo").exists() else platform.processor()
        label = f"{platform.system()} {cpu} {os.cpu_count()} cpus"
    return {"machine": hashlib.sha256(label.encode()).hexdigest()[:16], "machine_label": label}


def toolchain_identity(godot: str) -> dict:
    compiler = first_line(["c++", "--version"])
    godot_version = first_line([godot, "--version"])
    label = f"godot {godot_version}; {compiler}; {platform.system()} {platform.release()}"
    return {"toolchain": hashlib.sha256(label.encode()).hexdigest()[:16], "toolchain_label": label}


def competing_processes(ps_output: str, mine: int, min_cpu: float = COMPETING_CPU) -> list[str]:
    """Busy Godot, build or link processes that are not ours (an idle editor does not count)."""
    found = []
    for pid, cpu, command in busy_processes(ps_output, mine, min_cpu):
        executable = command.split()[0]
        if COMPETING.search(executable + " "):
            found.append(f"{pid} {executable.rsplit('/', 1)[-1]} {cpu:.0f}% cpu")
    return found


# Lower than COMPETING_CPU on purpose: a low idle figure can come from several processes that
# each use only a little CPU, and they are what the hint has to name.
BUSIEST_MIN_CPU = 1.0
APP_BUNDLE = re.compile(r"/([^/]+)\.app/Contents/MacOS/[^/]+$")


def process_name(executable: str) -> str:
    """A readable name for an executable path, as `ps -o comm=` prints it (no arguments, spaces
    kept). A macOS app's own executable is named by its bundle; anything else by its basename."""
    bundle = APP_BUNDLE.search(executable)
    return bundle.group(1) if bundle else executable.rsplit("/", 1)[-1]


def parse_executables(ps_output: str) -> dict[int, str]:
    """pid -> executable path from `ps -axo pid=,comm=`. comm holds no arguments, so a path with
    spaces stays whole and an argument can never be taken for the program."""
    found = {}
    for line in ps_output.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            found[int(parts[0])] = parts[1]
    return found


def busiest_processes(ps_output: str, mine: int, executables: dict[int, str] | None = None,
                      limit: int = 3, min_cpu: float = BUSIEST_MIN_CPU) -> list[str]:
    """The busiest processes that are not ours, of any kind, busiest first. They name what is
    using the CPU when the idle figure is low but no known competitor is running. A process
    missing from `executables` is named by the first word of its command line."""
    executables = executables or {}
    found = sorted(busy_processes(ps_output, mine, min_cpu), key=lambda p: (-p[1], p[0]))
    return [f"{pid} {process_name(executables.get(pid) or command.split()[0])} {cpu:.0f}% cpu"
            for pid, cpu, command in found[:limit]]


def busy_processes(ps_output: str, mine: int, min_cpu: float) -> list[tuple[int, float, str]]:
    """(pid, %cpu, command) for `ps -axo pid=,ppid=,%cpu=,command=` rows at or above min_cpu,
    leaving out this process and its children. Malformed rows are skipped."""
    rows = []
    for line in ps_output.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        pid, ppid, cpu, command = int(parts[0]), int(parts[1]), to_number(parts[2]), parts[3]
        if pid == mine or ppid == mine or cpu is None or cpu < min_cpu:
            continue
        rows.append((pid, cpu, command))
    return rows


def process_table() -> str:
    return subprocess.run(["ps", "-axo", "pid=,ppid=,%cpu=,command="], text=True,
                          capture_output=True, check=False).stdout


def executable_table() -> str:
    return subprocess.run(["ps", "-axo", "pid=,comm="], text=True,
                          capture_output=True, check=False).stdout


# Rough cost of each step on a quiet machine, used only to decide how long waiting may last.
ESTIMATE_S = {"build": 240, "golden": 60, "load_consistency": 120, "round": 15}


def work_estimate(missing_ready: list[bool], tier: str, rounds: int) -> float:
    """Seconds of work for the commits still to measure; True means its worktree is already built."""
    per_commit = ESTIMATE_S["golden"] + rounds * ESTIMATE_S["round"]
    if tier == "full":
        per_commit += ESTIMATE_S["load_consistency"]
    return sum(per_commit + (0 if ready else ESTIMATE_S["build"]) for ready in missing_ready)


def wait_allowance(budget_s: float, elapsed_s: float, estimate_s: float) -> float:
    """Seconds the whole run may still spend waiting for a quiet machine: never negative."""
    return max(0.0, budget_s - elapsed_s - estimate_s)


def check_budget(args) -> None:
    if args.budget > 0 and time.monotonic() - args.started >= args.budget * 60:
        raise Deferred(f"the {args.budget:g}-minute run budget expired")


def wait_for_quiet_machine(args, log: list) -> dict:
    """Block until the machine is quiet. Waiting shares one allowance for the whole run
    (the time budget minus the estimated work); when it runs out the run is deferred."""
    deadline = time.monotonic() + args.wait_left
    if args.budget > 0:
        deadline = min(deadline, args.started + args.budget * 60)
    while True:
        check_budget(args)
        load1 = os.getloadavg()[0]
        idle = cpu_idle()
        cpus = os.cpu_count() or 0
        table, mine = process_table(), os.getpid()
        competing = competing_processes(table, mine)
        busiest = [] if competing else busiest_processes(table, mine, parse_executables(executable_table()))
        reasons = load_gate(idle, competing, args.min_idle, busiest)
        sample = {"at": now(), "cpu_idle": None if idle is None else round(idle, 3),
                  "load1": round(load1, 2), "cpus": cpus, "busy": reasons}
        check_budget(args)
        if not reasons:
            args.wait_left = max(0.0, deadline - time.monotonic())
            return sample
        log.append(sample)
        if time.monotonic() + args.poll_seconds > deadline:
            raise Deferred(f"machine still busy and the {args.budget:g}-minute budget leaves no time "
                           f"to wait: " + "; ".join(reasons))
        print(f"machine busy, waiting: {'; '.join(reasons)}", flush=True)
        time.sleep(args.poll_seconds)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- archive

class Archive:
    def __init__(self, home: Path):
        self.home = home
        self.records = home / "records"
        self.worktrees = home / "worktrees"
        self.comparisons = home / "comparisons"
        self.build = home / "build"
        for path in (self.records, self.worktrees, self.comparisons):
            path.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def build_lock(self):
        """One build at a time per archive: two checks would otherwise check out over each other."""
        import fcntl

        with (self.home / "build.lock").open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def scenario_id(self, scenario: dict) -> str:
        return "_".join(f"{key}{scenario[key]}" for key in sorted(scenario))

    def find(self, identity: dict, tier: str, rounds: int) -> tuple[dict | None, str]:
        folder = self.records / identity["commit"][:12] / self.scenario_id(identity["scenario"])
        why = "no record"
        if not folder.exists():
            return None, why
        for path in sorted(folder.glob("*/record.json"), reverse=True):
            record = json.loads(path.read_text())
            ok, why = record_reusable(record, identity, tier, rounds)
            if ok:
                record["path"] = str(path.parent)
                return record, why
        return None, why

    def new_record_dir(self, identity: dict) -> Path:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = (self.records / identity["commit"][:12] / self.scenario_id(identity["scenario"])
                / f"{stamp}-{identity['machine']}")
        path.mkdir(parents=True)
        return path

    def index(self, record: dict) -> None:
        line = {key: record.get(key) for key in ("created", "tier", "status", "path")}
        line.update(commit=record["identity"]["commit"], subject=record.get("subject"),
                    scenario=record["identity"]["scenario"],
                    machine=record["identity"]["machine_label"],
                    headline=record.get("headline", {}))
        with (self.home / "index.jsonl").open("a") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- worktrees and builds

def git(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args]).stdout.strip()


PLATFORMS = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}
ARCHES = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "AMD64": "x86_64"}


def host_target(system: str, machine: str) -> tuple[str, str]:
    if system not in PLATFORMS or machine not in ARCHES:
        raise StepFailed(f"no build recipe for {system}/{machine}")
    return PLATFORMS[system], ARCHES[machine]


def scons_command(system: str, machine: str, jobs: int) -> list[str]:
    """The headless editor loads the debug mapping of dots_ext.gdextension, so only that target is built."""
    target_platform, arch = host_target(system, machine)
    return ["scons", f"platform={target_platform}", "target=template_debug",
            f"arch={arch}", "dev_build=no", f"-j{max(1, jobs)}"]


def debug_libraries(tree: Path, system: str, machine: str) -> list[Path]:
    """This host's debug libraries only: other platforms' libraries are checked in and prove nothing."""
    target_platform, arch = host_target(system, machine)
    folder = tree / PROJECT / LIBRARY_DIR / target_platform
    return sorted(folder.glob(f"*.{target_platform}.template_debug.{arch}*"))


def compile_commit(repo: Path, archive: Archive, commit: str, args, record_dir: Path) -> list[Path]:
    """Build one commit in the archive's long-lived build tree and return its debug libraries.

    The build tree is reused across commits, so SCons only recompiles what differs from the last
    build; only the first build on a machine compiles godot-cpp and every source from scratch.
    """
    tree = archive.build
    if not (tree / ".git").exists():
        shutil.rmtree(tree, ignore_errors=True)
        git(repo, "worktree", "add", "--detach", str(tree), commit)
    run(["git", "-C", str(tree), "checkout", "--detach", "--force", commit],
        log=record_dir / f"checkout-{commit[:12]}.log")
    submodule = ["git", "-C", str(tree), "submodule", "update", "--init", "--force", GODOT_CPP]
    reference = repo / GODOT_CPP
    if (reference / ".git").exists():
        submodule[5:5] = ["--reference", str(reference)]
    run(submodule, log=record_dir / f"submodule-{commit[:12]}.log")
    host = (platform.system(), platform.machine())
    for stale in debug_libraries(tree, *host):
        shutil.rmtree(stale) if stale.is_dir() else stale.unlink()
    env = {}
    if args.scons:
        env["PATH"] = os.pathsep.join([str(Path(args.scons).expanduser().parent), os.environ["PATH"]])
    check_budget(args)
    run(scons_command(platform.system(), platform.machine(), os.cpu_count() or 8),
        cwd=tree / "gdext", env=env, log=record_dir / f"build-{commit[:12]}.log")
    built = debug_libraries(tree, *host)
    if not built:
        raise StepFailed(f"build of {commit[:12]} produced no template_debug library")
    return built


def prepare_worktree(repo: Path, archive: Archive, commit: str, args, record_dir: Path,
                     busy_log: list) -> Path:
    path = archive.worktrees / commit[:12]
    ready = path / ".perf-built"
    if ready.exists() and ready.read_text().strip() == commit:
        path.touch()
        return path
    if path.exists():
        run(["git", "-C", str(repo), "worktree", "remove", "--force", str(path)], check=False)
        shutil.rmtree(path, ignore_errors=True)
    prune_worktrees(repo, archive)
    started = time.monotonic()
    with archive.build_lock():
        wait_for_quiet_machine(args, busy_log)
        built = compile_commit(repo, archive, commit, args, record_dir)
        check_budget(args)
        compiled = time.monotonic() - started
        git(repo, "worktree", "add", "--detach", str(path), commit)
        for library in built:
            target = path / library.relative_to(archive.build)
            target.parent.mkdir(parents=True, exist_ok=True)
            if library.is_dir():
                shutil.copytree(library, target, dirs_exist_ok=True)
            else:
                shutil.copy2(library, target)
    seeded = seed_import_cache(archive, path)
    wait_for_quiet_machine(args, busy_log)
    import_started = time.monotonic()
    run([args.godot, "--headless", "--path", str(path / PROJECT), "--import"],
        log=record_dir / f"import-{commit[:12]}.log")
    print(f"imported {commit[:12]} in {time.monotonic() - import_started:.0f}s"
          + (f" (cache from {seeded.name})" if seeded else " (no cache)"), flush=True)
    ready.write_text(commit + "\n")
    print(f"built {commit[:12]}: compile {compiled:.0f}s, total {time.monotonic() - started:.0f}s",
          flush=True)
    return path


def seed_import_cache(archive: Archive, target: Path) -> Path | None:
    """Clone the newest imported asset cache into a fresh worktree so --import only redoes changed
    assets. Godot checks each source against its recorded hash, so a stale cache costs time, not
    correctness. Only .godot/imported is copied; the script class and uid caches are rebuilt."""
    sources = sorted((p for p in archive.worktrees.iterdir()
                      if p != target and (p / ".perf-built").exists()
                      and (p / PROJECT / ".godot/imported").is_dir()),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if (archive.build / PROJECT / ".godot/imported").is_dir():
        sources.append(archive.build)
    if not sources:
        return None
    source, destination = sources[0] / PROJECT / ".godot/imported", target / PROJECT / ".godot/imported"
    destination.parent.mkdir(parents=True, exist_ok=True)
    clone = ["cp", "-cR", str(source), str(destination)] if platform.system() == "Darwin" else None
    if clone is None or subprocess.run(clone, capture_output=True).returncode != 0:
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(source, destination)
    return sources[0]


def prune_worktrees(repo: Path, archive: Archive) -> None:
    existing = sorted((p for p in archive.worktrees.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    for path in existing[:max(0, len(existing) - (MAX_WORKTREES - 1))]:
        run(["git", "-C", str(repo), "worktree", "remove", "--force", str(path)], check=False)
        shutil.rmtree(path, ignore_errors=True)


def build_hash(worktree: Path) -> str:
    binaries = sorted(path for library in debug_libraries(worktree, platform.system(), platform.machine())
                      for path in ([library] if library.is_file() else library.rglob("*")))
    digest = hashlib.sha256()
    for path in binaries:
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


# ---------------------------------------------------------------- measurements

def perf_round(worktree: Path, out: Path, scenario: dict, tier: str, godot: str, label: str) -> dict:
    out.mkdir(parents=True)
    command = [godot, "--headless", "--path", str(worktree / PROJECT), "--script", PERF_SCRIPT, "--",
               *(f"{key}={value}" for key, value in scenario.items()),
               f"label={label}", f"output_dir={out}"]
    env = dict(os.environ)
    if tier == "full":
        env["PK_RUNTIME_WATERFALL_CSV"] = str(out / "waterfall.csv")
    log = out / "godot.log"
    started = time.monotonic()
    with log.open("w") as handle:
        process = subprocess.Popen(command, cwd=worktree, env=env, stdout=handle,
                                   stderr=subprocess.STDOUT)
        _, status, usage = os.wait4(process.pid, 0)
    wall = time.monotonic() - started
    exit_code = os.waitstatus_to_exitcode(status)
    lines = log.read_text(errors="replace").splitlines()
    metrics, result = {}, None
    errors = []
    try:
        result = parse_kv_line(lines, RESULT_PREFIX)
        metrics.update(numeric_items("result", result))
    except ValueError as error:
        errors.append(str(error))
    for prefix, name in ((AUTH_PREFIX, "auth"), (HARNESS_PREFIX, "harness")):
        try:
            metrics.update(numeric_items(name, parse_kv_line(lines, prefix)))
        except ValueError as error:
            errors.append(str(error))
    csv_path = Path(result.get("path", "")) if result else None
    rows = None
    if csv_path and csv_path.is_file():
        try:
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle, strict=True)
                columns = reader.fieldnames
                if not columns or "" in columns or len(set(columns)) != len(columns):
                    raise ValueError("missing or duplicate column names")
                rows = list(reader)
            if any(None in row or None in row.values() for row in rows):
                raise ValueError("row does not match header width")
            metrics.update(csv_metrics(rows))
        except (csv.Error, OSError, ValueError) as error:
            errors.append(f"perf csv: {error}")
    waterfall = out / "waterfall.csv"
    if waterfall.is_file():
        with waterfall.open(newline="", encoding="utf-8", errors="replace") as handle:
            metrics.update(waterfall_metrics(list(csv.DictReader(handle))))
    scale = 1 if platform.system() == "Darwin" else 1024
    metrics.update({"rusage.wall_s": wall, "rusage.cpu_s": usage.ru_utime + usage.ru_stime,
                    "rusage.user_s": usage.ru_utime, "rusage.sys_s": usage.ru_stime,
                    "rusage.maxrss_mb": usage.ru_maxrss * scale / 2**20})
    errors += validate_perf_run(exit_code, result, rows, scenario)
    method = (result or {}).get("recorder_method")
    if result is not None and method is None:
        # Old scripts had no version marker. Only identical unversioned
        # scripts can be assumed to give the old metric names the same meaning.
        script = worktree / PROJECT / PERF_SCRIPT.removeprefix("res://")
        try:
            method = "unversioned:" + hashlib.sha256(script.read_bytes()).hexdigest()[:12]
        except OSError as error:
            errors.append(f"could not identify unversioned recorder: {error}")
    return {"label": label, "command": command, "exit": exit_code, "errors": errors,
            "recorder_method": method, "metrics": metrics, "dir": str(out)}


def golden_check(worktree: Path, out: Path, godot: str, runs: int) -> dict:
    candidate = out / "golden-candidate.json"
    logs = out / "golden-logs"
    done = run([sys.executable, "tools/ci/check_golden_determinism.py", "--godot", godot,
                "--runs", str(runs), "--log-dir", str(logs), "--write-candidate", str(candidate)],
               cwd=worktree, log=out / "golden.log", check=False)
    summary = logs / "summary.json"
    passed = done.returncode == 0 and summary.is_file() and json.loads(summary.read_text()).get("passed") is True
    return {"passed": passed and candidate.is_file(), "exit": done.returncode, "runs": runs,
            "candidate": str(candidate) if candidate.is_file() else None, "log": str(out / "golden.log")}


def load_consistency_check(worktree: Path, out: Path, godot: str) -> dict:
    logs = out / "load-logs"
    done = run([sys.executable, "tools/ci/check_runtime_load_consistency.py", "--godot", godot,
                "--workers", "7", "--log-dir", str(logs)], cwd=worktree, log=out / "load.log", check=False)
    return {"passed": done.returncode == 0, "exit": done.returncode, "log": str(out / "load.log")}


def headline(rounds: list[dict]) -> dict:
    out = {}
    for name in HEADLINE:
        values = [r["metrics"][name] for r in rounds if name in r["metrics"]]
        if values:
            out[name] = statistics.median(values)
    return out


# ---------------------------------------------------------------- commands

def resolve(repo: Path, rev: str) -> tuple[str, str]:
    commit = git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}")
    return commit, git(repo, "log", "-1", "--format=%s", commit)


def identity_for(commit: str, scenario: dict, machine: dict, toolchain: dict) -> dict:
    return {"commit": commit, "scenario": scenario, "method_version": METHOD_VERSION,
            **machine, **toolchain}


def ensure_records(repo: Path, archive: Archive, revs: list[str], args, busy_log: list) -> list[dict]:
    """Return one complete record per rev, measuring alternately only the missing ones."""
    check_budget(args)
    machine, toolchain = machine_identity(), toolchain_identity(args.godot)
    plans = []
    for rev in revs:
        commit, subject = resolve(repo, rev)
        identity = identity_for(commit, args.scenario, machine, toolchain)
        record, why = archive.find(identity, args.tier, args.rounds)
        if record is not None:
            print(f"reusing archived record for {commit[:12]}: {record['path']}", flush=True)
            record["reused"] = True
        plans.append({"commit": commit, "subject": subject, "identity": identity,
                      "record": record, "why": why})
    missing = [plan for plan in plans if plan["record"] is None]
    ready = [(archive.worktrees / p["commit"][:12] / ".perf-built").exists() for p in missing]
    estimate = work_estimate(ready, args.tier, args.rounds)
    args.wait_left = (float("inf") if args.budget <= 0 else
                      wait_allowance(args.budget * 60, time.monotonic() - args.started, estimate))
    if missing:
        print(f"estimated work {estimate:.0f}s; may wait up to "
              f"{'unlimited' if args.budget <= 0 else f'{args.wait_left:.0f}s'} for a quiet machine", flush=True)
    for position, plan in enumerate(missing):
        check_budget(args)
        print(f"measuring {plan['commit'][:12]} ({plan['why']})", flush=True)
        record_dir = archive.new_record_dir(plan["identity"])
        plan["dir"] = record_dir
        plan["worktree"] = prepare_worktree(repo, archive, plan["commit"], args, record_dir, busy_log)
        check_budget(args)
        if args.budget > 0:
            # The build is done: give waiting what is left after the remaining work.
            remaining = (work_estimate([True] + ready[position + 1:], args.tier, args.rounds)
                         + position * args.rounds * ESTIMATE_S["round"])  # earlier commits' rounds
            args.wait_left = wait_allowance(args.budget * 60, time.monotonic() - args.started, remaining)
        record = {"identity": plan["identity"], "subject": plan["subject"], "tier": args.tier,
                  "created": now(), "status": "measuring", "build": build_hash(plan["worktree"]),
                  "rounds": [], "load_samples": [], "path": str(record_dir)}
        plan["record"] = record
        save(record_dir / "record.json", record)
        wait_for_quiet_machine(args, busy_log)
        record["golden"] = golden_check(plan["worktree"], record_dir, args.godot, GOLDEN_RUNS)
        if args.tier == "full":
            wait_for_quiet_machine(args, busy_log)
            record["load_consistency"] = load_consistency_check(plan["worktree"], record_dir, args.godot)
    for index in range(1, args.rounds + 1):
        for plan in missing:
            sample = wait_for_quiet_machine(args, busy_log)
            plan["record"]["load_samples"].append(sample)
            out = plan["dir"] / f"round-{index}"
            label = f"{plan['commit'][:12]}-r{index}"
            print(f"round {index}/{args.rounds} {plan['commit'][:12]}", flush=True)
            plan["record"]["rounds"].append(
                perf_round(plan["worktree"], out, args.scenario, args.tier, args.godot, label))
    check_budget(args)
    for plan in missing:
        record = plan["record"]
        record["headline"] = headline(record["rounds"])
        valid = (record["golden"]["passed"] and all(not r["errors"] for r in record["rounds"])
                 and record.get("load_consistency", {"passed": True})["passed"])
        record["status"] = "complete" if valid else "invalid"
        record["finished"] = now()
        save(plan["dir"] / "record.json", record)
        archive.index(record)
    return [plan["record"] for plan in plans]


def correctness_facts(base: dict, head: dict) -> list[str]:
    facts = []
    for name, record in (("base", base), ("head", head)):
        golden = record.get("golden", {})
        if not golden.get("passed"):
            facts.append(f"{name} {record['identity']['commit'][:12]}: same-input repeat check failed "
                         f"({golden.get('log')})")
        load = record.get("load_consistency")
        if load is not None and not load.get("passed"):
            facts.append(f"{name}: results changed under CPU load ({load.get('log')})")
    if not facts:
        expected = json.loads(Path(base["golden"]["candidate"]).read_text())
        actual = json.loads(Path(head["golden"]["candidate"]).read_text())
        diff = first_difference(expected, actual)
        if diff:
            facts.append(f"daily results differ between base and head at {diff['path']}: {json.dumps(diff)[:400]}")
    return facts


def render_markdown(report: dict) -> str:
    base, head = report["base"], report["head"]
    lines = [f"# Performance change check: {base['commit'][:12]} → {head['commit'][:12]}", "",
             f"- Status: **{report['status']}**" + (f" — {'; '.join(report['reasons'])}" if report["reasons"] else ""),
             f"- Base: `{base['commit'][:12]}` {base['subject']} ({'archived ' + base['created'] if base['reused'] else 'measured now'})",
             f"- Head: `{head['commit'][:12]}` {head['subject']} ({'archived ' + head['created'] if head['reused'] else 'measured now'})",
             f"- Scenario: {json.dumps(report['scenario'])}; tier {report['tier']}; "
             f"base {base['rounds']} rounds, head {head['rounds']} rounds",
             f"- Machine: {report['machine']}; toolchain: {report['toolchain']}",
             f"- Noise threshold for timings: ±{report['noise']:.0%} and no overlap between the two sides' ranges",
             "", "## Results unchanged", ""]
    lines += [f"- {fact}" for fact in report["correctness"]] or [
        "- Same-input repeat check passed on both sides, and the daily per-domain hashes of base and head are identical."]
    if report["tier"] == "full":
        lines.append("- CPU-load consistency check: " + ", ".join(
            f"{side} {'passed' if report[side].get('load_consistency', {}).get('passed') else 'FAILED'}"
            for side in ("base", "head")))
    rows = report["metrics"]
    def fmt(value):
        return "—" if value is None else f"{value:,.4g}"
    def table(selected, title):
        if not selected:
            return
        lines.extend(["", f"## {title}", "", "| metric | base median | head median | change | base range | head range | status |",
                      "|---|---:|---:|---:|---|---|---|"])
        for row in selected:
            change = "—" if row.get("change") is None else f"{row['change']:+.1%}"
            ranges = [f"{fmt(min(v))}–{fmt(max(v))}" if v else "—" for v in (row["base"], row["head"])]
            lines.append(f"| `{row['metric']}` | {fmt(row.get('base_median'))} | {fmt(row.get('head_median'))} | "
                         f"{change} | {ranges[0]} | {ranges[1]} | {row['status']} |")
    by_name = {row["metric"]: row for row in rows}
    table([by_name[name] for name in HEADLINE if name in by_name], "Headline")
    claimed = [row for row in rows if any(re.search(p, row["metric"]) for p in report["claims"])]
    table(claimed, "Claimed metrics")
    moved = sorted((row for row in rows if row["status"] in ("improved", "regressed")),
                   key=lambda row: -abs(row.get("change") or 0))
    table(moved[:40], f"Beyond noise ({len(moved)})")
    work = sorted((row for row in rows if row["status"] in ("less_work", "more_work", "changed")),
                  key=lambda row: -abs(row.get("change") or 0))
    table(work[:40], f"Deterministic counters and gauges that changed ({len(work)})")
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines += ["", "## Coverage", "",
              f"- {len(rows)} metrics compared: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())),
              *(f"- Excluded from the statistics: {item}" for item in report.get("excluded_rounds", [])),
              *([f"- Claim not measured headlessly: {report['unmeasured']}"] if report.get("unmeasured") else []),
              "- Not measured: windowed frame time and GPU work (needs an unlocked screen).",
              f"- Raw data: base `{base['path']}`, head `{head['path']}`"]
    if report["busy_samples"]:
        lines.append(f"- Waited for a busy machine {len(report['busy_samples'])} time(s) before measuring.")
    if "elapsed_s" in report:
        budget = report.get("budget_min") or 0
        lines.append(f"- Run time: {report['elapsed_s']}s" + (f" of a {budget:g}-minute budget" if budget else ""))
    return "\n".join(lines) + "\n"


def assess(base: dict, head: dict, claims: list[str], noise: float,
           unmeasured: str | None = None) -> dict:
    """Correctness is always checked; invalid rounds fail the check and never enter the statistics."""
    invalid = [f"{side} round {i}: {'; '.join(r['errors'])}"
               for side, record in (("base", base), ("head", head))
               for i, r in enumerate(record["rounds"], 1) if r["errors"]]
    # A full record may satisfy a quick request. Waterfall timings belong to the full tier.
    same_tier = base.get("tier", "quick") == head.get("tier", "quick")

    def valid_metrics(record):
        samples = [r["metrics"] for r in record["rounds"] if not r["errors"]]
        if same_tier:
            return samples
        return [{key: value for key, value in sample.items() if not key.startswith("waterfall.")}
                for sample in samples]

    correctness = correctness_facts(base, head)
    methods = [{run.get("recorder_method") for run in record["rounds"] if not run["errors"]}
               for record in (base, head)]
    method_errors = [f"{side} has missing or inconsistent recorder methods"
                     for side, method in zip(("base", "head"), methods)
                     if len(method) > 1 or None in method]
    invalid.extend(method_errors)
    if method_errors:
        rows = []
        status, reasons = judge(correctness, invalid, rows, claims, unmeasured)
    elif all(methods) and methods[0] != methods[1]:
        base_method, head_method = (next(iter(method)) for method in methods)
        reasons = correctness + invalid
        status = "fail" if reasons else "needs_human"
        reasons.append(f"incompatible recorder methods: {base_method} vs {head_method}")
        rows = []
    else:
        rows = compare_rounds(valid_metrics(base), valid_metrics(head), noise)
        status, reasons = judge(correctness, invalid, rows, claims, unmeasured)
    return {"status": status, "reasons": reasons, "correctness": correctness, "rows": rows,
            "excluded_rounds": invalid}


def command_compare(args, repo: Path, archive: Archive) -> int:
    busy = []
    base, head = ensure_records(repo, archive, [args.base, args.head], args, busy)
    verdict = assess(base, head, args.claim, args.noise, args.unmeasured)
    status, reasons, correctness, rows = (verdict[key] for key in ("status", "reasons", "correctness", "rows"))
    def side(record):
        return {"commit": record["identity"]["commit"], "subject": record.get("subject"),
                "created": record.get("created"), "reused": bool(record.get("reused")),
                "rounds": len(record["rounds"]),
                "path": record.get("path"), "load_consistency": record.get("load_consistency")}
    report = {"status": status, "reasons": reasons, "base": side(base), "head": side(head),
              "scenario": args.scenario, "tier": args.tier, "requested_rounds": args.rounds, "noise": args.noise,
              "claims": args.claim, "unmeasured": args.unmeasured, "machine": head["identity"]["machine_label"],
              "toolchain": head["identity"]["toolchain_label"], "correctness": correctness,
              "busy_samples": busy, "metrics": rows, "excluded_rounds": verdict["excluded_rounds"],
              "elapsed_s": round(time.monotonic() - args.started), "budget_min": args.budget,
              "created": now(), "method_version": METHOD_VERSION}
    out = Path(args.out) if args.out else archive.comparisons / (
        f"{base['identity']['commit'][:12]}..{head['identity']['commit'][:12]}-"
        f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}")
    markdown = render_markdown(report)
    check_budget(args)
    out.mkdir(parents=True, exist_ok=True)
    save(out / "report.json", report)
    (out / "report.md").write_text(markdown, encoding="utf-8")
    print(f"PERF_CHECK_RESULT={json.dumps({'status': status, 'reasons': reasons, 'report': str(out / 'report.md')}, ensure_ascii=False)}")
    return {"pass": EXIT_PASS, "needs_human": EXIT_HUMAN}.get(status, EXIT_FAIL)


def command_measure(args, repo: Path, archive: Archive) -> int:
    record, = ensure_records(repo, archive, [args.rev], args, [])
    check_budget(args)
    print(f"PERF_RECORD={json.dumps({'status': record['status'], 'path': record['path']})}")
    return EXIT_PASS if record["status"] == "complete" else EXIT_FAIL


def command_history(args, archive: Archive) -> int:
    index = archive.home / "index.jsonl"
    if not index.exists():
        print("archive is empty")
        return EXIT_PASS
    for line in index.read_text().splitlines():
        entry = json.loads(line)
        if args.commit and not entry["commit"].startswith(args.commit):
            continue
        head = entry.get("headline", {})
        print(f"{entry['created']} {entry['commit'][:12]} {entry['status']:<8} {entry['tier']:<5} "
              f"run_ms={head.get('result.run_ms', float('nan')):.0f} "
              f"days/s={head.get('auth.authoritative_days_per_second', float('nan')):.2f} "
              f"rss_mb={head.get('rusage.maxrss_mb', float('nan')):.0f}  {entry.get('subject') or ''}")
    return EXIT_PASS


def parse_args(argv: list[str]):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="Project.Keynes checkout (default: current directory)")
    parser.add_argument("--home", default=os.environ.get("KEYNES_PERF_HOME", "~/.keynes-perf"))
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"))
    parser.add_argument("--scons", default=shutil.which("scons"))
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("measure", "compare"):
        p = sub.add_parser(name)
        if name == "measure":
            p.add_argument("rev")
        else:
            p.add_argument("base")
            p.add_argument("head")
            p.add_argument("--claim", action="append", default=[],
                           help="regex of a metric the change claims to improve (repeatable)")
            p.add_argument("--unmeasured", metavar="REASON",
                           help="part of the claimed gain has no headless metric (say why); the daily "
                                "results, headline metrics and any --claim are still judged, and the "
                                "run never passes")
            p.add_argument("--noise", type=float, default=NOISE)
            p.add_argument("--out", help="report directory (default: inside the archive)")
        p.add_argument("--tier", choices=TIERS, default="quick")
        p.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
        for key, value in DEFAULT_SCENARIO.items():
            p.add_argument(f"--{key.replace('_', '-')}", type=int, default=value)
        p.add_argument("--min-idle", type=float, default=0.5,
                       help="lowest CPU idle fraction over one second allowed before each step")
        p.add_argument("--budget", type=float, default=10,
                       help="minutes for the whole run; waiting for a quiet machine gets what the "
                            "estimated work leaves, then the run is deferred (0 = no limit)")
        p.add_argument("--poll-seconds", type=float, default=15)
    h = sub.add_parser("history")
    h.add_argument("--commit")
    args = parser.parse_args(argv)
    if args.command == "compare":
        if args.unmeasured is not None and not args.unmeasured.strip():
            parser.error("--unmeasured needs a reason")
        if not args.claim and args.unmeasured is None:
            parser.error("compare needs --claim, --unmeasured or both")
        for pattern in args.claim:
            if not pattern.strip():
                parser.error("--claim must be a nonempty regex")
            try:
                re.compile(pattern)
            except re.error as error:
                parser.error(f"invalid --claim regex {pattern!r}: {error}")
    if args.command in ("measure", "compare"):
        if not 0.0 < args.min_idle <= 1.0:
            parser.error("--min-idle must be in (0, 1]")
        if to_number(args.budget) is None or args.budget < 0:
            parser.error("--budget must be 0 (no limit) or positive")
        if args.rounds < 2:
            parser.error("--rounds must be at least 2 so timings have a range")
        args.scenario = {key: getattr(args, key) for key in DEFAULT_SCENARIO}
        if any(value <= 0 for key, value in args.scenario.items() if key != "foreign_count"):
            parser.error("scenario values must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exit_:
        return EXIT_USAGE if exit_.code else EXIT_PASS
    args.started = time.monotonic()
    archive = Archive(Path(args.home).expanduser())
    if args.command == "history":
        return command_history(args, archive)
    try:
        if platform.system() not in ("Darwin", "Linux"):
            raise StepFailed("measure and compare require macOS or Linux for process timing and load sampling")
        repo = Path(git(Path(args.repo), "rev-parse", "--show-toplevel"))
        if args.command == "measure":
            return command_measure(args, repo, archive)
        return command_compare(args, repo, archive)
    except Deferred as error:
        print(f"PERF_CHECK_RESULT={json.dumps({'status': 'deferred', 'reasons': [str(error)]})}")
        return EXIT_DEFERRED
    except StepFailed as error:
        print(f"PERF_CHECK_RESULT={json.dumps({'status': 'fail', 'reasons': [str(error)[:1500]]})}")
        return EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
