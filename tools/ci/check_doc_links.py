#!/usr/bin/env python3
"""Ratchet for relative links in the tracked Markdown under ``docs/``.

A relative link is dead when its target (with any ``#anchor`` dropped) is not a
tracked file or a directory holding one. Links with a scheme (``https:``,
``mailto:`` ...) and same-page ``#anchor`` links are not checked; a link that
starts with ``/`` is resolved from the repository root, as GitHub does. Links
inside fenced code blocks are ignored.

Existing dead links are frozen in ``doc_links_baseline.json`` as
``"<file> -> <target>": count``. The check fails when

- a dead link appears that is not in the baseline, or a file gains another copy
  of a baselined one (new dead link);
- a baselined entry has fewer dead copies than recorded (fixed or removed:
  run ``--write-baseline`` to tighten it).

``--write-baseline`` refuses to write a baseline that is looser than the
current one; with no baseline file it records the current dead links.
"""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "tools/ci/doc_links_baseline.json"
INLINE = re.compile(r"\]\(\s*<?([^)\s>]+)>?")
REFERENCE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def link_targets(text: str) -> list[tuple[int, str]]:
    """(line, target) for every inline or reference-style link outside fenced code."""
    found: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), 1):
        opened = FENCE.match(line)
        if opened:
            marker = opened.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        found.extend((number, m.group(1)) for m in INLINE.finditer(line))
        ref = REFERENCE.match(line)
        if ref:
            found.append((number, ref.group(1)))
    return found


def resolve(source: str, target: str) -> str | None:
    """Repository path the link points at, or None when the link is not a checked relative link."""
    if SCHEME.match(target) or target.startswith("#"):
        return None
    path = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not path:
        return None
    joined = path.lstrip("/") if path.startswith("/") else posixpath.join(posixpath.dirname(source), path)
    return posixpath.normpath(joined)


def doc_sources(files: list[str]) -> list[str]:
    return sorted(p for p in files if p.startswith("docs/") and p.endswith(".md"))


def missing_sources(root: Path, files: list[str]) -> list[str]:
    """Tracked docs/ Markdown absent from the work tree (e.g. left out of a sparse checkout)."""
    return [p for p in doc_sources(files) if not (root / p).is_file()]


def dead_links(root: Path, files: list[str]) -> list[tuple[str, int, str]]:
    """(file, line, target) for every dead relative link in the tracked docs/ Markdown."""
    tracked = set(files)
    known = {"."}  # every directory that holds a tracked file, at any depth
    for p in tracked:
        d = posixpath.dirname(p)
        while d and d not in known:
            known.add(d)
            d = posixpath.dirname(d)
    dead: list[tuple[str, int, str]] = []
    for source in doc_sources(files):
        path = root / source
        if not path.is_file():
            continue
        for line, target in link_targets(path.read_text(encoding="utf-8", errors="replace")):
            resolved = resolve(source, target)
            if resolved is None:
                continue
            if resolved.startswith("../") or resolved == ".." or (resolved not in tracked and resolved not in known):
                dead.append((source, line, target))
    return dead


def key(source: str, target: str) -> str:
    return f"{source} -> {target}"


def compare(dead: list[tuple[str, int, str]], baseline: dict[str, int]) -> tuple[list[str], list[str]]:
    """(new dead links, baseline entries that can be tightened)."""
    counts = Counter(key(s, t) for s, _, t in dead)
    new = []
    for source, line, target in dead:
        k = key(source, target)
        if counts[k] > baseline.get(k, 0):
            new.append(f"{source}:{line}: dead link {target}")
    stale = [f"{k}: baseline {n}, now {counts.get(k, 0)}" for k, n in sorted(baseline.items()) if counts.get(k, 0) < n]
    return new, stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write-baseline", action="store_true", help="tighten the baseline to the current dead links")
    args = parser.parse_args(argv)
    baseline_path = ROOT / BASELINE
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
    files = tracked_files(ROOT)
    missing = missing_sources(ROOT, files)
    if missing:
        # Their links would go unchecked and their baseline entries would look fixed.
        print(f"::error::{len(missing)} tracked docs/ Markdown files are not in the work tree, e.g. {missing[0]}; "
              "check out all of docs/**/*.md")
        return 1
    dead = dead_links(ROOT, files)
    new, stale = compare(dead, baseline)
    if args.write_baseline:
        if new and baseline_path.exists():
            print("refusing to write a looser baseline; fix these links first:", *new, sep="\n  ", file=sys.stderr)
            return 1
        current = dict(sorted(Counter(key(s, t) for s, _, t in dead).items()))
        if current != baseline:
            baseline_path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
        print(f"baseline holds {sum(current.values())} dead links")
        return 0
    for problem in new:
        source, line, _ = problem.split(":", 2)
        print(f"::error file={source},line={line}::{problem}")
    for entry in stale:
        print(f"stale baseline entry (run --write-baseline): {entry}")
    if new or stale:
        return 1
    print(f"doc links ok; {sum(baseline.values())} known dead links remain in the baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
