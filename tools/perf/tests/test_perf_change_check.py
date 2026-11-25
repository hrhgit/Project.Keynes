"""perf_change_check decides whether a performance change may proceed (AGENTS.md rule 6).

Each gate, parser and classifier is fed inputs it must refuse, not only good ones.
Run: python -m unittest tools/perf/tests/test_perf_change_check.py -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import perf_change_check as pc  # noqa: E402

SCENARIO = dict(pc.DEFAULT_SCENARIO)
GOOD_RESULT = {"rows": "50", "expected_rows": "50", "fatal": "false", "economy_configured": "true",
               "formal_start": "true", "ledger_failures": "0", "population": "1200",
               "country_count": "4", "path": "/tmp/perf.csv"}
IDENTITY = {"commit": "a" * 40, "scenario": SCENARIO, "method_version": pc.METHOD_VERSION,
            "machine": "m1", "machine_label": "Mac", "toolchain": "t1", "toolchain_label": "godot"}


def record(**changes):
    value = {"status": "complete", "tier": "quick", "identity": dict(IDENTITY)}
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
        self.assertEqual(pc.validate_perf_run(0, GOOD_RESULT, 50, SCENARIO), [])

    def test_refuses_each_broken_fact(self):
        cases = {
            "exit": (1, GOOD_RESULT, 50),
            "no result": (0, None, 50),
            "short csv": (0, GOOD_RESULT, 49),
            "missing csv": (0, GOOD_RESULT, None),
            "rows": (0, GOOD_RESULT | {"rows": "49"}, 50),
            "expected rows": (0, GOOD_RESULT | {"expected_rows": "10"}, 50),
            "fatal": (0, GOOD_RESULT | {"fatal": "true"}, 50),
            "fatal missing": (0, {k: v for k, v in GOOD_RESULT.items() if k != "fatal"}, 50),
            "ledger": (0, GOOD_RESULT | {"ledger_failures": "2"}, 50),
            "ledger not a number": (0, GOOD_RESULT | {"ledger_failures": "nan"}, 50),
            "economy": (0, GOOD_RESULT | {"economy_configured": "false"}, 50),
            "synthetic start": (0, GOOD_RESULT | {"formal_start": "false"}, 50),
            "no population": (0, GOOD_RESULT | {"population": "0"}, 50),
            "too few countries": (0, GOOD_RESULT | {"country_count": "2"}, 50),
        }
        for name, (code, result, rows) in cases.items():
            with self.subTest(name):
                self.assertTrue(pc.validate_perf_run(code, result, rows, SCENARIO))


class MetricClassification(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(pc.metric_kind("csv.bd_economy_scan_cells.per_day"), "counter")
        self.assertEqual(pc.metric_kind("csv.t_sus_ms.p95"), "timing")
        self.assertEqual(pc.metric_kind("rusage.maxrss_mb"), "timing")
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
        rows = [{"bd_economy_scan_a": "0", "t_sus_ms": "1", "label": "x"},
                {"bd_economy_scan_a": "10", "t_sus_ms": "3", "label": "x"},
                {"bd_economy_scan_a": "20", "t_sus_ms": "2", "label": "x"}]
        metrics = pc.csv_metrics(rows)
        self.assertEqual(metrics["csv.bd_economy_scan_a.per_day"], 10)
        self.assertEqual(metrics["csv.t_sus_ms.max"], 3)
        self.assertNotIn("csv.label.mean", metrics)

    def test_refuses_partially_numeric_column(self):
        rows = [{"t_sus_ms": "1"}, {"t_sus_ms": ""}]
        self.assertEqual(pc.csv_metrics(rows), {})


class ArchiveReuse(unittest.TestCase):
    def test_reuses_identical_identity(self):
        self.assertTrue(pc.record_reusable(record(), dict(IDENTITY), "quick")[0])
        self.assertTrue(pc.record_reusable(record(tier="full"), dict(IDENTITY), "quick")[0])

    def test_refuses_any_identity_difference(self):
        for key, value in (("commit", "b" * 40), ("scenario", SCENARIO | {"days": 60}),
                           ("machine", "m2"), ("toolchain", "t2"),
                           ("method_version", pc.METHOD_VERSION + 1)):
            with self.subTest(key):
                self.assertFalse(pc.record_reusable(record(), IDENTITY | {key: value}, "quick")[0])

    def test_refuses_incomplete_invalid_missing_or_lower_tier(self):
        self.assertFalse(pc.record_reusable(None, IDENTITY, "quick")[0])
        self.assertFalse(pc.record_reusable(record(status="invalid"), IDENTITY, "quick")[0])
        self.assertFalse(pc.record_reusable(record(status="measuring"), IDENTITY, "quick")[0])
        self.assertFalse(pc.record_reusable(record(), IDENTITY, "full")[0])
        stored = record()
        stored["identity"] = IDENTITY | {"extra": 1}
        self.assertFalse(pc.record_reusable(stored, IDENTITY, "quick")[0])


class MachineLoadGate(unittest.TestCase):
    def test_quiet_machine_goes(self):
        self.assertEqual(pc.load_gate(1.0, 8, [], 0.5), [])

    def test_refuses_high_load_unknown_cpus_and_competitors(self):
        self.assertTrue(pc.load_gate(6.0, 8, [], 0.5))
        self.assertTrue(pc.load_gate(0.1, 0, [], 0.5))
        self.assertTrue(pc.load_gate(0.1, 8, ["123 godot 90% cpu"], 0.5))

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
        self.assertEqual(pc.judge([], [], self.ROWS, [r"no_such_metric"])[0], "needs_human")
        self.assertEqual(pc.judge([], [], self.ROWS, [r"run_ms"])[0], "needs_human")

    def test_refuses_pass_when_headline_regressed(self):
        rows = self.ROWS + [{"metric": "result.run_ms", "status": "regressed", "change": 0.4}]
        self.assertEqual(pc.judge([], [], rows, [])[0], "needs_human")


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


class ArgumentChecks(unittest.TestCase):
    def test_refuses_single_round_and_nonpositive_scenario(self):
        self.assertEqual(pc.main(["compare", "a", "b", "--rounds", "1"]), pc.EXIT_USAGE)
        self.assertEqual(pc.main(["measure", "a", "--days", "0"]), pc.EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
