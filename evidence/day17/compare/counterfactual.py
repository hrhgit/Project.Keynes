"""Re-judge the two archived records with and without the recorder-method refusal (PR 85, tools/perf/perf_change_check.py:1052-1069).

Usage: python3 -I counterfactual.py <pcc_merged.py> <base record.json> <head record.json>
The 'without' run treats both sides as the same method, which is what the tool did before PR 85.
"""
import copy, importlib.util, json, sys
spec = importlib.util.spec_from_file_location("pcc", sys.argv[1]); pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
base, head = (json.load(open(p)) for p in sys.argv[2:4])
print("methods: base", sorted({r.get("recorder_method") for r in base["rounds"]}), "head", sorted({r.get("recorder_method") for r in head["rounds"]}))
for label, b, h in (("with the refusal (as merged)", base, head), ("without it (same method assumed)", None, None)):
    if b is None:
        b, h = copy.deepcopy(base), copy.deepcopy(head)
        for r in b["rounds"] + h["rounds"]:
            r["recorder_method"] = "same"
    v = pc.assess(b, h, [], pc.NOISE, "counterfactual")
    print(f"== {label}: status={v['status']} rows={len(v['rows'])}")
    for reason in v["reasons"]: print("  reason:", reason)
    for row in v["rows"]:
        if row.get("metric") in pc.HEADLINE:
            print("  ", json.dumps({k: row.get(k) for k in ("metric", "base", "head", "change", "verdict", "significant") if k in row}))
