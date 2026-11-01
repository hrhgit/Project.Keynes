# dots_ext — ProjectKeynes DOTS GDExtension

C++ implementation of the DataCore world hot loop, part of the DOTS roadmap
(see `.codebuddy/plan/dots-roadmap-to-gdextension/`).

## Layout

```
gdext/
├── SConstruct           # SCons build script (wraps godot-cpp)
├── godot-cpp/           # git submodule, pinned to the Godot 4.7-compatible stable commit
└── src/
    ├── register_types.{h,cpp}      # GDExtension init / class registration
    ├── world_ext.{h,cpp}           # DCWorldExt main type
    ├── components/
    │   ├── component_ids.h         # Mirrors GDScript DCComponentIds
    │   └── slot.h                  # Internal _Slot struct
    ├── systems/                    # Hot-loop ports (filled in I3.B/C)
    └── profiles/                   # ClimateProfile plain-struct serdes (I3.B)
```

Compiled binaries land in
`../Project/project-keynes/addons/dots_ext/bin/<platform>/` automatically — no
manual copy step.

## Building (Windows)

Open **x64 Native Tools Command Prompt for VS 2022**, then:

```
cd D:\Godot\ProjectKeynes\Project.Keynes\gdext
scons platform=windows target=template_debug
scons platform=windows target=template_release
```

First build will compile godot-cpp itself (~10–20 minutes). Subsequent
builds are incremental.

## Setup after fresh clone

```
git submodule update --init --recursive
```

## Why we pin godot-cpp 10.0.0-stable

The submodule is pinned to the `10.0.0-stable` release, whose bundled
`extension_api-4-7.json` targets `v4.7.stable.official`. `gdext/SConstruct`
passes `api_version=4.7` explicitly, so a future movement on godot-cpp `master`
cannot silently change the generated bindings.

## Targeted Godot version

Godot **4.7.2** (Windows / macOS arm64 / Linux / Android arm64 / Web).
The project and extension metadata require Godot 4.7 so the editor, native
extension, and export templates use the same API generation.

## I3.A scope reminder

This extension currently only exposes the *interface* DCWorld already
provides — `register_component`, `view_f32/i32/u8`, `bind_map_data`,
`create_pool`, `create_archetype`, etc. The hot-loop entry points
(`run_climate_pass_a`, etc.) are stubs returning `-1.0`, signalling the
GDScript caller to fall back to the legacy path. I3.B/C will fill them in.
