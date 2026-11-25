> Review replay for the Qodo hackathon, Day 12. Same commits as pull request 69 (base `7a9fa73`, head `22ee108`; identical diff). Do not merge; it will be closed after the review.

Closes #61

## Acceptance criteria
- [ ] 用连续不变、局部改变、风向或风速单独改变、尺寸变化及换局验证失效条件。未变时不再遍历全图生成风图，也不为判定相等新增一遍全图扫描。
- [ ] 与相同输入的改前版本逐字节对照风图和天气表，覆盖天气变化但风未变、风变化后再稳定的连续发布。过渡端点、日历和逐日结果保持一致。
- [ ] 在电脑的 50 倍速玩家窗口交替复测，列出未变/变化发布数、真正跳过的编码次数、标记维护成本和发布帧 P95。若整体表现稳定变差或标记成本抵消收益，记录数据并撤回该方案。

Qodo local review coverage was incomplete. See the factory run record for details.

## Factory
Plan, checks and reviews are in the run record `20261123-192914` and the issue comments. The verdict is computed from facts, not from this report.

`native_changed=false` · `native_rebuilt=false` · `native_runtime_ok=false`

<details><summary>Plan</summary>

## Fit

**已核实**

- 本票跨 **Climate** 和**地图显示**。桌面正式局的风场由后台 C++ 的 `RuntimeClimateAuthority` 持有，先在 `commit_day()` 安装气候结果，再由宿主在整日提交时发布只读快照。主线程取走同批最新快照和全部逐日记录，先写回 `MapData`，再交给渲染。当前气候提交在每日模块表之前。 [模块地图 29–31、58–60、127–132](/Users/herh/.keynes-factory/work/docs/architecture/module-map.md:29) · [运行现状 14–39、55–73](/Users/herh/.keynes-factory/work/docs/architecture/current-state.md:14) · [气候提交 450–479](/Users/herh/.keynes-factory/work/gdext/src/runtime_climate_authority.cpp:450) · [整日发布 816–859](/Users/herh/.keynes-factory/work/gdext/src/native_simulation_host_commands.cpp:816)
- `last_wind_day` 是最近一次**求风日期**。风向 X、Y 和风速在求风及散度修正完成后共用这个日期，显示快照已经携带它。同一来源和绑定内，日期相同可证明这三列沿用旧值。日期前进只能证明求过风，实际值仍可能相同。现有风轨迹指纹只抽样，可能漏掉局部改动。 [求风 184–203、254–257、292–340](/Users/herh/.keynes-factory/work/gdext/src/runtime_climate_kernel.cpp:254) · [快照复制 128–148](/Users/herh/.keynes-factory/work/gdext/src/runtime_climate_physics_state.cpp:128) · [轨迹指纹 1343–1363](/Users/herh/.keynes-factory/work/gdext/src/runtime_climate_pass_math.h:1343)
- 主线程目前对每份通过校验的物理快照复制三列风，再写入地图。当前分支 `7a9fa7373` 已合入 #60。即时上传和同帧合批都在 `_upload_weather_lut_pair()` 编码一次整张风图，天气表重排后写入目标层，云影和天气云共用按格编号排好的字节。云影的相同字节复用发生在编码之后。`weather_lut_update_usec` 在表和风字节准备好后发布，供显示过渡使用。 [写回 379–445、558–619、687–746](/Users/herh/.keynes-factory/work/gdext/src/world_ext_simulation_host_climate.cpp:379) · [天气发布 474–522、1090–1131](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/rendering/bakers/cell_lut_baker.gd:1090) · [风图消费与编码 27–92](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/rendering/weather_wind_source.gd:27)

**证据范围**。两张 12 格地图的留存试验各复制 3 次、复用 4 次，跳取第 0、3、4、6 日时各复制 3 次、复用 1 次，三列字节均一致。我也从 #60 留存的无窗口短样本数出 7 对相邻发布中有 5 对风图字节相同。票面 118/135 和此前跨日缓存的 P95 从 25.13 升至 35.15 ms 都是历史数据。当前桌面未变比例、标记成本和发布帧 P95 仍待实测。本次只读，未启动 Godot 或运行回归。 [小地图日志 19–33](/private/tmp/keynes-wind-mark.8uAw2n/transfer-run.log:19) · [#60 风图原始记录](/private/tmp/keynes-60.YvfpoO/raw-after.jsonl.wind) · [历史验证 34–74](/Users/herh/.keynes-factory/work/docs/architecture/feature-status.md:34)

## Reuse

- 沿用 `apply_runtime_climate_writeback()` 和 `flush_slots_to_map_keys()`。前者已拿到与本批匹配的物理快照，后者按实际写过的字段更新地图。把已写回的风标记随这条交接交给显示端，避免调用会复制整组物理数组的诊断视图。 [写回与诊断视图 170–199、558–589、695–765](/Users/herh/.keynes-factory/work/gdext/src/world_ext_simulation_host_climate.cpp:170)
- 保留 #60 的 `WorldData.publish_weather_wind()`、`published_weather_wind_bytes()` 和共用发布入口。沿用 `WeatherWindSource.build_bytes()` 的现有编码规则及独立预览路径。 [WorldData 311–328](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/geography/world_data.gd:311) · [风图编码 59–92](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/rendering/weather_wind_source.gd:59)
- 复用 `_cell_offset_layout()` 和 `weather_table_commit_plan()`。表的天气层为 0/1，配对风层为 2/3，翻转后旧当前层自然成为上一层。 [布局缓存 868–889](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/rendering/bakers/cell_lut_baker.gd:868) · [四层写入计划 46–105](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/rendering/bakers/weather_table_plan.gd:46)

## Affected

- **地图绑定和读档**。`bind_map_data()` 即使重绑同一对象也会重装数组。开局、读档、换图、重绑和风源切换都要清除复用资格。生成和兼容求风路径也能写三列风，应在这些路径使标记失效。 [地图绑定 597–717](/Users/herh/.keynes-factory/work/gdext/src/world_ext.cpp:597) · [读档重置 1619–1647](/Users/herh/.keynes-factory/work/gdext/src/world_ext_simulation_host_save.cpp:1619) · [兼容求风写回 628–642](/Users/herh/.keynes-factory/work/gdext/src/world_ext_physical.cpp:628)
- **存档和跨模块交付**。CLM2 内的物理状态已经保存 `last_wind_day`，也用它计算下次求风的时间跨度。新增记录只属于显示端，可在恢复时重建。沿既有 `RuntimeClimateSnapshot` 和写回绑定传递，Economy 继续从原有已提交视图读取气候。 [物理状态编码 89–109](/Users/herh/.keynes-factory/work/gdext/src/runtime_climate_physics_state.cpp:89) · [现有绑定 85–95](/Users/herh/.keynes-factory/work/gdext/src/world_ext_bind_runtime.cpp:85) · [经济读取字段 5–31](/Users/herh/.keynes-factory/work/gdext/src/runtime_climate_committed_view.cpp:5)
- **天气过渡**。`WeatherLayer` 按发布时间和层号刷新两个端点，云影关闭时仍为天气云供风。重点复用 `weather_table_layout_test.gd`、`cell_lut_incremental_test.gd`、`cloud_weather_quality_test.gd` 和 `render_data_tables_test.gd`。专项约束和实测结果分别记入 `feature-guides.md`、`feature-status.md`。 [天气端点 1327–1363](/Users/herh/.keynes-factory/work/Project/project-keynes/scripts/rendering/weather_layer.gd:1327) · [专项指南 404–438、770–779](/Users/herh/.keynes-factory/work/docs/architecture/feature-guides.md:404)

## Plan

1. 以合入 #60 的版本录改前数据。用正式玩家场景复现 60×40、种子 `20260718`、四国、50×。在诊断样本里逐字节核对三列风，统计实际未变比例、同日期能覆盖的比例，以及重新求风但字节仍相同的次数。把逐字节取证与计时分开。按开发指南保留仓库外的改前逐日参考。 [对照要求 191–205](/Users/herh/.keynes-factory/work/docs/architecture/development-guide.md:191)
2. 在主线程写回处比较**同一来源、同一地图及绑定上最后成功写回的风日期**。三列都通过校验并写回后才登记。命中时三列都跳过复制和地图写入，日历、其他字段和逐日回执继续交付。60×40 每次命中少复制 `2,400 × 3 × 4 = 28,800` 字节。先用现有日期衡量覆盖率，若需覆盖重算后完全相同的风，只考虑在现有最终写入中维护精确信息。
3. 在实际天气上传点，用与取风数组对应的标记、地图和尺寸复用 #60 的编码结果。同帧合批按实际上传时取到的风判断。天气仍由原有天气字节决定何时发布，发布发生时正常推进时间戳和端点。有效风版本相同就直接取已有字节，缺失或失效则走现有编码路径。
4. 天气表先确定目标层和布局，再判断该风层是否已有同版风。有则跳过该层重排、建图和上传，天气层照常写入并翻转。`A→B→B→B` 中，第一次重复 B 补写还存 A 的层。首次建表、布局变化、重建和失败恢复时填齐所需层，完成上传后才登记版本。
5. 对拍连续相同、单格变化、仅风向或仅风速变化、天气变而风不变、换尺寸、换局、读档、重绑、换风源和失败恢复。覆盖即时上传和合批，逐字节比较风数组、风图、天气表四层及每次过渡两端，并核对日历、逐日结果和回执。工厂在电脑真实图形环境执行天气表回读和端点检查。
6. 复用 `player_scene_handoff_probe.gd` 与 `tools/perf/analyze_player_handoff.py`，在真实玩家窗口按改前/改后、改后/改前交替测 50×。固定实际桌面设置和镜头，取双方均采到的结算日区间。逐轮列出风未变/变化发布数、实际复制/编码/风层上传及跳过次数、标记维护成本、发布帧 P95 和绘制间隔。以 #60 的每次发布一次编码为基线算额外收益。整体稳定变慢或标记成本抵消收益时，记录数据并撤回。 [桌面取样要求 120–140](/Users/herh/.keynes-factory/work/docs/architecture/feature-status.md:120)

## Checks

- `tools/ci/check_golden_determinism.py --runs 3`
- `tools/ci/check_golden_determinism.py --runs 3 --external-only`
- `tools/ci/run_regression_checks.py tests/world/weather_table_layout_test.gd`
- `tools/ci/run_regression_checks.py tests/runtime/runtime_climate_c5_scenarios_test.gd`
- `tools/ci/run_regression_checks.py tests/game/player_calendar_handoff_test.gd`

## Questions

none

</details>

<details><summary>Agent report</summary>

**#61 候选实现已撤回。** 三轮 50 倍速无窗口复测中，发布帧 P95 均下降，全部帧 P95 分别从 37.38、35.22、33.48 ms 升至 38.20、42.39、42.78 ms。九个共同结算区间均出现退化，因此保守撤回。工作树仅保留[验证记录](/Users/herh/.keynes-factory/work/docs/architecture/feature-status.md:6)。

- 候选沿用求风日期，三轮分别跳过 92、73、82 次三数组写回和整图编码，以及 81、63、72 次风层上传。标记维护中位约为写回 10 μs、发布 21–23 μs。[候选补丁与测试](/private/tmp/keynes-61.DqknPB/issue-61-candidate.patch)
- 九次固定输入对拍中，风图、天气表四层的写入字节和过渡端点一致。存读档、同图重绑、日历交接及两组各三次黄金回放通过。第 1–180 日结果和回执一致。撤回后，天气表、气候 C5 和日历交接复测通过。
- macOS 图形服务连接失败，桌面工具未获访问 Godot 的批准。真实窗口帧时间和图形回读仍待验收。Qodo 未登录，评审未完成。



</details>

Implemented-By: Codex (gpt-6.2-sol)
