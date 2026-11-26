You are implementing a ticket for Project Keynes. Follow `AGENTS.md` and the architecture docs it points to.

Ticket #83: 分开读取界面和地图数据，忙帧跳过地图专用数据复制

## 目标

让 UI 按现有节奏读取后台已发布的结果，让地图按当前帧的负担独立决定何时取数。地图积压时，玩家仍能及时收到操作反馈；恢复时一次补齐期间的变化。

#63 已经可以推迟地图贴图更新，#74 分开了前台领取、普通面板刷新和地图绘制。仍可在 `DCWorldExt::poll_runtime_commit` 看到：领取日记录和命令回执的同一次调用，会复制供地图贴图使用的整图数组 `transition_age` 和 `previous_vitality`。请从这里追到实际使用方，在复制或转换地图专用数据前做出是否读取的决定。UI 和地图均从后台已发布的结果读取。共用字段按实际使用方处理。

## 验收标准

- [ ] 先在正式玩家场景记录改前的读取路径，写出复现条件和根因证据。增加能区分「读取地图数据」和「绘制地图」的检查。连续推迟地图更新时，按原有领取节奏交付每日记录、命令回执和等待玩家处理的事件；该期间为地图贴图复制上述两组数组的次数为零。后台继续推进到正常的玩家等待点。
- [ ] 覆盖连续积压多天且不同地块分别变化的情形。恢复时取最近一次完整发布，包含上次地图更新以来的全部变格，与同一天持续更新的地图对照一致。检查画面落后时点击地块的视野与详情，以及暂停时恢复、读档或换局时清掉旧数据。
- [ ] 相同种子和命令下，正常读取与推迟地图读取的逐日结果、命令生效日及回执顺序一致。覆盖已有的普通面板刷新和地图绘制开关，保持原有语义。
- [ ] 用可见的正式玩家窗口在同一场景、帧率档、画质和倍速下交替测改前改后，覆盖正常与繁忙两种情况。给出地图取数次数、复制字节与耗时、面板点击到反馈的时间、实际绘制间隔、后台天数/秒和地图落后天数，附样本量及复现方法。按实测说明操作反馈是否改善。

## 参考

沿用现有帧率设置及忙帧判断。可从 `world_runtime_daily_adapter_part3.gd`、`world_runtime_presentation.gd` 和 `independent_presentation_window_test.gd` 追踪。保留已有断言，按根因修复。

相关工作：[忙时推迟贴图更新](https://github.com/hrhgit/Project.Keynes/issues/63) · [前台领取、界面刷新和地图绘制的独立控制](https://github.com/hrhgit/Project.Keynes/pull/74)。


Acceptance criteria:
- 先在正式玩家场景记录改前的读取路径，写出复现条件和根因证据。增加能区分「读取地图数据」和「绘制地图」的检查。连续推迟地图更新时，按原有领取节奏交付每日记录、命令回执和等待玩家处理的事件；该期间为地图贴图复制上述两组数组的次数为零。后台继续推进到正常的玩家等待点。
- 覆盖连续积压多天且不同地块分别变化的情形。恢复时取最近一次完整发布，包含上次地图更新以来的全部变格，与同一天持续更新的地图对照一致。检查画面落后时点击地块的视野与详情，以及暂停时恢复、读档或换局时清掉旧数据。
- 相同种子和命令下，正常读取与推迟地图读取的逐日结果、命令生效日及回执顺序一致。覆盖已有的普通面板刷新和地图绘制开关，保持原有语义。
- 用可见的正式玩家窗口在同一场景、帧率档、画质和倍速下交替测改前改后，覆盖正常与繁忙两种情况。给出地图取数次数、复制字节与耗时、面板点击到反馈的时间、实际绘制间隔、后台天数/秒和地图落后天数，附样本量及复现方法。按实测说明操作反馈是否改善。

The investigation plan (from a read-only pass over the code):

## Fit

**已核实。** #83 归「会话、存读档、玩家输入」模块的结果领取与显示交接，地图和界面是下游读者。两组数组由 `NativeSimulationHost` 在正式桌面会话的后台线程上生成，保存在 `RuntimeDayTail.cell_luts`。每日结算完成后，`publish_day()` 先发布带日期和编号的提交，再发布可供前台领取的批次。内联执行器沿用同一个发布函数。[module-map.md，50–60 行](~/.keynes-factory/work/docs/architecture/module-map.md:50) · [current-state.md，55–79 行](~/.keynes-factory/work/docs/architecture/current-state.md:55) · [native_simulation_host_commands.cpp，807–859 行](~/.keynes-factory/work/gdext/src/native_simulation_host_commands.cpp:807) · [native_simulation_host_day_tail.cpp，231–285 行](~/.keynes-factory/work/gdext/src/native_simulation_host_day_tail.cpp:231)

**根因。** 主线程默认每个处理帧检查领取时间，也支持固定间隔。`world_runtime_daily_adapter_part3.gd` 调用 `poll_runtime_commit(..., true)` 时，只要领到含生态过渡数据的批次，C++ 就为 `transition_age` 和 `previous_vitality` 各分配一个字节数组并执行 `memcpy`。适配器之后才交付逐日记录、回执和待答事项，再排入地图更新。直到 `apply_pending_worker_map()` 才判断本帧是否有余量。因此即便本帧推迟贴图，复制也已经发生。领取还推进后台快进所用的八日窗口，地图积压期间必须继续领取。[world_runtime_daily_adapter_part1.gd，137–150 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_daily_adapter_part1.gd:137) · [world_runtime_daily_adapter_part3.gd，36–70、119–147 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_daily_adapter_part3.gd:36) · [world_ext_simulation_host.cpp，1324–1414 行](~/.keynes-factory/work/gdext/src/world_ext_simulation_host.cpp:1324) · [world_runtime_presentation.gd，76–92 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_presentation.gd:76) · [native_simulation_host_day_tail.cpp，204–217 行](~/.keynes-factory/work/gdext/src/native_simulation_host_day_tail.cpp:204) · [native_simulation_host_environment.cpp，55–70 行](~/.keynes-factory/work/gdext/src/native_simulation_host_environment.cpp:55)

**实际使用方。** 两组数组经 `publish_worker_climate_visuals()` 进入 `CellLutBaker`，由 C++ 编码器或 GDScript 路径生成生态贴图。`display_dirty_cells` 用于地图更新范围。`display_class_cells` 是共用字段，还负责把地形、地貌、植被和覆盖分类写进界面会读取的地块对象。气候和视野的已发布副本也有共用读者。[mapgen_native_daily_runtime.gd，61–67 行](~/.keynes-factory/work/Project/project-keynes/scripts/simulation/climate/mapgen_native_daily_runtime.gd:61) · [cell_lut_baker.gd，310–389、539–580 行](~/.keynes-factory/work/Project/project-keynes/scripts/rendering/bakers/cell_lut_baker.gd:310) · [world_ext_cell_luts.cpp，400–425 行](~/.keynes-factory/work/gdext/src/world_ext_cell_luts.cpp:400) · [world_runtime_daily_adapter_part3.gd，14–33、187–197 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_daily_adapter_part3.gd:187) · [cell_inspector_view_model.gd，249–270 行](~/.keynes-factory/work/Project/project-keynes/scripts/ui/cell_inspector_view_model.gd:249)

**待实测。** 按源码推算，60×40 格地图每次成功复制这两列共 4,800 字节。本次只读核查基于 `c81ebf871`。现有 #63 记录测的是整次领取和后续贴图处理，本票的复制频次、耗时及点击反馈仍需在正式窗口采样。[feature-status.md，63–87 行](~/.keynes-factory/work/docs/architecture/feature-status.md:63)

## Reuse

- 继续用 `RuntimePublicationReader.due()` 管理原有领取间隔。地图沿用 `WorldRuntimeMapUpdates.can_apply()` 的实际帧率、剩余帧时间和恢复节奏，以及现有变格合并、整图标记和失败恢复规则。[runtime_publication_reader.gd](~/.keynes-factory/work/Project/project-keynes/scripts/game/runtime_publication_reader.gd) · [world_runtime_map_updates.gd，27–65、76–138 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_map_updates.gd:27)
- 复用洋流显示的做法，先用轻量信息判断是否需要更新，到期才取已发布数组，并核对地图、格数和提交身份。[ocean_currents_job.gd，1132–1175 行](~/.keynes-factory/work/Project/project-keynes/scripts/simulation/sus/jobs/ocean_currents_job.gd:1132) · [feature-guides.md，612–647 行](~/.keynes-factory/work/docs/architecture/feature-guides.md:612)
- 复用 `MapDrawnFrame` 的日期、镜头和视野记录，以及实际出图后刷新地块详情的入口。沿用 `player_scene_handoff_probe.gd` 和配对运行脚本采集正式窗口数据。[map_drawn_frame.gd，17–75 行](~/.keynes-factory/work/Project/project-keynes/scripts/rendering/map_drawn_frame.gd:17) · [selected_cell.gd，39–56、90–100 行](~/.keynes-factory/work/Project/project-keynes/scripts/ui/game_ui/selected_cell.gd:39) · [player_scene_handoff_probe.gd，270–362 行](~/.keynes-factory/work/Project/project-keynes/tests/game/player_scene_handoff_probe.gd:270) · [run_rendered_player_handoff.py，174–223 行](~/.keynes-factory/work/tools/perf/run_rendered_player_handoff.py:174)

## Affected

- **原生绑定与已发布视图。** 地图读取走 `MapRuntimeBridge` 和 `runtime` 绑定。新增方法时同步 `world_ext.h`、`world_ext_bind_runtime.cpp` 和方法清单。`finish_runtime_display_frame()` 会清除本次领取时固定的提交，待显示地图需要独立保留其只读引用。气候、视野、资源、物种、Country 和 Modifier 继续沿现有已发布视图安装。读档用的 `poll_runtime_commit(0, false)` 仍可读取提交头。[world_ext_binding_modules.json，10–19、87–101 行](~/.keynes-factory/work/tools/ci/world_ext_binding_modules.json:10) · [world_runtime_generation_adapter.gd，206–215 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_generation_adapter.gd:206)
- **地图与界面。** `draw_enabled` 管实际出图，`ui_refresh_enabled` 管普通面板刷新。视野变化仍优先提交贴图，并随同一次绘制更新边界、建筑情报和标签。点击跟随最后画出的镜头和视野，详情等对应画面出图。相关回归是 `independent_presentation_test.gd`、`simulation_presentation_coalescing_test.gd`、`cell_lut_incremental_test.gd` 和正式窗口用例。[player_map_viewport.gd，51–123 行](~/.keynes-factory/work/Project/project-keynes/scripts/rendering/player_map_viewport.gd:51) · [world_runtime_presentation.gd，49–67 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_presentation.gd:49) · [independent_presentation_window_test.gd，68–145 行](~/.keynes-factory/work/Project/project-keynes/tests/game/independent_presentation_window_test.gd:68)
- **会话与存档。** 待显示引用、变格和读取进度属于本局显示状态。沿用 PKSV、PKSR、CLM2 和视野存档契约，以及保存前的环境和视野同步。读档、换局和关闭走现有清理入口。同局重启要保留积压，现有用例覆盖发布编号回落。实施时沿用会话、玩家控制器、运行时架构和性能复测技能，并把交付行为和实测结果分别写入 `feature-guides.md` 和 `feature-status.md`。[game_save_coordinator.gd，375–403 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/game_save_coordinator.gd:375) · [world_runtime_lifecycle.gd，59–92 行](~/.keynes-factory/work/Project/project-keynes/scripts/game/world_runtime_lifecycle.gd:59) · [simulation_presentation_coalescing_test.gd，226–236 行](~/.keynes-factory/work/Project/project-keynes/tests/runtime/simulation_presentation_coalescing_test.gd:226)

## Plan

1. **先取改前证据。** 用 `GameFlow` 启动正式玩家窗口，复用种子 `20260718`、60×40、四国和现有 `--overload` 场景。在实际分配及复制处记录两列的次数、字节和耗时，同时记录领取、贴图提交和实际出图。保存一段连续忙帧记录，证明期间领取在继续、贴图在推迟、数组仍在复制。另存改前的逐日对照数据。
2. **把地图取数放到忙帧判断之后。** 原领取入口继续交付逐日记录、回执、待答事项和共用字段。地图积压期间只保留最近完整发布的只读引用及累计变格标记。通过现有帧预算判断后，才复制和转换地图专用数据。取数时核对会话、地图、日期、编号和格数，确保生态数组与已安装的气候、视野和分类属于对应的发布。
3. **恢复时只应用一次最新结果。** 合并上次成功提交贴图以来的普通变格、分类变格及整图标记。只有成功提交贴图才清除积压，失败沿用同日整图恢复。覆盖至少两天分别改变不同地块，并与每天更新、停在同一天的地图比较贴图字节。保留视野变化的同帧优先规则，单独验证揭雾和保存同步。
4. **验证领取与出图仍各自有效。** 在正式场景连续推迟地图取数，让期间既有命令结算又到达玩家待答点。断言两列实际复制次数为零，逐日结果、命令生效日和回执顺序与正常读取一致。保留原断言，覆盖两个开关、落后时点击、暂停当天恢复、同局重启、读档和换局。直接以可见窗口运行 `independent_presentation_window_test.gd`。
5. **交替测改前改后。** 固定地图、镜头、实际帧率档、画质、倍速和操作顺序，正常与繁忙各做至少三组配对。记录地图取数次数、复制字节和耗时、面板点击到首个可见反馈帧的时间、实际绘制间隔、后台天数/秒及后台提交日与已画地图日的差值。报告样本量、中位数、P95、范围和复现命令，据实判断反馈是否改善。

## Checks

`tools/ci/check_golden_determinism.py --runs 3`  
`tools/ci/check_golden_determinism.py --runs 3 --external-only`  
`tools/ci/run_regression_checks.py tests/world/weather_table_layout_test.gd`  
`tools/ci/run_regression_checks.py tests/game/game_settings_service_test.gd`

## Questions

none

Rules for this run:
- Change only what the ticket and plan need. Leave `.github/`, `tools/factory/`, `tools/ci/`, `.qodo/`, `gdext/godot-cpp/` and `gdext/rebuild.sh` to a person.
- Leave changes under `Project/project-keynes/addons/dots_ext/bin/` to a person. The factory builds and checks the macOS libraries locally when native source changes.
- Do not commit, branch, push or stash. Leave all changes in the working tree; the factory commits them.
- Find the root cause before changing code. Do not loosen assertions, lengthen timeouts, add retries, add days or change hashes to make a check pass.
- Add or update tests that prove each acceptance criterion.
- If a person must decide something before you can continue, write the question to `.factory-question.md` in the repository root and stop.

Qodo reviews the pull request against these project rules (`docs/factory/qodo-rules.json`). No static check enforces them, so write the change to meet them from the start:

- **Keynes: simulation results must not depend on timing or load** Check that production, consumption, price updates, planning cadence and command effective dates are decided only by the seed, content version, sealed command log and game day. Wall-clock time, frame rate, thread wake-ups, slice budgets or machine load may change when work finishes, never what it produces.
- **Keynes: the front end only reads published frames** Code under scripts/ui and scripts/rendering may read only the published, committed frame and forward player requests to the simulation. It must not read live simulation state to make decisions and must not write simulation state; the simulation decides where it stops to wait for the player.
- **Keynes: cross-module hand-offs go through committed views or intents** A module reads another module only through the owner's committed view (copy_committed_view / observe_committed_view) and changes it only by submitting an intent the owner accepts. Reject code that keeps a reference to another owner's snapshot or plan, holds its writable container, or patches its money, goods or population directly, including through pointers or aliases the text guards miss.
- **Keynes: new continuation state is versioned, validated and installed atomically** When a change adds state that affects later days (fractional remainders, per-cell dates, request or ACK cursors, id counters), check that its owner freezes a copy at the commit boundary, bumps the section version, validates length, finiteness and content identity, decodes completely before installing, and rejects older versions with an explicit error. Saving only a cursor or a display mirror is not enough.
- **Keynes: fix the root cause instead of relaxing the check** Flag changes that make a failing test or replay pass by loosening assertions, widening tolerances, lengthening timeouts, adding retries, running more days, deleting compared fields or changing a hash algorithm. A fix must come with root-cause evidence (reproduction, log or code path) and keep the original comparison.
- **Keynes: errors fail loudly instead of falling back silently** When something goes wrong (a missing extension or method, a failed native call, invalid or missing data, an unexpected state, a failed load or decode), report it with push_error or an explicit error result, stop that operation and keep the previous state. Do not silently switch to another code path, a default value, an empty result or a GDScript reimplementation, and do not report success. A fallback is acceptable only where the docs name it as intended behaviour, and it must still log the cause. Defaults for values that are documented as optional are fine; flag a default only when it hides data or a result that must exist. The climate entry points in map_generator.gd (Pass-A, Pass-B, ocean, sea-ice, transpiration) have no fallback at all: no GDScript full-map computation and no successful empty result.
- **Keynes: daily stage functions stay engine-free** native_simulation_stage_<domain>.cpp functions run on both the inline path and the worker thread, so they must not touch Godot objects, resources or the GPU. Their bool return means continue traversal, not business success; success, waiting and failure stay in the existing stage/commit fields and fault state.
- **Keynes: saves happen only at a committed boundary and never lose commands** Saving must wait for a committed safe boundary through GameSaveCoordinator and must not capture Plan intermediates from a provider. Commands beyond the PKSR capacity must fail explicitly and keep every command. A failed load must not switch to a new world or continue a half-restored session.
- **Keynes: background-day tests wait for the committed day and receive results** Tests that advance background days manually must wait with wait_for_runtime_day for the committed date and run the production result-receive step (e.g. the host's _service_runtime_liveness) before asserting. Waiting only until the observed day grows, or using 'one more day after observing' as the completion condition, is wrong.
- **Keynes: session components get narrow dependencies and one daily entry** Components split out of world_runtime_host.gd receive narrow Callable or RefCounted dependencies, never the whole host, and never add a second daily-advance entry. Callbacks handed to signals or save services must be Callables bound to the host, not the component's own unbound methods.
- **Keynes: GDScript splits keep the public surface and literals** When splitting a GDScript file, public methods and signals stay in the original file as thin forwards and responsibilities move to RefCounted collaborators (pure transforms to static helpers), not extends chains. Adding a host. prefix must not change string literals or comments, and Callable(self, ...) or method names passed as values must still point at the host.
- **Keynes: shaders keep if-branches few and are judged by real GPU work** Use as few if statements in shaders as possible. Pixels in one batch that take different branches often execute both paths, so a branch rarely saves work and can cost it. Do not count an if-branch as saved work. There is no fixed pattern for shader optimisation: first measure where the GPU actually spends its time, then change that, and justify a claimed speed-up with measured frame time at the same quality and resolution.
- **Keynes: treasury construction checks the regime capability** Economy construction quote and apply must both reject requests from a country whose frozen CountryReadView lacks CountryApi::CAP_TREASURY_CONSTRUCTION. Regime state belongs to Country and must not be written to HexCell, DataCore or the Ideology POD; restoring an old save must not default to allowing treasury construction.
- **Keynes: gates are tested with inputs they must refuse** A new or changed gate, parser, allowlist or validator in tools/factory/ (or any code that decides whether something may proceed) must come with a test that feeds it an input it has to refuse: malformed, empty, unknown, or carrying extra syntax. Tests that only show good input being accepted do not count. Unknown values must be refused, not read as clean, and the function must be listed in GATES in tools/factory/tests/test_gates_refuse.py.



Finish with a short report: what you changed and why, which tests prove each criterion, and anything you could not verify.
