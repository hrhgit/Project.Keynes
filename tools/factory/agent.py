"""Codex calls. Codex writes code; the factory decides what happens next from facts."""

from __future__ import annotations

import json
from pathlib import Path

from common import FACTORY, godot_environment, sh
from ticket import section


REVIEW_RULES = FACTORY.parents[1] / "docs" / "factory" / "qodo-rules.json"
# Prompts that do not get the review rules, with the reason. Every other prompt lets Codex write code and
# must contain `{review_rules}`; test_factory.py enforces both.
PROMPTS_WITHOUT_RULES = {"plan": "read-only investigation; Codex writes no code"}


def render(name: str, **values: str) -> str:
    text = (FACTORY / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    if "{review_rules}" in text and "review_rules" not in values:
        values = {**values, "review_rules": review_rules()}
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def review_rules(path: Path = REVIEW_RULES) -> str:
    """The rules only Qodo review enforces, with their examples, as Markdown for the code-writing prompts.

    Raises ValueError when the file has no rules, a rule lacks a name or content, or an example is not
    text, so the agent never runs with a silently empty or partial rule list.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        raise ValueError(f"{path}: no rules")
    blocks = []
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"{path}: rule {i} is not an object")
        name, content = rule.get("name"), rule.get("content")
        if not isinstance(name, str) or not name.strip() or not isinstance(content, str) or not content.strip():
            raise ValueError(f"{path}: rule {i} has no name or content")
        block = [f"### {name.strip()}", "", " ".join(content.split())]
        for key, label in (("good_examples", "Meets the rule"), ("bad_examples", "Breaks the rule")):
            example = rule.get(key, "")
            if not isinstance(example, str):
                raise ValueError(f"{path}: rule {i} {key} is not text")
            if example.strip():
                block += ["", f"{label}:", "```", example.strip("\n"), "```"]
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def codex(cfg: dict, workdir: str, prompt: str, report: str, writable: bool, *, session: str | None = None) -> dict:
    """Run Codex once. With `session`, continue that conversation instead of starting a new one."""
    a = cfg["agent"]
    sandbox = "workspace-write" if writable else "read-only"
    if session:
        # `codex exec resume` takes neither -C nor -s: the directory comes from cwd, the sandbox from config.
        args = [cfg["tools"]["codex"], "exec", "resume", session, "-m", a["model"],
                "-c", f'model_reasoning_effort="{a["effort"]}"', "-c", f'sandbox_mode="{sandbox}"']
    else:
        args = [cfg["tools"]["codex"], "exec", "-C", workdir, "-m", a["model"],
                "-c", f'model_reasoning_effort="{a["effort"]}"', "-s", sandbox]
    args += ["--json", "--skip-git-repo-check", "-o", report, "-"]
    log = report + ".log"
    r = sh(args, cwd=workdir, stdin=prompt, timeout=a["timeoutMinutes"] * 60, log=log,
           env=godot_environment(cfg, workdir))
    text = Path(report).read_text(encoding="utf-8") if Path(report).exists() else ""
    return {"ok": r.ok, "code": r.code, "report": text, "log": log, "session": session or session_id(log)}


def session_id(log: str) -> str | None:
    """The thread id from a `codex exec --json` event log, or None if it never started."""
    try:
        lines = Path(log).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        if '"thread.started"' not in line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
            return event["thread_id"]
    return None


def failure_reason(out: dict) -> str:
    code = out["code"]
    return "Codex timed out (exit 124)" if code == 124 else f"Codex failed (exit {code})"


def parse_disputes(text: str | None, findings: list[dict]) -> list[tuple[str, str]]:
    ids = {str(f["id"]) for f in findings}
    disputes, bad = [], []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        finding_id, colon, evidence = line[2:].partition(":")
        if finding_id.startswith("`") and finding_id.endswith("`"):
            finding_id = finding_id[1:-1]
        if (line.startswith("- ") and colon and "`" not in finding_id and finding_id in ids
                and evidence.startswith(" ") and evidence.strip()):
            disputes.append((finding_id, evidence.strip()))
        else:
            bad.append(repr(line))
    if bad:
        raise ValueError("invalid lines in .factory-disagree.md: " + ", ".join(bad))
    return disputes


def parse_conflict_resolutions(report: str, paths: list[str]) -> dict[str, tuple[str, str]]:
    try:
        entries = json.loads(report)
    except json.JSONDecodeError as e:
        raise ValueError("Conflict resolution report must be a JSON array") from e
    if not isinstance(entries, list):
        raise ValueError("Conflict resolution report must be a JSON array")
    expected = set(paths)
    resolutions = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "action", "reason"}:
            raise ValueError("Each conflict resolution must contain path, action and reason")
        path, action, reason = entry["path"], entry["action"], entry["reason"]
        if not isinstance(path, str) or path not in expected or path in resolutions:
            raise ValueError(f"Unexpected or duplicate conflict path: {path!r}")
        if action not in ("keep", "delete") or not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"Conflict resolution for {path!r} requires a keep/delete action and a reason")
        resolutions[path] = (action, reason.strip())
    missing = sorted(expected - resolutions.keys())
    if missing:
        raise ValueError("Missing conflict resolutions: " + ", ".join(missing))
    return resolutions


def _items(lines: list[str] | None) -> list[str]:
    out = []
    for line in lines or []:
        s = line.strip().lstrip("-*").strip().strip("`").strip()
        if s and s.lower() not in ("none", "无", "n/a"):
            out.append(s)
    return out


def plan_checks(plan: str) -> list[str]:
    return _items(section(plan, ("checks",)))


def plan_questions(plan: str) -> list[str]:
    return _items(section(plan, ("questions",)))


def plan_complete(plan: str) -> list[str]:
    """Section headings the plan is missing."""
    need = ("fit", "reuse", "affected", "plan", "checks", "questions")
    return [h for h in need if section(plan, (h,)) is None]
