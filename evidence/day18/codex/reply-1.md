### Diagnosis

**日志显示：**静态架构检查没有报错，Factory tests 的 211 个测试通过；失败发生在随后运行 `python -m unittest discover -s tools/perf/tests -v` 时，Python 报目录不可导入。**我的推断：**最符合证据的是 **(b) 工作流检出内容不包含这些测试文件**。该 job 的 sparse-checkout 清单没有包含 `tools/perf/`，但它仍运行 `tools/perf/tests` 下的测试。证据不支持代码本身坏了，也没有迹象表明这是临时 runner 问题。

### Evidence

在 `b05f8fc9e` 的 [.github/workflows/runtime-checks.yml](<~/MyFiles/games/keynes/.github/workflows/runtime-checks.yml:19>) 中，`architecture-guards` 的 sparse-checkout 清单从第 19 行开始列出检出路径；清单没有 `tools/perf/`。同一 job 在第 52 行运行性能测试命令。

`git ls-tree b05f8fc9e -- tools/perf` 显示该提交**确实有** `tools/perf/` 目录。递归树中包含 `tools/perf/tests/test_analyze_player_handoff.py` 和 `tools/perf/tests/test_perf_change_check.py`。因此，测试文件存在于提交树中，但不在该 job 请求检出的路径中。

**本次运行的命令和结果：**

- `git -C ~/MyFiles/games/keynes show b05f8fc9e:.github/workflows/runtime-checks.yml`：读取了失败提交中的工作流配置；稀疏检出路径未列出 `tools/perf/`，测试步骤却执行 `python -m unittest discover -s tools/perf/tests -v`。
- `git -C ~/MyFiles/games/keynes ls-tree b05f8fc9e -- tools/perf` 以及 `git -C ~/MyFiles/games/keynes ls-tree -r b05f8fc9e -- tools/perf`：确认性能目录及两个测试文件存在于该提交中。
- `git -C ~/MyFiles/games/keynes show b05f8fc9e:tools/perf/tests/test_perf_change_check.py` 和对另一个测试文件的相同读取：确认测试文件内容存在于提交树。

我没有导出树或运行本地复现，因此没有本地复现输出。日志里的 ImportError 与“检出范围缺少目标测试目录”一致，但我没有在本机验证该命令在稀疏和完整检出下的实际结果。

### CI 摘要应提及

本次失败是 `architecture-guards` job 的性能工具测试步骤因测试目录不可导入而失败；之前静态架构检查没有报告 guard 错误，Factory 的 211 个测试通过。Qodo 没有生成 CI 摘要：给出的回复说明 `/checks` 已弃用，因此没有可比较的 Qodo 结论。

### Proposed change

**建议将 `tools/perf/` 加入 `architecture-guards` job 的 sparse-checkout 清单。**在现有列表中加入一行：

```diff
             /tools/factory/
+            /tools/perf/
             /gdext/src/
```

确认检查：用包含此路径的检出运行同一条命令 `python -m unittest discover -s tools/perf/tests -v`，确认测试被发现并完成。

### 未检查

未访问 GitHub、未检查或推断之后的提交、未运行 CI 或本地复现，也未核查除这个失败原因以外的 workflow 行为。

