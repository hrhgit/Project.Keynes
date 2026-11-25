#!/bin/bash
set -euo pipefail

run_dir="$(cd "$(dirname "$0")" && pwd)"
source_repo=/Users/herh/MyFiles/games/keynes-wt-day13
source_build=/Users/herh/.keynes-perf/build
cache_commit=5b69be27c2673a8ba165fb6f75663b15021e7b51
submodule_commit=9e0650a0ae806367854d50342c4751690a09d521

export GIT_ALLOW_PROTOCOL=file
mkdir -p "$run_dir/perf" "$run_dir/user-home" "$run_dir/tmp"
git clone --shared --no-checkout "$source_repo" "$run_dir/repo"
git -C "$run_dir/repo" worktree add --detach --no-checkout "$run_dir/perf/build" "$cache_commit"
cp -cpR "$source_build" "$run_dir/warm-build"
mv "$run_dir/warm-build/.git" "$run_dir/old-build-git-pointer"
mv "$run_dir/perf/build/.git" "$run_dir/warm-build/.git"
rmdir "$run_dir/perf/build"
mv "$run_dir/warm-build" "$run_dir/perf/build"
git -C "$run_dir/perf/build" reset --mixed HEAD

local_submodule="$run_dir/perf/build/gdext/godot-cpp"
mv "$local_submodule/.git" "$run_dir/old-submodule-git-pointer"
git clone --shared --no-checkout "$source_build/gdext/godot-cpp" "$run_dir/submodule-git"
mv "$run_dir/submodule-git/.git" "$local_submodule/.git"
rmdir "$run_dir/submodule-git"
git -C "$local_submodule" reset --mixed "$submodule_commit"
git -C "$local_submodule" rev-parse --absolute-git-dir HEAD
git -C "$run_dir/perf/build" rev-parse --absolute-git-dir HEAD
git -C "$run_dir/repo" cat-file -t 9ddb127342622cc1230b4690d2ea07b96e2c7be7
git -C "$run_dir/repo" cat-file -t ec9a22ce2ec349504c474fef3099f01c8b79d3c0
