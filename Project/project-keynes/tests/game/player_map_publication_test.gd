extends "res://tests/game/player_scene_handoff_probe.gd"

## Drives the formal clock admission one day at a time, leaving the player
## scene's real publication reader and map preparation connected.
const WAITING_DAY := 20
var _hold_map := false
var _failures: Array[String] = []
var _ui_days: Array[int] = []
var _texture_days: Array[int] = []


func _run() -> void:
	if OS.get_environment("PK_SAVE_DIR").is_empty():
		printerr("Set PK_SAVE_DIR to an isolated directory for the map publication test")
		quit(1)
		return
	root.get_node("GameSettings").update({"frame_rate_limit": 60, "graphics_custom": true,
		"autosave_enabled": false, "ai_narrative_enabled": false, "event_pause_mask": 255}, false)
	var config := NewGameConfig.new()
	config.apply_land_layout(NewGameConfig.DEFAULT_LAND_LAYOUT)
	config.base.map_width = WIDTH
	config.base.map_height = HEIGHT
	config.base.initial_seed = SEED
	config.country.foreign_count = 3
	var normal := await _play_to_wait(config, false)
	var held := await _play_to_wait(config, true)
	_check(not normal.is_empty() and not held.is_empty() and normal == held,
		"daily outcomes, ordered receipts, and final map bytes match with and without the hold")
	if not held.is_empty():
		await _check_load_discards_pending_map()
	if is_instance_valid(_host):
		_check(bool((await _host.close_world()).get("ok", false)), "formal world closes")
	for failure in _failures:
		printerr(failure)
	print("PLAYER_MAP_PUBLICATION=", JSON.stringify({"failures": _failures,
		"compared_days": normal.get("records", []).size(), "display": DisplayServer.get_name()}))
	quit(0 if _failures.is_empty() else 1)


func _play_to_wait(config: NewGameConfig, hold: bool) -> Dictionary:
	var old_map: MapData = _host.current_map() if is_instance_valid(_host) else null
	var old_ext = _generator.get_data_core_world_ext() if old_map != null else null
	var old_generation := _host._runtime_commit_generation if old_map != null else 0
	var start := await _start_player_scene(root.get_node("GameFlow"), config)
	_check(bool(start.get("ok", false)), "starts through GameFlow")
	if not start.get("ok", false):
		return {}
	_attach_scene()
	if old_ext != null:
		_check(old_ext.read_runtime_map_lut_frame(old_map, WAITING_DAY, old_generation,
			old_map.cell_count()).is_empty(), "new game discards the old map publication")
	var ext = _generator.get_data_core_world_ext()
	_check(_host.received_worker_day() <= 0 and Engine.max_fps == 60, "starts at day zero at 60 fps")
	for command: Dictionary in COMMAND_LOG:
		var admission: Dictionary = ext.submit_runtime_command(command)
		_check(admission.get("ok", false) and admission.get("effective_day") == command.requested_day,
			"admits the same command log before day one")
	_clock.set_speed(50.0)
	_clock.pause(false)
	_host.publication_reader.interval_usec = 100_000
	process_frame.connect(_set_map_budget)
	var opening: Array = []
	var copies := 0
	for day in range(1, WAITING_DAY + 1):
		if not await _advance_to(day):
			process_frame.disconnect(_set_map_budget)
			return {}
		var sample := _timings.take()
		var expected := 0 if _hold_map else 1
		_check(sample.received_batches == 1 and sample.map_copies.size() == expected,
			"day %d delivers records and performs %d map copies" % [day, expected])
		_check(not _ui_days.is_empty() and _ui_days.back() == day, "UI publishes day %d on the receipt frame" % day)
		copies += sample.map_copies.size()
		if day == 1:
			opening = _atlas()
			_hold_map = hold
			_set_map_budget()
		if _hold_map:
			_check(_atlas() == opening and _texture_days == [1],
				"day %d leaves the map at its last published textures" % day)
	var control := _generator.get_runtime_control_state()
	var offer: Dictionary = _controller.narrative_service().active_offer()
	_check(control.get("player_block_day") == WAITING_DAY
		and control.get("player_block_reason") == "narrative_choice_required"
		and _host.player_confirmation_view().get("reason") == "narrative_choice_required"
		and offer.get("event_id") == "evt.citychain.wall", "worker and player scene reach the same story choice")
	_check(_commands_settled() and _day_rows.size() == WAITING_DAY,
		"receives all days and the ordered command receipts through the wait")
	var generation := _host._runtime_commit_generation
	_clock.pause(true)
	_host._sync_runtime_worker_clock()
	if hold:
		# The pending frame survives a replacement executor, even before its first new day.
		_check(bool(_host.restart_runtime_executor().get("ok", false)), "restarter accepts paused world")
		_hold_map = false
		await process_frame
		await process_frame
		var recovered: Array = _timings.take().map_copies
		_check(recovered.size() == 1 and recovered[0].day == WAITING_DAY
			and recovered[0].bytes == 2 * WIDTH * HEIGHT and _texture_days == [1, WAITING_DAY],
			"paused recovery reads and publishes the latest full map exactly once")
	process_frame.disconnect(_set_map_budget)
	_check(_host.received_worker_day() == WAITING_DAY and _clock.paused,
		"map recovery does not release another simulation day")
	_check_identity_rejection(ext, generation)
	var records: Array = []
	for row: Dictionary in _day_rows:
		records.append([row.day, row.business_hash, row.receipts])
	var atlas := _atlas()
	_check(atlas.size() == 4 and atlas.all(func(bytes: PackedByteArray): return bytes.size() >= 4 * WIDTH * HEIGHT)
		and atlas != opening, "the map produced complete, updated atlas bytes")
	print("MAP_READ_PHASE=", JSON.stringify({"held": hold, "copies_before_recovery": copies,
		"texture_days": _texture_days, "ui_days": _ui_days, "player_day": control.get("player_block_day")}))
	return {"records": records, "atlas": atlas, "offer": offer.get("event_id")}


func _attach_scene() -> void:
	var scene := current_scene as PlayerGame
	_host = scene.get_node("RuntimeHost")
	_generator = _host.get_generator()
	_clock = scene.get_node("WorldClock")
	_controller = scene.get_node("PlayerController")
	_clock.set_process(false)
	_hold_map = false
	_ui_days.clear()
	_texture_days.clear()
	_day_rows.clear()
	_timings = FrameTimings.new()
	_timings.attach(_host)
	_host.simulation_day_records.connect(_record_days)
	_host.simulation_ui_updated.connect(func(_from, day, _generation): _ui_days.append(day))
	_host.map_texture_published.connect(func(day): _texture_days.append(day))


func _advance_to(day: int) -> bool:
	var through := day + 1 if day == WAITING_DAY else day
	_check(_host._admit_runtime_calendar(through + 1) >= through,
		"calendar admits work through day %d" % through)
	var started := Time.get_ticks_usec()
	while _host.received_worker_day() < day and not _host.is_runtime_fault_paused():
		if Time.get_ticks_usec() - started >= WATCHDOG_USEC:
			break
		await process_frame
	var arrived := _host.received_worker_day() == day and not _host.is_runtime_fault_paused()
	_check(arrived, "day %d delivered through the normal publication reader" % day)
	return arrived


func _set_map_budget() -> void:
	if not is_instance_valid(_host):
		return
	var spent := roundi(1_000_000.0 / Engine.max_fps) if _hold_map else 0
	_host._presentation._map_updates.start_frame(Time.get_ticks_usec() - spent if _hold_map else 0)


func _atlas() -> Array:
	var baker: MapBaker = _generator._baker
	return [baker._cell_enum_lut_bytes_cache, baker._cell_dyn_lut_bytes_cache,
		baker._cell_eco_lut_bytes_cache, baker._prev_weather_lut_bytes]


func _check_identity_rejection(ext, generation: int) -> void:
	var map := _host.current_map()
	var day := _host.received_worker_day()
	var count := map.cell_count()
	var wrong_map := MapData.new(WIDTH, HEIGHT)
	_check(ext.read_runtime_map_lut_frame(wrong_map, day, generation, count).is_empty()
		and ext.read_runtime_map_lut_frame(map, day - 1, generation, count).is_empty()
		and ext.read_runtime_map_lut_frame(map, day, generation + 1, count).is_empty()
		and ext.read_runtime_map_lut_frame(map, day, generation, count - 1).is_empty(),
		"native reader refuses a different map, day, generation or count")


func _check_load_discards_pending_map() -> void:
	var offer: Dictionary = _controller.narrative_service().active_offer()
	_hold_map = true
	process_frame.connect(_set_map_budget)
	# The choice can release a day before the next process_frame callback.
	_set_map_budget()
	var flow = _controller.narrative_flow()
	flow.on_outcome_acknowledged()
	var receipt: Dictionary = flow.on_option_chosen(int(offer.offer_id), int(offer.offer_generation), 0)
	_check(receipt.get("ok", false) and int(receipt.effective_day) == WAITING_DAY + 1,
		"player answer is admitted for the next day")
	_clock.pause(false)
	_host._sync_runtime_worker_clock()
	var next_day := WAITING_DAY + 1
	var arrived := await _advance_to(next_day)
	_clock.pause(true)
	_host._sync_runtime_worker_clock()
	if arrived:
		await _save_and_reload_pending_map(next_day)
	process_frame.disconnect(_set_map_budget)


func _save_and_reload_pending_map(day: int) -> void:
	_check(_host._presentation._map_updates.has_pending(),
		"the next day has staged map data before save")
	var save: Dictionary = await root.get_node("GameSave").request_manual_save("manual_1")
	_check(save.get("ok", false), "save succeeds while map data is held")
	if not save.get("ok", false):
		return
	var pending: bool = _host._presentation._map_updates.has_pending()
	var copies: Array = _timings.take().map_copies
	_check(pending and copies.is_empty(),
		"save leaves the unneeded map copy pending (pending=%s, copies=%s)" % [pending, copies])
	var old_map := _host.current_map()
	var old_ext = _generator.get_data_core_world_ext()
	var generation := _host._runtime_commit_generation
	var previous_id := current_scene.get_instance_id()
	var game_flow := root.get_node("GameFlow")
	var failures: Array[Dictionary] = []
	var failed := func(info): failures.append(info)
	game_flow.player_start_failed.connect(failed)
	var loaded: Dictionary = game_flow.begin_load_game("manual_1")
	if loaded.get("ok", false):
		loaded = await _wait_for_player_scene(game_flow, previous_id, failures)
	game_flow.player_start_failed.disconnect(failed)
	_check(loaded.get("ok", false), "reopens the save through GameFlow")
	if not loaded.get("ok", false):
		return
	_attach_scene()
	_check(_host.current_map() != old_map and _host.received_worker_day() == day
		and not _host._presentation._map_updates.has_pending()
		and old_ext.read_runtime_map_lut_frame(old_map, day, generation, old_map.cell_count()).is_empty(),
		"load restores the saved date and discards the previous scene's pending map")


func _check(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
