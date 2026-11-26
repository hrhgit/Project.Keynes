### Diagnosis

**What the log shows:** the performance test step failed because Python could not import `tools/perf/tests`; the prior Factory tests passed. **What I infer:** the job’s sparse checkout omitted the directory that the later test step requires. The reproduction supports that inference: the command fails in the sparse tree, passes in the full tree, and passes after adding `tools/perf/` to the sparse tree. That supports workflow checkout configuration as the cause, not broken tests or a transient runner issue.

### Evidence

I exported `b05f8fc9e` into `full/` and built `sparse/` from the `architecture-guards` checkout paths listed in `.github/workflows/runtime-checks.yml` at that commit. I did not read later commits.

The workflow’s checkout list does not include `tools/perf/`, while its Performance tool tests step runs `python -m unittest discover -s tools/perf/tests -v`. The failed commit’s tree contains that directory and its tests.

From the scratch directory, I ran the same command separately inside each export:

- `sparse/`: exit code **1**; final error: `ImportError: Start directory is not importable: 'tools/perf/tests'`.
- `full/`: exit code **0**; final lines: `Ran 88 tests in 0.153s` and `OK`.
- `sparse-fixed/`, made by adding `tools/perf/` from `full/` to `sparse/`: exit code **0**; final lines: `Ran 88 tests in 0.153s` and `OK`.

There was an initial set of runs from the scratch root rather than each export directory; those results were invalid. The results above are the corrected runs from the intended directories.

### Anything the CI summary should mention

The `architecture-guards` job failed in the Performance tool tests step because its sparse checkout did not include the tests that step ran. Static architecture guards reported no errors, and Factory tests passed. The provided Qodo reply says `/checks` was deprecated, so there is no Qodo CI summary to compare.

### Proposed change

Add `tools/perf/` to the `architecture-guards` job’s sparse-checkout list:

```diff
             /tools/factory/
+            /tools/perf/
             /gdext/src/
```

The confirming check is the same unittest discovery command in that job’s checkout. In this reproduction, adding that path resulted in all 88 tests passing.

### What I did not check

I did not access GitHub, inspect later commits, modify the repository, or run CI. I did not investigate any other cause or any other failed job.

