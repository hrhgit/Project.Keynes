"""The performance claim section and the factory's call into tools/perf/perf_change_check.py.

Refusals are registered in test_gates_refuse.py; this file covers what must be accepted and the real
subprocess path, with a stand-in script in place of the measuring one."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import perf  # noqa: E402
from common import load_config  # noqa: E402
from ticket import gate  # noqa: E402

CRITERIA = "## Acceptance criteria\n- [ ] economy memory falls\n"


class ClaimSection(unittest.TestCase):
    def test_no_section_means_no_performance_check(self):
        self.assertIsNone(perf.parse_claim_section(CRITERIA))
        self.assertIsNone(perf.parse_claim_section(""))

    def test_claims_and_tier_are_read(self):
        body = CRITERIA + ("\n## Performance claim\n- `result.economy_memory_bytes`\n\n"
                           "* `household_market.*_ms`\nTier: FULL\n\n## Notes\n- `ignored`\n")
        self.assertEqual(perf.parse_claim_section(body),
                         (["result.economy_memory_bytes", "household_market.*_ms"], "full"))

    def test_tier_defaults_to_quick_and_chinese_heading_is_accepted(self):
        self.assertEqual(perf.parse_claim_section("## 性能声明\n- `result.run_ms`\n"), (["result.run_ms"], "quick"))

    def test_written_section_reads_back(self):
        claims = ["result.economy_memory_bytes", "csv\\.household_market_ms\\.mean"]
        self.assertEqual(perf.parse_claim_section(perf.claim_text(claims, "full")), (claims, "full"))

    def test_ticket_gate_accepts_a_good_section(self):
        self.assertEqual(gate("t", CRITERIA + "## Performance claim\n- `result.run_ms`\n", [], []), [])


class ResultLine(unittest.TestCase):
    def test_each_status_with_its_exit_code(self):
        for status, code in perf.EXITS.items():
            report = None if status == "deferred" else "/archive/report.md"
            line = "PERF_CHECK_RESULT=" + json.dumps({"status": status, "reasons": ["r"], "report": report})
            with self.subTest(status=status):
                self.assertEqual(perf.parse_perf_result(f"built\n{line}\n", code),
                                 {"status": status, "reasons": ["r"], "report": report})


    def test_a_failure_with_a_reason_and_no_report_is_read(self):
        # The script prints this when a build or worktree step fails before any report exists.
        line = "PERF_CHECK_RESULT=" + json.dumps({"status": "fail", "reasons": ["scons exited 2"]})
        self.assertEqual(perf.parse_perf_result(line, 1), {"status": "fail", "reasons": ["scons exited 2"], "report": None})


STAND_IN = """import json, sys
print("argv=" + json.dumps(sys.argv[1:]))
print("PERF_CHECK_RESULT=" + json.dumps({"status": STATUS, "reasons": ["claimed metric improved"],
                                         "report": "REPORT"}))
sys.exit(CODE)
"""


class RunScript(unittest.TestCase):
    def run_with(self, status, code):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        script = tmp / "runner" / perf.SCRIPT
        script.parent.mkdir(parents=True)
        report = tmp / "report.md"
        report.write_text("# Report\n")
        script.write_text(STAND_IN.replace("STATUS", repr(status)).replace("CODE", str(code))
                          .replace("REPORT", str(report)))
        cfg = load_config()
        cfg["tools"]["python"] = sys.executable
        log = tmp / "perf.log"
        return perf.run(cfg, str(tmp / "runner"), str(tmp), "b" * 40, "h" * 40,
                        ["result.run_ms", "household_market.*_ms"], "full", str(log)), log

    def test_passes_commits_claims_and_tier_and_reads_the_verdict(self):
        result, log = self.run_with("pass", 0)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(perf.report_excerpt(result), "# Report\n")
        argv = json.loads(log.read_text().splitlines()[0].removeprefix("argv="))
        self.assertEqual(argv[argv.index("compare"):],
                         ["compare", "b" * 40, "h" * 40, "--tier", "full",
                          "--claim", "result.run_ms", "--claim", "household_market.*_ms"])
        self.assertIn("--repo", argv)

    def test_a_status_that_disagrees_with_the_exit_code_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_with("pass", 1)

    def stand_in(self, text):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        script = tmp / "runner" / perf.SCRIPT
        script.parent.mkdir(parents=True)
        script.write_text(text)
        cfg = load_config()
        cfg["tools"]["python"] = sys.executable
        return cfg, lambda: perf.run(cfg, str(tmp / "runner"), str(tmp), "b", "h", ["x"], "quick", str(tmp / "log"))

    def test_the_factory_environment_is_not_passed_to_the_measured_code(self):
        cfg, run = self.stand_in(
            "import json, os, sys\n"
            "seen = sorted(k for k in ('GH_TOKEN', 'OPENAI_API_KEY', 'PATH', 'HOME') if k in os.environ)\n"
            "print('PERF_CHECK_RESULT=' + json.dumps({'status': 'fail', 'reasons': seen}))\n"
            "sys.exit(1)\n")
        with patch.dict(os.environ, {"GH_TOKEN": "not-a-real-token", "OPENAI_API_KEY": "not-a-real-key"}):
            self.assertEqual(run()["reasons"], ["HOME", "PATH"])

    def test_a_timeout_keeps_its_reason(self):
        cfg, run = self.stand_in("import time\ntime.sleep(30)\n")
        cfg["limits"]["perfCheckTimeoutMinutes"] = 0.02
        with self.assertRaisesRegex(ValueError, "timed out after"):
            run()

    def test_missing_script_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            perf.run(load_config(), tmp, tmp, "b", "h", ["x"], "quick", str(Path(tmp) / "log"))


if __name__ == "__main__":
    unittest.main()
