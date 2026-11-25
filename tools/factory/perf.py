"""The performance check as a merge condition.

A PR (or the ticket it came from) that claims a performance gain carries a section

    ## Performance claim
    - `result.economy_memory_bytes`
    - `household_market.*_ms`
    Tier: full

Each item is a regex over metric names, passed to `tools/perf/perf_change_check.py --claim`. `Tier:`
is optional (`quick` by default). The factory runs its own copy of the script (the runner checkout,
not the PR's), and the outcome is read only from the script's `PERF_CHECK_RESULT=` line and exit code.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from common import sh
from ticket import heading_count, section

TITLES = ("performance claim", "性能声明")
CLAIM = re.compile(r"^\s*[-*]\s+`([^`]+)`\s*$")
TIER = re.compile(r"^\s*tier:\s*(\S+)\s*$", re.I)
TIERS = ("quick", "full")
SCRIPT = "tools/perf/perf_change_check.py"
RESULT = "PERF_CHECK_RESULT="
# The script's exit code for each status; a line whose status and exit disagree is not trusted.
EXITS = {"pass": 0, "fail": 1, "needs_human": 2, "deferred": 75}
# The only variables the check's subprocess sees. It builds and runs the PR's code, so the factory's
# tokens and keys (GH_TOKEN, OPENAI_API_KEY, ...) are not passed on.
ENV_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TERM")


def parse_claim_section(body: str) -> tuple[list[str], str] | None:
    """The claims and tier from the PR or ticket body. None when there is no claim section.

    Raises ValueError for a section the factory cannot act on, so a typo never turns a claimed
    performance change into an unchecked one."""
    lines = section(body, TITLES)
    if lines is None:
        return None
    if heading_count(body, TITLES) > 1:
        raise ValueError("the body has more than one performance claim section; merge them into one")
    claims: list[str] = []
    tier = None
    for line in lines:
        if not line.strip():
            continue
        m, t = CLAIM.match(line), TIER.match(line)
        if m:
            pattern = m.group(1).strip()
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"the performance claim `{pattern}` is not a valid regex: {e}") from e
            if not pattern:
                raise ValueError("a performance claim is empty")
            claims.append(pattern)
        elif t:
            if tier is not None:
                raise ValueError("the performance claim section names the tier twice")
            tier = t.group(1).lower()
            if tier not in TIERS:
                raise ValueError(f"unknown performance tier {t.group(1)!r}; use quick or full")
        else:
            raise ValueError(f"unreadable line in the performance claim section: {line.strip()[:200]!r}")
    if not claims:
        raise ValueError("the performance claim section lists no metric")
    return claims, tier or "quick"


def claim_text(claims: list[str], tier: str) -> str:
    """The section as the factory writes it into a PR body; parse_claim_section reads it back."""
    return "## Performance claim\n" + "".join(f"- `{c}`\n" for c in claims) + f"Tier: {tier}\n"


def parse_perf_result(output: str, code: int) -> dict:
    """The script's verdict. Raises ValueError unless the last result line is well formed and its
    status matches the exit code."""
    lines = [l for l in (output or "").splitlines() if l.startswith(RESULT)]
    if not lines:
        raise ValueError(f"the performance check printed no {RESULT} line (exit {code})")
    try:
        result = json.loads(lines[-1][len(RESULT):])
    except json.JSONDecodeError as e:
        raise ValueError(f"the {RESULT} line is not JSON: {e}") from e
    if not isinstance(result, dict):
        raise ValueError(f"the {RESULT} line is not an object")
    status, reasons = result.get("status"), result.get("reasons")
    if status not in EXITS:
        raise ValueError(f"unknown performance check status {status!r}")
    if EXITS[status] != code:
        raise ValueError(f"the performance check reported {status!r} but exited {code}")
    if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
        raise ValueError("the performance check reasons are not a list of strings")
    report = result.get("report")
    if report is not None and not isinstance(report, str):
        raise ValueError("the performance check report path is not a string")
    if status == "pass" and report is None:
        raise ValueError("the performance check reported 'pass' without a report path")
    if status != "pass" and report is None and not reasons:
        raise ValueError(f"the performance check reported {status!r} with neither a report nor a reason")
    return {"status": status, "reasons": reasons, "report": report}


def report_excerpt(result: dict, limit: int = 6000) -> str:
    path = result.get("report")
    if not path:
        return ""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        return f"(the report {path} could not be read: {e})"
    return text if len(text) <= limit else text[:limit] + f"\n\n… cut; full report at `{path}`"


def run(cfg: dict, runner_dir: str, repo: str, base: str, head: str, claims: list[str], tier: str,
        log: str) -> dict:
    """Run the factory's own copy of the script on base..head and return its parsed verdict.

    The script waits for a quiet machine inside its 10-minute budget and defers otherwise, so the
    factory never measures while its own regression jobs or a build are running."""
    script = Path(runner_dir) / SCRIPT
    if not script.is_file():
        raise ValueError(f"the factory has no performance check script at {script}")
    tools = cfg["tools"]
    args = [tools["python"], str(script), "--repo", repo, "--godot", str(Path(tools["godot"]).expanduser()),
            "--scons", str(Path(tools["scons"]).expanduser()), "compare", base, head, "--tier", tier]
    for claim in claims:
        args += ["--claim", claim]
    env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
    r = sh(args, cwd=repo, timeout=cfg["limits"].get("perfCheckTimeoutMinutes", 60) * 60, log=log,
           env=env, inherit_env=False)
    try:
        output = Path(log).read_text(encoding="utf-8", errors="replace")
    except OSError:
        output = ""
    try:
        verdict = parse_perf_result(output, r.code)
    except ValueError as e:
        # A timeout or a missing interpreter leaves no result line; say so instead of only "no line".
        cause = f"{r.err.strip()}; " if r.err.strip() else ""
        raise ValueError(f"{cause}{e}") from e
    return {**verdict, "command": args, "log": log}
