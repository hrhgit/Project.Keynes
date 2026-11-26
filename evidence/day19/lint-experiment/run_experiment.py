"""Re-run the Day 19 lint experiment: does guard_scan.py catch the fail-loudly findings, and how noisy is it?

Usage: python3 run_experiment.py <keynes repo> <findings dir with ext<PR>.json>
For each inspected finding: scan the cited .gd file at the finding's commit and report whether a flag lies
within 3 lines of the finding's location. For each PR: count flags that fall on lines the PR added.
"""
import json, re, subprocess, sys
from pathlib import Path

REPO, FIND = sys.argv[1], Path(sys.argv[2])
SCAN = Path(__file__).with_name("guard_scan.py")
FINDINGS = {74: "41b96796", 88: "665d91a0", 59: "162dd0f5", 38: "82a5d2c1", 52: "452b8e7e", 73: "963d6938", 36: "bb5fed6b"}

def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, check=True).stdout

def scan(text):
    out = subprocess.run([sys.executable, "-I", str(SCAN)], input=text, capture_output=True, text=True, check=True).stdout
    return [int(x) for x in out.split()]

def load(pr):
    t = (FIND / f"ext{pr}.json").read_text()
    return json.JSONDecoder().raw_decode(t)[0]

print("== Finding locations (flag within 3 lines?)")
for pr, fid in FINDINGS.items():
    f = next(x for x in load(pr)["findings"] if x["id"].startswith(fid))
    loc = f["location"]; path = loc["file_path"]
    if not path.endswith(".gd"):
        print(f"PR {pr} {fid} {path}: not GDScript, skipped"); continue
    hits = scan(git("show", f"{f['git_sha']}:{path}"))
    near = [h for h in hits if abs(h - loc["start_line"]) <= 3 or loc["start_line"] <= h <= loc["end_line"]]
    print(f"PR {pr} {fid} {path}:{loc['start_line']} -> {'HIT ' + str(near) if near else 'MISS'}  ({f['title']})")

print("\n== Flags on lines each PR added, at the commit Qodo reviewed (matched = within 3 lines of a fail-loudly finding)")
RULE = "4948321"
def fail_loudly(f):
    return f["id"].startswith("665d91a0") or RULE in json.dumps(f.get("evidence", {}))
for pr in sorted(FINDINGS):
    data = load(pr)
    sha = next(x for x in data["findings"] if x["id"].startswith(FINDINGS[pr]))["git_sha"]
    info = json.loads(subprocess.run(["gh", "pr", "view", str(pr), "--repo", "hrhgit/Project.Keynes", "--json",
                                      "headRefOid,mergeCommit"], capture_output=True, text=True, check=True).stdout)
    base = git("merge-base", info["mergeCommit"]["oid"] + "^1", sha).strip()
    targets = [(x["location"]["file_path"], x["location"]["start_line"]) for x in data["findings"]
               if x["git_sha"] == sha and fail_loudly(x) and x.get("location")]
    diff = git("diff", "-U0", base, sha, "--", "*.gd")
    added, path = {}, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
        if m and path:
            start, n = int(m.group(1)), int(m.group(2) or 1)
            added.setdefault(path, set()).update(range(start, start + n))
    total, matched, where = 0, 0, []
    for p_, lines in sorted(added.items()):
        for h in [h for h in scan(git("show", f"{sha}:{p_}")) if h in lines]:
            hit = any(tp == p_ and abs(tl - h) <= 3 for tp, tl in targets)
            total += 1; matched += hit
            where.append(f"{p_}:{h}{'  <- Qodo fail-loudly finding' if hit else ''}")
    print(f"PR {pr} ({base[:9]}..{sha[:9]}): {total} flags on added lines, {matched} matched; "
          f"{len(targets)} fail-loudly findings at this commit")
    for w in where: print("   ", w)
