Please do step 3 now, which you skipped, and then reply **in English**, same reply format.

Reproduction, writing only inside your working directory:
1. `git -C ~/MyFiles/games/keynes archive b05f8fc9e | tar -x -C full/` (create `full/` first) to get the full tree of the failed commit.
2. Build `sparse/` containing only the paths the `architecture-guards` job checks out at `b05f8fc9e` (copy the matching paths from `full/`; the list is in `.github/workflows/runtime-checks.yml` at that commit).
3. In `sparse/` run `python3 -m unittest discover -s tools/perf/tests -v`; in `full/` run the same. Report exit codes and the last lines of output.
4. Then copy `sparse/` to `sparse-fixed/`, add `tools/perf/` from `full/` (simulating your proposed diff), and run the same command there.
Do not read commits after `b05f8fc9e`.
