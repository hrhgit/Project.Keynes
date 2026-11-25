"""perf_change_check decides whether a performance change may proceed (AGENTS.md rule 6).

Each gate, parser and classifier is fed inputs it must refuse, not only good ones.
Run: python -m unittest tools/perf/tests/test_perf_change_check.py -v
"""
import argparse
import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import perf_change_check as pc  # noqa: E402

SCENARIO = dict(pc.DEFAULT_SCENARIO)
GOOD_RESULT = {"rows": "50", "expected_rows": "50", "fatal": "false", "economy_configured": "true",
               "formal_start": "true", "ledger_failures": "0", "population": "1200",
               "country_count": "4", "path": "/tmp/perf.csv"}
GOOD_CSV = [{"tick_idx": str(i), "speed_multiplier": "50", "t_sus_ms": "1"} for i in range(1, 51)]
IDENTITY = {"commit": "a" * 40, "scenario": SCENARIO, "method_version": pc.METHOD_VERSION,
            "machine": "m1", "machine_label": "Mac", "toolchain": "t1", "toolchain_label": "godot"}


def record(**changes):
    value = {"status": "complete", "tier": "quick", "identity": dict(IDENTITY),
             "rounds": [{"errors": [], "metrics": {}} for _ in range(3)]}
    value.update(changes)
    return value


class ResultLineParsing(unittest.TestCase):
    def test_reads_single_line(self):
        lines = ["noise", "[headless-perf/result] days=50 fatal=false path=/x/perf.csv"]
        self.assertEqual(pc.parse_kv_line(lines, pc.RESULT_PREFIX)["path"], "/x/perf.csv")

    def test_refuses_missing_duplicate_empty_and_repeated_keys(self):
        for lines in ([], ["[headless-perf/result] days=1", "[headless-perf/result] days=1"],
                      ["[headless-perf/result] nothing here"],
                      ["[headless-perf/result] days=1 days=2"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                pc.parse_kv_line(lines, pc.RESULT_PREFIX)


class PerfRunValidation(unittest.TestCase):
    def test_accepts_a_complete_run(self):
        self.assertEqual(pc.validate_perf_run(0, GOOD_RESULT, GOOD_CSV, SCENARIO), [])

    def test_refuses_each_broken_fact(self):
        cases = {
            "exit": (1, GOOD_RESULT, GOOD_CSV),
            "no result": (0, None, GOOD_CSV),
            "short csv": (0, GOOD_RESULT, GOOD_CSV[:-1]),
            "missing csv": (0, GOOD_RESULT, None),
            "rows": (0, GOOD_RESULT | {"rows": "49"}, GOOD_CSV),
            "expected rows": (0, GOOD_RESULT | {"expected_rows": "10"}, GOOD_CSV),
            "fatal": (0, GOOD_RESULT | {"fatal": "true"}, GOOD_CSV),
            "fatal missing": (0, {k: v for k, v in GOOD_RESULT.items() if k != "fatal"}, GOOD_CSV),
            "ledger": (0, GOOD_RESULT | {"ledger_failures": "2"}, GOOD_CSV),
            "ledger not a number": (0, GOOD_RESULT | {"ledger_failures": "nan"}, GOOD_CSV),
            "economy": (0, GOOD_RESULT | {"economy_configured": "false"}, GOOD_CSV),
            "synthetic start": (0, GOOD_RESULT | {"formal_start": "false"}, GOOD_CSV),
            "no population": (0, GOOD_RESULT | {"population": "0"}, GOOD_CSV),
            "too few countries": (0, GOOD_RESULT | {"country_count": "2"}, GOOD_CSV),
        }
        for name, (code, result, rows) in cases.items():
            with self.subTest(name):
                self.assertTrue(pc.validate_perf_run(code, result, rows, SCENARIO))

    def test_refuses_required_columns_missing_with_the_correct_row_count(self):
        for column in ("tick_idx", "speed_multiplier", "t_sus_ms"):
            rows = [{key: value for key, value in row.items() if key != column} for row in GOOD_CSV]
            with self.subTest(column=column):
                self.assertTrue(any(column in error for error in
                                    pc.validate_perf_run(0, GOOD_RESULT, rows, SCENARIO)))

    def test_refuses_required_column_with_no_numeric_values(self):
        rows = [row | {"speed_multiplier": ""} for row in GOOD_CSV]
        self.assertTrue(any("speed_multiplier" in error for error in
                            pc.validate_perf_run(0, GOOD_RESULT, rows, SCENARIO)))

    def run_csv_round(self, tmp, headers, values):
        worktree = Path(tmp)
        path = worktree / "perf.csv"
        path.write_text("\n".join([headers, *values]) + "\n")
        days = len(values)
        result = GOOD_RESULT | {"rows": str(days), "expected_rows": str(days), "path": str(path)}
        usage = argparse.Namespace(ru_utime=0.1, ru_stime=0.1, ru_maxrss=1000)

        def godot(*_, stdout, **__):
            stdout.write(pc.RESULT_PREFIX + " " + " ".join(f"{k}={v}" for k, v in result.items()) + "\n")
            stdout.write(pc.AUTH_PREFIX + " authoritative_days_per_second=50\n")
            stdout.write(pc.HARNESS_PREFIX + " adjusted_days_per_second=50\n")
            return argparse.Namespace(pid=42)

        with mock.patch.object(pc.subprocess, "Popen", side_effect=godot), \
             mock.patch.object(pc.os, "wait4", return_value=(42, 0, usage), create=True):
            return pc.perf_round(worktree, worktree / "round", SCENARIO | {"days": days},
                                 "quick", "godot", "r1")

    def test_perf_round_uses_observed_samples_for_optional_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.run_csv_round(tmp, "tick_idx,speed_multiplier,t_sus_ms,market_ms",
                                     ["1,50,0,", "2,50,0,7", "3,50,0,", "4,50,0,3"])
        self.assertEqual(run["errors"], [])
        self.assertEqual(run["metrics"]["csv.market_ms.mean"], 5)
        self.assertEqual(run["metrics"]["csv.market_ms.p95"], 7)
        self.assertEqual(run["metrics"]["csv.market_ms.max"], 7)

    def test_perf_round_rejects_missing_required_column_and_corrupt_optional_cells(self):
        for headers, values, reason in (
            ("tick_idx,t_sus_ms", ["1,0", "2,0"], "speed_multiplier"),
            ("tick_idx,speed_multiplier,t_sus_ms", ["1,50,0", "2,,0"], "speed_multiplier"),
            ("tick_idx,speed_multiplier,t_sus_ms,market_ms", ["1,50,0,7", "2,50,0,invalid"], "market_ms"),
            ("tick_idx,speed_multiplier,t_sus_ms,market_ms", ["1,50,0,7", "2,50,0"], "header width"),
            ("tick_idx,speed_multiplier,t_sus_ms,t_sus_ms", ["1,50,0,0", "2,50,0,0"], "duplicate"),
        ):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                run = self.run_csv_round(tmp, headers, values)
                self.assertTrue(any(reason in error for error in run["errors"]), run["errors"])


class MetricClassification(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(pc.metric_kind("csv.bd_economy_scan_cells.per_day"), "counter")
        self.assertEqual(pc.metric_kind("csv.t_sus_ms.p95"), "timing")
        self.assertEqual(pc.metric_kind("rusage.maxrss_mb"), "cost")
        self.assertEqual(pc.metric_kind("rusage.cpu_s"), "timing")
        self.assertEqual(pc.metric_kind("result.population"), "gauge")
        self.assertEqual(pc.direction("auth.authoritative_days_per_second"), "higher")

    def test_improvement_needs_a_clear_gap(self):
        row = pc.compare_metric("csv.t_sus_ms.mean", [10, 10.5, 11], [7, 7.2, 7.4])
        self.assertEqual(row["status"], "improved")

    def test_refuses_improvement_inside_noise(self):
        row = pc.compare_metric("csv.t_sus_ms.mean", [10, 10.2, 10.4], [9.0, 9.1, 9.2])
        self.assertEqual(row["status"], "within_noise")

    def test_refuses_improvement_when_ranges_overlap(self):
        row = pc.compare_metric("csv.t_sus_ms.mean", [6, 10, 14], [5, 7, 13])
        self.assertEqual(row["status"], "within_noise")

    def test_refuses_timing_verdict_from_one_round(self):
        row = pc.compare_metric("csv.t_sus_ms.mean", [10], [5])
        self.assertEqual(row["status"], "insufficient_rounds")

    def test_higher_is_better_for_throughput(self):
        row = pc.compare_metric("auth.authoritative_days_per_second", [30, 31, 32], [20, 21, 22])
        self.assertEqual(row["status"], "regressed")

    def test_counters_compare_exactly(self):
        self.assertEqual(pc.compare_metric("csv.scan_steps_x.per_day", [5, 5], [3, 3])["status"], "less_work")
        self.assertEqual(pc.compare_metric("csv.scan_steps_x.per_day", [5, 5], [5, 5])["status"], "unchanged")

    def test_refuses_exact_verdict_for_a_counter_that_varies(self):
        row = pc.compare_metric("csv.scan_steps_x.per_day", [5, 6, 7], [3, 3, 3])
        self.assertNotIn(row["status"], ("less_work", "unchanged"))

    def test_memory_that_repeats_exactly_counts_as_less_or_more_work(self):
        self.assertEqual(pc.metric_kind("csv.economy_memory_bytes.mean"), "cost")
        self.assertEqual(pc.compare_metric("csv.economy_memory_bytes.mean", [900, 900], [600, 600])["status"],
                         "less_work")
        self.assertEqual(pc.compare_metric("csv.economy_memory_bytes.mean", [600, 600], [900, 900])["status"],
                         "more_work")

    def test_refuses_exact_verdict_for_memory_that_varies(self):
        row = pc.compare_metric("csv.economy_memory_bytes.mean", [900, 905, 910], [890, 895, 899])
        self.assertEqual(row["status"], "within_noise")

    def test_gauges_without_a_direction_are_only_changed(self):
        self.assertEqual(pc.compare_metric("result.population", [100, 100], [90, 90])["status"], "changed")

    def test_metric_missing_on_one_side(self):
        self.assertEqual(pc.compare_metric("waterfall.total_ms.p95", [], [1, 2])["status"], "only_in_head")


class CsvSummaries(unittest.TestCase):
    def test_counters_become_per_day_increase_and_timings_get_tail(self):
        rows = [{"bd_economy_scan_a": "0", "t_sus_ms": "1", "label": "x", "unused_ms": ""},
                {"bd_economy_scan_a": "10", "t_sus_ms": "3", "label": "", "unused_ms": ""},
                {"bd_economy_scan_a": "20", "t_sus_ms": "2", "label": "x", "unused_ms": ""}]
        metrics = pc.csv_metrics(rows)
        self.assertEqual(metrics["csv.bd_economy_scan_a.per_day"], 10)
        self.assertEqual(metrics["csv.t_sus_ms.max"], 3)
        self.assertNotIn("csv.label.mean", metrics)
        self.assertNotIn("csv.unused_ms.mean", metrics)

    def test_sparse_counters_use_elapsed_days_between_samples(self):
        rows = [{"scan_steps_a": "", "scan_steps_b": ""},
                {"scan_steps_a": "0", "scan_steps_b": ""},
                {"scan_steps_a": "", "scan_steps_b": "3"},
                {"scan_steps_a": "6", "scan_steps_b": ""},
                {"scan_steps_a": "", "scan_steps_b": ""}]
        self.assertEqual(pc.csv_metrics(rows), {"csv.scan_steps_a.per_day": 3})

    def test_refuses_nonnumeric_populated_cells_in_a_numeric_column(self):
        for bad in ("invalid", "nan"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "market_ms"):
                pc.csv_metrics([{"market_ms": "1"}, {"market_ms": ""}, {"market_ms": bad}])

    def test_fewer_research_fallback_scans_satisfy_a_claim(self):
        for name in ("research_full_scan_fallbacks", "bd_country_research_full_scan_fallbacks"):
            with self.subTest(name=name):
                base = pc.csv_metrics([{name: "7"}, {name: "9"}, {name: "11"}])
                head = pc.csv_metrics([{name: "7"}, {name: "8"}, {name: "9"}])
                row, = pc.compare_rounds([base, base], [head, head])
                self.assertEqual(row["metric"], f"csv.{name}.per_day")
                self.assertEqual(row["status"], "less_work")
                self.assertEqual(pc.judge([], [], [row], [name]), ("pass", []))


class ArchiveReuse(unittest.TestCase):
    def test_reuses_identical_identity(self):
        self.assertTrue(pc.record_reusable(record(), dict(IDENTITY), "quick", 3)[0])
        self.assertTrue(pc.record_reusable(record(tier="full"), dict(IDENTITY), "quick", 2)[0])

    def test_refuses_any_identity_difference(self):
        for key, value in (("commit", "b" * 40), ("scenario", SCENARIO | {"days": 60}),
                           ("machine", "m2"), ("toolchain", "t2"),
                           ("method_version", pc.METHOD_VERSION + 1)):
            with self.subTest(key):
                self.assertFalse(pc.record_reusable(record(), IDENTITY | {key: value}, "quick", 3)[0])

    def test_refuses_incomplete_invalid_missing_or_lower_tier(self):
        self.assertFalse(pc.record_reusable(None, IDENTITY, "quick", 3)[0])
        self.assertFalse(pc.record_reusable(record(status="invalid"), IDENTITY, "quick", 3)[0])
        self.assertFalse(pc.record_reusable(record(status="measuring"), IDENTITY, "quick", 3)[0])
        self.assertFalse(pc.record_reusable(record(), IDENTITY, "full", 3)[0])
        stored = record()
        stored["identity"] = IDENTITY | {"extra": 1}
        self.assertFalse(pc.record_reusable(stored, IDENTITY, "quick", 3)[0])

    def test_archive_refuses_fewer_rounds_than_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = pc.Archive(Path(tmp))
            entry = archive.new_record_dir(IDENTITY) / "record.json"
            pc.save(entry, record())
            found, reason = archive.find(IDENTITY, "quick", 4)
            self.assertIsNone(found)
            self.assertIn("3 rounds", reason)
            self.assertEqual(len(archive.find(IDENTITY, "quick", 2)[0]["rounds"]), 3)


class MachineLoadGate(unittest.TestCase):
    def test_quiet_machine_goes(self):
        self.assertEqual(pc.load_gate(0.7, [], 0.5), [])

    def test_refuses_busy_cpu_unknown_or_impossible_idle_and_competitors(self):
        for idle in (0.3, None, -0.1, 1.5):
            with self.subTest(idle=idle):
                self.assertTrue(pc.load_gate(idle, [], 0.5))
        self.assertTrue(pc.load_gate(0.9, ["123 godot 90% cpu"], 0.5))

    def test_top_idle_uses_the_last_sample_not_the_since_boot_one(self):
        text = ("CPU usage: 5.0% user, 2.0% sys, 93.0% idle\n"
                "CPU usage: 67.43% user, 9.2% sys, 23.54% idle\n")
        self.assertAlmostEqual(pc.parse_top_idle(text), 0.2354)

    def test_refuses_top_output_without_two_samples(self):
        for text in ("", "CPU usage: 5.0% user, 2.0% sys, 93.0% idle\n", "garbage"):
            with self.subTest(text=text):
                self.assertIsNone(pc.parse_top_idle(text))

    def test_proc_stat_idle_between_two_readings(self):
        before = "cpu  100 0 100 700 100 0 0 0\ncpu0 1 2 3 4 5\n"
        after = "cpu  150 0 150 850 150 0 0 0\n"
        self.assertAlmostEqual(pc.parse_proc_stat_idle(before, after), 200 / 300)

    def test_refuses_unreadable_or_non_advancing_proc_stat(self):
        same = "cpu  100 0 100 700 100 0 0 0\n"
        for before, after in (("", same), (same, same), ("cpu x y z w v", same)):
            with self.subTest(before=before):
                self.assertIsNone(pc.parse_proc_stat_idle(before, after))

    def test_busy_godot_and_compilers_count_but_idle_editor_and_children_do_not(self):
        table = "\n".join([
            "  10     1  95.0 /opt/homebrew/bin/godot --headless --path x",
            "  11     1   0.3 /Applications/Godot.app/Contents/MacOS/Godot",
            "  12     1  80.0 /usr/bin/clang++ -c a.cpp",
            "  13   500  99.0 /opt/homebrew/bin/godot --headless",
            "  14     1  99.0 /usr/bin/python3 tools/x.py",
            "garbage line",
        ])
        found = pc.competing_processes(table, mine=500)
        self.assertEqual([entry.split()[0] for entry in found], ["10", "12"])


class TimeBudget(unittest.TestCase):
    def args(self, **overrides):
        values = dict(started=0.0, wait_left=0.0, poll_seconds=15, budget=10, min_idle=0.5)
        return argparse.Namespace(**(values | overrides))

    def test_estimate_counts_builds_only_for_unbuilt_worktrees(self):
        built = pc.work_estimate([True], "quick", 3)
        self.assertEqual(pc.work_estimate([False], "quick", 3), built + pc.ESTIMATE_S["build"])
        self.assertGreater(pc.work_estimate([True], "full", 3), built)
        self.assertEqual(pc.work_estimate([], "quick", 3), 0)

    def test_allowance_is_what_the_work_leaves_and_never_negative(self):
        self.assertEqual(pc.wait_allowance(600, 0, 200), 400)
        self.assertEqual(pc.wait_allowance(600, 500, 200), 0)

    def test_refuses_to_wait_once_the_allowance_is_spent(self):
        args = self.args()
        with mock.patch.object(pc, "load_gate", return_value=["cpu busy"]), \
             mock.patch.object(pc, "cpu_idle", return_value=0.1), \
             mock.patch.object(pc, "process_table", return_value=""), \
             mock.patch.object(pc.time, "monotonic", return_value=30), \
             mock.patch.object(pc.time, "sleep") as sleep, self.assertRaises(pc.Deferred):
            pc.wait_for_quiet_machine(args, [])
        sleep.assert_not_called()

    def test_quiet_machine_runs_without_wait_allowance_if_budget_remains(self):
        with mock.patch.object(pc, "cpu_idle", return_value=0.9), \
             mock.patch.object(pc, "process_table", return_value=""), \
             mock.patch.object(pc.time, "monotonic", return_value=30):
            self.assertEqual(pc.wait_for_quiet_machine(self.args(), [])["busy"], [])

    def test_wont_sleep_past_the_run_budget_with_waiting_allowance_left(self):
        with mock.patch.object(pc, "cpu_idle", return_value=0.1), \
             mock.patch.object(pc, "process_table", return_value=""), \
             mock.patch.object(pc.time, "monotonic", return_value=590), \
             mock.patch.object(pc.time, "sleep") as sleep, self.assertRaisesRegex(pc.Deferred, "busy"):
            pc.wait_for_quiet_machine(self.args(wait_left=120), [])
        sleep.assert_not_called()

    def test_refuses_to_sample_after_the_run_budget_expires(self):
        with mock.patch.object(pc, "cpu_idle", return_value=0.9) as sample, \
             mock.patch.object(pc, "process_table", return_value=""), \
             mock.patch.object(pc.time, "monotonic", return_value=600), \
             self.assertRaisesRegex(pc.Deferred, "budget.*expired"):
            pc.wait_for_quiet_machine(self.args(), [])
        sample.assert_not_called()

    def test_refuses_a_quiet_sample_that_finishes_after_the_budget(self):
        elapsed = 599

        def cpu_idle():
            nonlocal elapsed
            elapsed = 600
            return 0.9

        with mock.patch.object(pc, "cpu_idle", side_effect=cpu_idle), \
             mock.patch.object(pc, "process_table", return_value=""), \
             mock.patch.object(pc.time, "monotonic", side_effect=lambda: elapsed), \
             self.assertRaisesRegex(pc.Deferred, "budget.*expired"):
            pc.wait_for_quiet_machine(self.args(), [])

    def test_last_round_over_budget_cannot_complete_a_record(self):
        elapsed = 0

        def perf_round(*_):
            nonlocal elapsed
            elapsed += 30
            return {"errors": [], "metrics": {}}

        args = self.args(rev="a", godot="godot", scenario=SCENARIO, tier="quick", rounds=2, budget=1)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            archive = pc.Archive(repo)
            with mock.patch.object(pc, "machine_identity", return_value={"machine": "m", "machine_label": "test"}), \
                 mock.patch.object(pc, "toolchain_identity", return_value={}), \
                 mock.patch.object(pc, "resolve", return_value=("a" * 40, "test")), \
                 mock.patch.object(pc, "prepare_worktree", return_value=repo), \
                 mock.patch.object(pc, "golden_check", return_value={"passed": True}), \
                 mock.patch.object(pc, "cpu_idle", return_value=0.9), \
                 mock.patch.object(pc, "process_table", return_value=""), \
                 mock.patch.object(pc, "perf_round", side_effect=perf_round) as measure, \
                 mock.patch.object(pc.time, "monotonic", side_effect=lambda: elapsed), \
                 self.assertRaisesRegex(pc.Deferred, "budget.*expired"):
                pc.command_measure(args, repo, archive)
            self.assertEqual(measure.call_count, 2)
            self.assertFalse((repo / "index.jsonl").exists())

    def test_zero_budget_is_unlimited(self):
        with mock.patch.object(pc, "cpu_idle", return_value=0.9), \
             mock.patch.object(pc, "process_table", return_value=""), \
             mock.patch.object(pc.time, "monotonic", return_value=1000):
            self.assertEqual(pc.wait_for_quiet_machine(self.args(budget=0), [])["busy"], [])

    def test_refuses_negative_budget_and_impossible_idle_floor(self):
        command = ["compare", "a", "b", "--claim", "run_ms"]
        for value in ("-1", "nan", "inf"):
            with self.subTest(budget=value), contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(pc.main([*command, "--budget", value]), pc.EXIT_USAGE)
                self.assertIn("--budget", stderr.getvalue())
        for value in ("0", "1.5"):
            with self.subTest(min_idle=value):
                self.assertEqual(pc.main([*command, "--min-idle", value]), pc.EXIT_USAGE)


class GoldenComparison(unittest.TestCase):
    def test_identical_results_pass(self):
        value = {"days": [{"day": 1, "domain_hashes": {"ECONOMY": "1"}}]}
        self.assertIsNone(pc.first_difference(value, value))

    def test_refuses_changed_hash_length_type_and_keys(self):
        base = {"days": [{"day": 1, "domain_hashes": {"ECONOMY": "1"}}]}
        for head in ({"days": [{"day": 1, "domain_hashes": {"ECONOMY": "2"}}]},
                     {"days": []}, {"days": {}},
                     {"days": [{"day": 1, "domain_hashes": {"CLIMATE": "1"}}]}):
            with self.subTest(head=head):
                self.assertIsNotNone(pc.first_difference(base, head))


class Judgement(unittest.TestCase):
    ROWS = [{"metric": "csv.t_sus_ms.mean", "status": "improved", "change": -0.3},
            {"metric": "result.run_ms", "status": "within_noise", "change": -0.05}]

    def test_pass_when_claim_improves(self):
        self.assertEqual(pc.judge([], [], self.ROWS, [r"t_sus_ms"]), ("pass", []))

    def test_refuses_pass_when_results_changed_or_runs_invalid(self):
        self.assertEqual(pc.judge(["hash differs"], [], self.ROWS, [])[0], "fail")
        self.assertEqual(pc.judge([], ["round 1: fatal"], self.ROWS, [])[0], "fail")

    def test_refuses_pass_when_claim_missing_or_not_improved(self):
        self.assertEqual(pc.judge([], [], self.ROWS, [])[0], "needs_human")
        self.assertEqual(pc.judge([], [], self.ROWS, [r"no_such_metric"])[0], "needs_human")
        self.assertEqual(pc.judge([], [], self.ROWS, [r"run_ms"])[0], "needs_human")

    def test_refuses_pass_when_headline_regressed(self):
        for metric, base, head in (("result.run_ms", [10, 10], [14, 14]),
                                   ("rusage.maxrss_mb", [600, 600], [601, 601])):
            with self.subTest(metric=metric):
                rows = [self.ROWS[0], pc.compare_metric(metric, base, head)]
                status, reasons = pc.judge([], [], rows, ["t_sus_ms"])
                self.assertEqual(status, "needs_human")
                self.assertTrue(any(metric in reason for reason in reasons))

    def test_refuses_pass_when_any_metric_in_a_claim_regresses(self):
        for metric, base, head in (("csv.household_market_ms.p95", [10, 10], [14, 14]),
                                   ("csv.household_market_memory_bytes.mean", [500, 500], [501, 501])):
            with self.subTest(metric=metric):
                rows = [
                    pc.compare_metric("csv.household_market_ms.mean", [10, 10], [6, 6]),
                    pc.compare_metric(metric, base, head),
                ]
                status, reasons = pc.judge([], [], rows, ["household_market"])
                self.assertEqual(status, "needs_human")
                self.assertTrue(any(metric in reason for reason in reasons))

    def test_refuses_pass_if_an_unclaimed_measurement_is_missing(self):
        base = {"result.run_ms": 100, "csv.optional_ms.max": 10}
        head = {"result.run_ms": 65, "csv.optional_ms.max": 10}
        base_missing, head_missing = {"result.run_ms": 100}, {"result.run_ms": 65}
        for base_rounds, head_rounds in (([base] * 3, [head_missing] * 3),
                                         ([base] * 3, [head, head_missing, head]),
                                         ([base_missing] * 3, [head] * 3)):
            with self.subTest(base_rounds=base_rounds, head_rounds=head_rounds):
                rows = pc.compare_rounds(base_rounds, head_rounds)
                status, reasons = pc.judge([], [], rows, ["result.run_ms"])
                self.assertEqual(status, "fail")
                self.assertTrue(any("csv.optional_ms.max" in reason for reason in reasons))


class Assessment(unittest.TestCase):
    """Found on the first real run: an invalid round used to skip the base/head result comparison."""

    def side(self, tmp, name, hashes, errors):
        candidate = Path(tmp) / f"{name}.json"
        candidate.write_text(json.dumps({"days": [{"day": 1, "domain_hashes": hashes}]}))
        rounds = [{"metrics": {"result.run_ms": 100.0 + i}, "errors": list(e)} for i, e in enumerate(errors)]
        return {"identity": {"commit": name * 12}, "golden": {"passed": True, "candidate": str(candidate)},
                "rounds": rounds}

    def test_result_difference_is_reported_even_when_a_round_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.side(tmp, "a", {"ECONOMY": "1"}, [["exit=6"], [], []])
            head = self.side(tmp, "b", {"ECONOMY": "2"}, [[], [], []])
            verdict = pc.assess(base, head, [], pc.NOISE)
        self.assertEqual(verdict["status"], "fail")
        self.assertTrue(any("differ" in reason for reason in verdict["reasons"]))
        self.assertTrue(any("exit=6" in reason for reason in verdict["reasons"]))

    def test_invalid_rounds_are_left_out_of_the_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.side(tmp, "a", {"ECONOMY": "1"}, [["exit=6"], [], []])
            head = self.side(tmp, "b", {"ECONOMY": "1"}, [[], [], []])
            verdict = pc.assess(base, head, [], pc.NOISE)
        row, = [r for r in verdict["rows"] if r["metric"] == "result.run_ms"]
        self.assertEqual(row["base"], [101.0, 102.0])
        self.assertEqual(verdict["excluded_rounds"], ["base round 1: exit=6"])

    def test_quick_comparison_can_reuse_a_full_tier_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.side(tmp, "a", {"ECONOMY": "1"}, [[], []])
            head = self.side(tmp, "b", {"ECONOMY": "1"}, [[], []])
            base["tier"] = "full"
            base["load_consistency"] = {"passed": True}
            head["tier"] = "quick"
            for run in base["rounds"]:
                run["metrics"]["waterfall.total_ms.mean"] = 100
            for run in head["rounds"]:
                run["metrics"]["result.run_ms"] = 60
            verdict = pc.assess(base, head, ["result.run_ms"], pc.NOISE)
        self.assertEqual(verdict["status"], "pass")
        self.assertEqual([row["metric"] for row in verdict["rows"]], ["result.run_ms"])

    def test_report_uses_the_round_counts_from_the_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base = self.side(tmp, "a", {"ECONOMY": "1"}, [[], [], [], []])
            head = self.side(tmp, "b", {"ECONOMY": "1"}, [[], [], []])
            for saved in (base, head):
                saved["identity"] = IDENTITY | saved["identity"]
            base["reused"] = True
            base["created"] = "2026-11-24T12:00:00Z"
            for run in head["rounds"]:
                run["metrics"]["result.run_ms"] = 60
            args = pc.parse_args(["compare", "a", "b", "--claim", "result.run_ms", "--out", tmp])
            args.started = pc.time.monotonic()
            with mock.patch.object(pc, "ensure_records", return_value=[base, head]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pc.command_compare(args, repo, pc.Archive(repo)), pc.EXIT_PASS)
            report = json.loads((repo / "report.json").read_text())
            self.assertEqual(report["requested_rounds"], 3)
            self.assertEqual(report["base"]["rounds"], 4)
            self.assertEqual(report["head"]["rounds"], 3)
            self.assertIn("base 4 rounds, head 3 rounds", (repo / "report.md").read_text())


class BuildRecipe(unittest.TestCase):
    def test_builds_only_the_debug_target_the_headless_editor_loads(self):
        command = pc.scons_command("Darwin", "arm64", 8)
        self.assertIn("target=template_debug", command)
        self.assertNotIn("target=template_release", command)
        self.assertIn("arch=arm64", command)

    def test_checked_in_libraries_of_other_platforms_do_not_count_as_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / pc.PROJECT / pc.LIBRARY_DIR
            (bin_dir / "android").mkdir(parents=True)
            (bin_dir / "android" / "libdots_ext.android.template_debug.arm64.so").write_text("x")
            (bin_dir / "macos").mkdir()
            (bin_dir / "macos" / "libdots_ext.macos.template_release.arm64.dylib").write_text("x")
            self.assertEqual(pc.debug_libraries(Path(tmp), "Darwin", "arm64"), [])
            built = bin_dir / "macos" / "libdots_ext.macos.template_debug.arm64.dylib"
            built.write_text("x")
            self.assertEqual(pc.debug_libraries(Path(tmp), "Darwin", "arm64"), [built])

    def test_refuses_unknown_platform_or_architecture(self):
        for system, machine in (("SunOS", "x86_64"), ("Darwin", "riscv64")):
            with self.subTest(system=system, machine=machine), self.assertRaises(pc.StepFailed):
                pc.scons_command(system, machine, 8)

    def test_refuses_to_start_build_while_machine_is_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            archive = pc.Archive(repo)
            args = argparse.Namespace(started=pc.time.monotonic(), wait_left=0,
                                      budget=10, min_idle=0.5, poll_seconds=15)
            with mock.patch.object(pc, "cpu_idle", return_value=0.1), \
                 mock.patch.object(pc, "process_table", return_value=""), \
                 mock.patch.object(pc, "compile_commit") as compile_commit, \
                 mock.patch.object(pc, "git") as git, self.assertRaisesRegex(pc.Deferred, "busy"):
                pc.prepare_worktree(repo, archive, "a" * 40, args, repo, [])
            compile_commit.assert_not_called()
            git.assert_not_called()

    def test_refuses_to_import_if_the_machine_became_busy_during_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            archive = pc.Archive(repo)
            args = argparse.Namespace(started=pc.time.monotonic(), wait_left=0,
                                      budget=10, min_idle=0.5, poll_seconds=15)
            with mock.patch.object(pc, "cpu_idle", side_effect=[0.9, 0.1]), \
                 mock.patch.object(pc, "process_table", return_value=""), \
                 mock.patch.object(pc, "compile_commit", return_value=[]) as compile_commit, \
                 mock.patch.object(pc, "git"), mock.patch.object(pc, "run") as run, \
                 self.assertRaisesRegex(pc.Deferred, "busy"):
                pc.prepare_worktree(repo, archive, "a" * 40, args, repo, [])
            compile_commit.assert_called_once()
            run.assert_not_called()


class ArgumentChecks(unittest.TestCase):
    def test_refuses_single_round_and_nonpositive_scenario(self):
        self.assertEqual(pc.main(["compare", "a", "b", "--claim", "run_ms", "--rounds", "1"]), pc.EXIT_USAGE)
        self.assertEqual(pc.main(["measure", "a", "--days", "0"]), pc.EXIT_USAGE)

    def test_compare_requires_an_explicit_nonempty_claim(self):
        for flags in ([], ["--claim", ""], ["--claim", "["]):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(pc.main(["compare", "a", "b", *flags]), pc.EXIT_USAGE)
                self.assertIn("--claim", stderr.getvalue())

    def test_history_starts_without_unix_fcntl(self):
        with mock.patch.dict(sys.modules, {"fcntl": None}), \
             mock.patch.object(pc.platform, "system", return_value="Windows"), \
             tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as stdout:
            main = runpy.run_path(pc.__file__)["main"]
            self.assertEqual(main(["--home", tmp, "history"]), pc.EXIT_PASS)
            self.assertIn("archive is empty", stdout.getvalue())
            self.assertEqual(main(["--home", tmp, "measure", "a"]), pc.EXIT_FAIL)
            self.assertIn("macOS or Linux", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
