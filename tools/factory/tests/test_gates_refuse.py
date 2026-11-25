"""Gates, parsers, allowlists and validators are tested with inputs they must refuse (AGENTS.md rule 6).

Every gate-like function in the factory is listed in GATES with at least one input it must refuse.
The AST scan fails when a new gate-named function is added without an entry, so the rule is
enforced by this test and not by anyone remembering it.
"""

import ast
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

FACTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))

import agent
import checks
import perf
import ticket
import verdict
import work
import watch_prs
from common import Result, lane_lock, legacy_lane_gate, load_config

CFG = load_config()
NATIVE = CFG["checks"]["nativeRuntimeCheck"]
FINDINGS = [{"id": "f1"}, {"id": "f10"}]


def refuses_dispute(text):
    try:
        agent.parse_disputes(text, FINDINGS)
    except ValueError:
        return True
    return False


def refuses_resolution(entries):
    try:
        agent.parse_conflict_resolutions(json.dumps(entries), ["file.gd"])
    except ValueError:
        return True
    return False


def refuses_conflict_file(action, make_file):
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "file.gd"
        make_file(path)
        try:
            work.validate_conflict_files(tmp, {path.name: (action, "Combine both edits")})
        except ValueError:
            return True
        return False


def symlink_to_text(path):
    target = path.with_name("target.txt")
    target.write_text("Valid text")
    path.symlink_to(target)


def refuses_claim(text):
    try:
        perf.parse_claim_section("## Performance claim\n" + text)
    except ValueError:
        return True
    return False


def refuses_result(output, code):
    try:
        perf.parse_perf_result(output, code)
    except ValueError:
        return True
    return False


def result_line(status="pass", reasons=("ok",), report="/r/report.md"):
    return "PERF_CHECK_RESULT=" + json.dumps({"status": status, "reasons": list(reasons), "report": report})


def pr(**kw):
    base = {"headRefOid": "abc", "labels": [], "isDraft": False, "isCrossRepository": False,
            "headRefName": "feature/x"}
    base.update(kw)
    return base


def skipped(**kw):
    return watch_prs.skip_before_review(pr(**kw), watch_prs.PrState(), CFG) is not None


def preflight_refuses(kind, *, remote_base="base1", moved=True):
    """Run a preflight on a fake watcher; True when it returned a refusal."""
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    p = {"number": 7, "headRefOid": "head1", "headRefName": "agent/issue-1", "baseRefName": "master",
         "baseRefOid": "base1", "labels": [], "changedFiles": 1}
    fresh = {**p, "state": "OPEN", "isDraft": False, "isCrossRepository": False, "mergeable": "MERGEABLE"}
    if kind == "update":
        fresh["labels"] = [CFG["labels"]["working"]]
    me = SimpleNamespace(cfg=CFG, workdir="/nonexistent", gh=Mock(errors=[]),
                         base_moved=lambda *a: moved)
    me.gh.pr_merge_state.return_value = fresh
    with patch("work.remote_head", return_value=remote_base):
        if kind == "update":
            return watch_prs.Watcher.update_preflight(me, p, "master", "base1", Mock()) is not None
        fresh["headRefOid"] = "other"
        return watch_prs.Watcher.merge_preflight(me, p) is not None


def refuses_legacy_owner(lane, entry):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "lock").write_text("42")
        owner = Result(0, f"python3 tools/factory/{entry}", "")
        with patch("common.sh", return_value=owner):
            return legacy_lane_gate(root, lane)


HEAD = "a" * 40
CLEAN_CI = verdict.CIFacts(HEAD, [verdict.CIRun("completed", "success")], [verdict.CIRun("completed", "success")])


def merge_refused(**session):
    """decide() on a mergeable PR with successful CI and no findings; True when it did not merge."""
    review = {"review_session": {"status": "completed", "commit_sha": HEAD, "review_complete": True, **session},
              "findings": []}
    p = pr(number=7, headRefOid=HEAD, mergeable="MERGEABLE")
    cfg = {**CFG, "autoMerge": True}
    return watch_prs.decide(p, review, watch_prs.PrState(), cfg, changed_files=[], ci=CLEAN_CI).action != "merge"


def judge_refused(**facts):
    """judge() on facts that are otherwise READY; True when it did not return READY."""
    base = dict(head="abc", checks_sha="abc", review_status="completed", review_complete=True, review_sha="abc",
                ci_state="success", findings=[])
    return verdict.judge(verdict.Facts(**{**base, **facts})).verdict != "READY"


def refuses_perf_check(status="pass", error=None, issue_job_running=False):
    """True when perf_check returns a skip or a stop instead of letting the merge go on."""
    with TemporaryDirectory() as tmp:
        cfg = dict(CFG, home=tmp)
        watcher = watch_prs.Watcher(cfg, dry=False)
        result = {"status": status, "reasons": ["r"], "report": "/archive/report.md", "command": [], "log": "l"}
        pr = {"number": 7, "headRefOid": "h" * 40, "baseRefOid": "c" * 40}
        with patch.object(watcher, "prepare_head", return_value=True), patch("work.git", return_value="b" * 40), \
                patch("perf.run", return_value=result, side_effect=error), patch.object(watcher, "stop"), \
                patch.object(watcher, "merge_preflight", return_value=None):
            check = lambda: watcher.perf_check(pr, watch_prs.PrState(), {}, (["result.run_ms"], "quick"))
            if not issue_job_running:
                return check() != (None, None)
            with lane_lock(Path(tmp), "issue"):
                return check() != (None, None)


# name -> list of (description, callable returning True when the gate refused the input)
GATES = {
    "legacy_lane_gate": [
        ("the old Issue runner owns the Issue workspace", lambda: refuses_legacy_owner("issue", "run.py")),
        ("the old PR runner owns the shared workspace", lambda: refuses_legacy_owner("issue", "watch_prs.py")),
        ("the old PR runner owns PR processing", lambda: refuses_legacy_owner("pr", "watch_prs.py")),
    ],
    "parse_disputes": [
        ("line without the '- ' marker", lambda: refuses_dispute("f1: evidence")),
        ("id that is only a prefix of a real id", lambda: refuses_dispute("- f: evidence")),
        ("unknown id", lambda: refuses_dispute("- f2: evidence")),
        ("empty evidence", lambda: refuses_dispute("- f1:")),
        ("whitespace-only evidence", lambda: refuses_dispute("- f1:   ")),
        ("no space after the colon", lambda: refuses_dispute("- f1:evidence")),
        ("backtick left inside the id", lambda: refuses_dispute("- `f1: evidence")),
        ("one good line and one bad line", lambda: refuses_dispute("- f1: ok\n- f9: no")),
    ],
    "parse_conflict_resolutions": [
        ("report is not an array", lambda: refuses_resolution({"file.gd": "keep"})),
        ("missing path", lambda: refuses_resolution([])),
        ("unrelated path", lambda: refuses_resolution([{"path": "../file.gd", "action": "keep", "reason": "Merge"}])),
        ("duplicate path", lambda: refuses_resolution([{"path": "file.gd", "action": "keep", "reason": "Merge"}] * 2)),
        ("unknown action", lambda: refuses_resolution([{"path": "file.gd", "action": "skip", "reason": "Merge"}])),
        ("empty reason", lambda: refuses_resolution([{"path": "file.gd", "action": "keep", "reason": "  "}])),
    ],
    "validate_conflict_files": [
        ("declared deletion still exists", lambda: refuses_conflict_file("delete", lambda p: p.touch())),
        ("kept file is missing", lambda: refuses_conflict_file("keep", lambda p: None)),
        ("kept path is a directory", lambda: refuses_conflict_file("keep", lambda p: p.mkdir())),
        ("kept file is a symlink", lambda: refuses_conflict_file("keep", symlink_to_text)),
        ("kept file is binary", lambda: refuses_conflict_file("keep", lambda p: p.write_bytes(b"\0binary"))),
    ],
    "classify_level": [
        ("missing level is unknown", lambda: verdict.classify_level(None) == "unknown"),
        ("misspelled level is unknown", lambda: verdict.classify_level("Informational") == "unknown"),
        ("empty level is unknown", lambda: verdict.classify_level("") == "unknown"),
    ],
    "classify": [
        ("missing status is unknown", lambda: verdict.classify({"action_level": "action_required"}) == "unknown"),
        ("non-string status is unknown", lambda: verdict.classify({"attribution_status": 3}) == "unknown"),
        ("unfamiliar status is unknown", lambda: verdict.classify({"attribution_status": "reopened"}) == "unknown"),
        ("open status with a missing level is unknown", lambda: verdict.classify({"attribution_status": "pending"}) == "unknown"),
    ],
    "unknown_findings": [
        ("an unfamiliar status is reported", lambda: bool(verdict.unknown_findings([{"id": "a", "attribution_status": "x"}]))),
        ("a missing level is reported when required", lambda: bool(
            verdict.unknown_findings([{"id": "a", "attribution_status": "implemented"}], require_level=True))),
    ],
    "native_line": [
        ("a second command after ;", lambda: not checks.native_line(NATIVE + " ; rm x", NATIVE)),
        ("a pipe", lambda: not checks.native_line(NATIVE + " | sh", NATIVE)),
        ("command substitution", lambda: not checks.native_line(NATIVE + " $(id)", NATIVE)),
        ("another script that starts with the same name", lambda: not checks.native_line(NATIVE + "x", NATIVE)),
        ("a redirect", lambda: not checks.native_line(NATIVE + " > out", NATIVE)),
    ],
    "extra_checks": [
        ("a command outside the allowlist is rejected", lambda: checks.extra_checks(["rm -rf x"], r"^godot ")[1] == ["rm -rf x"]),
        ("an allowlisted prefix with a second command is rejected, not accepted",
         lambda: checks.extra_checks(["godot a; rm x"], r"^godot [a-z./_]+$")[:2] == ([], ["godot a; rm x"])),
    ],
    "matches": [
        ("a folder pattern does not match a sibling that shares its prefix", lambda: not ticket.matches("tools/factory2/x.py", "tools/factory/")),
        ("an exact pattern does not match a longer path", lambda: not ticket.matches("a/bc", "a/b")),
        ("a glob does not match across a different name", lambda: not ticket.matches("tools/ci/other.json", "tools/ci/*baseline*.json")),
    ],
    "touching": [
        ("an unprotected file is not reported", lambda: ticket.touching(["docs/a.md"], CFG["paths"]["forbidden"]) == []),
        ("a protected file is reported", lambda: ticket.touching([".github/x.yml"], CFG["paths"]["forbidden"]) == [".github/x.yml"]),
    ],
    "scope": [
        ("a forbidden path is reported as forbidden", lambda: work.scope(CFG, ["tools/factory/a.py"])[0] == ["tools/factory/a.py"]),
        ("a project-keynes binary requires a person",
         lambda: work.scope(CFG, ["Project/project-keynes/addons/dots_ext/bin/macos/libdots_ext.dylib"])[1]
                 == ["Project/project-keynes/addons/dots_ext/bin/macos/libdots_ext.dylib"]),
        ("an ordinary path is reported in no list", lambda: work.scope(CFG, ["docs/a.md"]) == ([], [], [])),
    ],
    "gate": [
        ("empty title", lambda: bool(ticket.gate("", "## Acceptance criteria\n- [ ] a", [], []))),
        ("no criteria heading", lambda: bool(ticket.gate("t", "just text", [], []))),
        ("heading with no items", lambda: bool(ticket.gate("t", "## Acceptance criteria\nnothing", [], []))),
        ("a skip label", lambda: bool(ticket.gate("t", "## Acceptance criteria\n- [ ] a", ["no-agent"], ["no-agent"]))),
        ("a performance claim section the factory cannot read",
         lambda: bool(ticket.gate("t", "## Acceptance criteria\n- [ ] a\n\n## Performance claim\nfaster", [], []))),
    ],
    "parse_claim_section": [
        ("a heading with no metric", lambda: refuses_claim("")),
        ("a metric written without backticks", lambda: refuses_claim("- result.run_ms")),
        ("prose next to a good claim", lambda: refuses_claim("- `result.run_ms`\nshould be faster")),
        ("a regex that does not compile", lambda: refuses_claim("- `household_market.(*_ms`")),
        ("a blank claim", lambda: refuses_claim("- `   `")),
        ("an unknown tier", lambda: refuses_claim("- `result.run_ms`\nTier: windowed")),
        ("two tiers", lambda: refuses_claim("- `result.run_ms`\nTier: quick\nTier: full")),
        ("a tier and no metric", lambda: refuses_claim("Tier: full")),
        ("a second claim section later in the body",
         lambda: refuses_claim("- `result.run_ms`\n\n## Notes\nx\n\n## Performance claim\n- `result.economy_memory_bytes`")),
        ("a second section under the Chinese heading", lambda: refuses_claim("- `result.run_ms`\n## 性能声明\n- `x`")),
    ],
    "perf_check": [
        ("a failed comparison", lambda: refuses_perf_check("fail")),
        ("a comparison that needs a person", lambda: refuses_perf_check("needs_human")),
        ("a deferred comparison", lambda: refuses_perf_check("deferred")),
        ("a check that could not run", lambda: refuses_perf_check(error=ValueError("timed out after 3600s"))),
        ("an Issue job running on the same machine", lambda: refuses_perf_check(issue_job_running=True)),
        ("the passing case goes on (so the cases above test the refusals)", lambda: not refuses_perf_check("pass")),
    ],
    "parse_perf_result": [
        ("no result line", lambda: refuses_result("built\nimported", 0)),
        ("a result line that is not JSON", lambda: refuses_result("PERF_CHECK_RESULT={pass", 0)),
        ("a result line that is a list", lambda: refuses_result("PERF_CHECK_RESULT=[]", 0)),
        ("an unknown status", lambda: refuses_result(result_line("ok"), 0)),
        ("pass with a failing exit code", lambda: refuses_result(result_line("pass"), 1)),
        ("fail with exit 0", lambda: refuses_result(result_line("fail"), 0)),
        ("deferred with exit 0", lambda: refuses_result(result_line("deferred", report=None), 0)),
        ("reasons that are not strings", lambda: refuses_result(result_line(reasons=(1,)), 0)),
        ("pass without a report", lambda: refuses_result(result_line(report=None), 0)),
        ("fail with neither a report nor a reason", lambda: refuses_result(result_line("fail", reasons=(), report=None), 1)),
        ("a report path that is not a string", lambda: refuses_result(result_line(report=5), 0)),
        ("an earlier pass overridden by a later failure line",
         lambda: refuses_result(result_line("pass") + "\n" + result_line("fail"), 0)),
    ],
    "update_preflight": [
        ("an unreadable base branch", lambda: preflight_refuses("update", remote_base=None, moved=False)),
        ("a base that moved on the remote", lambda: preflight_refuses("update", remote_base="base2")),
    ],
    "merge_preflight": [
        ("a head that changed before merge", lambda: preflight_refuses("merge")),
    ],
    "decide": [
        ("a completed review that Qodo skipped as trivial", lambda: merge_refused(review_complete=False)),
        ("a review with no review_complete field", lambda: merge_refused(review_complete=None)),
        ("review_complete given as a string", lambda: merge_refused(review_complete="true")),
        ("a review of an older commit", lambda: merge_refused(commit_sha="b" * 40)),
        ("a review that ended with another status", lambda: merge_refused(status="failed")),
    ],
    "judge": [
        ("a completed review that Qodo skipped as trivial", lambda: judge_refused(review_complete=False)),
        ("review completeness unknown", lambda: judge_refused(review_complete=None)),
        ("a review of an older commit", lambda: judge_refused(review_sha="old")),
        ("local checks on another commit", lambda: judge_refused(checks_sha="old")),
        ("CI still pending", lambda: judge_refused(ci_state="pending")),
        ("a closed finding with no action_level", lambda: judge_refused(
            findings=[{"id": "a", "attribution_status": "implemented"}])),
    ],
    "skip_before_review": [
        ("a draft PR", lambda: skipped(isDraft=True)),
        ("a PR from another repository", lambda: skipped(isCrossRepository=True)),
        ("a skip label", lambda: skipped(labels=[CFG["skipLabels"][0]])),
        ("an issue branch the runner has not handed over",
         lambda: skipped(headRefName=CFG["issueBranchPrefix"] + "1")),
    ],
}

NAME_PARTS = ("perf_check", "matches", "touching", "scope", "gate", "parse", "classify", "validate", "allowed", "native_line", "extra_checks", "unknown_findings", "preflight", "decide", "judge")
EXEMPT = {"gate": "registered as ticket.gate"}


def gate_functions():
    found = set()
    for path in FACTORY.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and \
                    any(p in node.name for p in NAME_PARTS):
                found.add(node.name)
    return found


class GatesRefuse(unittest.TestCase):
    def test_every_gate_refuses_its_bad_inputs(self):
        for name, cases in GATES.items():
            self.assertTrue(cases, name)
            for description, refused in cases:
                with self.subTest(gate=name, case=description):
                    self.assertTrue(refused())

    def test_merge_and_ready_gates_accept_a_clean_case(self):
        # Without this, every refusal above would pass for a gate that refuses everything.
        self.assertFalse(merge_refused())
        self.assertFalse(judge_refused())

    def test_every_gate_function_is_registered(self):
        missing = sorted(gate_functions() - set(GATES) - set(KNOWN_UNLISTED))
        self.assertEqual(missing, [], "gate-like functions with no refusal test; add them to GATES")

    def test_rule_text_matches_the_evidence_and_names_this_test(self):
        rules = FACTORY.parents[1] / "AGENTS.md"
        if not rules.is_file():
            self.skipTest("the repository rules are outside this checkout")
        import count_findings
        c = count_findings.count()
        text = rules.read_text()
        self.assertIn(f"{c['gate_input']} of {c['total']} findings", text)
        self.assertIn("test_gates_refuse.py", text)


# Functions whose names match but that are not gates; each needs a reason.
KNOWN_UNLISTED = {
    "scope_problems": "calls work.scope, whose refusals are in GATES; the stop is exercised in test_workflow.py",
    "scope_problem": "calls Candidate.scope over work.scope; refusals are in GATES",
    "scope_blocked": "reports scope_problem's result; refusals are in GATES",
}

if __name__ == "__main__":
    unittest.main()
