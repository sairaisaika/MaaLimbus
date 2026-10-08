# MaaFramework conformance

This page records the reading of MaaFramework that this project's click behaviour and
assets are held to, and what that reading found. It answers the question "are we doing
what the framework's specification says", with file and line references instead of
belief.

The framework this project ships is pinned by `pyproject.toml`:

```
dependencies = ["maafw==5.12.2", "numpy>=2", "opencv-python>=4.10"]
```

so the evidence below was read at the matching tag `v5.12.2` of
<https://github.com/MaaXYZ/MaaFramework> and kept locally for re-reading:

* `build/maafw-v5.12.2/ControllerAgent.cpp`
* `build/maafw-v5.12.2/2.4-控制方式说明.md`
* `build/maafw-v5.12.2/3.3-ProjectInterfaceV2协议.md`
* `build/maafw-src/MaaDef.h`, `AdbControlUnitMgr.cpp`, `InputAgent.cpp`,
  `AdbShellInput.cpp`, `MaatouchInput.cpp`, `MuMuPlayerExtras.cpp`,
  `3.1-任务流水线协议.md`, `2.2-集成接口一览.md`

The build that runs on this machine bundles MaaFramework `v5.12.2` as well
(`build/portable check 249aba9398a84dbfacd55c2b79065cd7/build-info.json` → `inputs.maa`
`MAA-win-x86_64-v5.12.2.zip`), so the specification read here and the binary here are
the same release.

## The click coordinate space

**Question.** Our plans, OCR boxes and journals are all in a 1920x1080 space
(`tools/window_step.py:776` sets `controller.set_screenshot_target_long_side(1920)`,
and a journal target looks like `[1440,771,121,134]`), while the device answers
`adb shell wm size` with `Physical size: 720x1280`. Does `post_click(x, y)` want the
scaled image's coordinates or the raw screenshot's?

**Answer: the scaled image's.** The framework converts for us —
`ControllerAgent::preproc_touch_point` (`ControllerAgent.cpp:1038-1060`) is called by
every touch handler (`handle_click` `:448`, long press `:470`, swipe `:498/:506`,
`:592/:594`, `:681`, `:694`, `:872`) and computes

```cpp
double scale_width  = static_cast<double>(image_raw_width_)  / image_target_width_;
double scale_height = static_cast<double>(image_raw_height_) / image_target_height_;
int proced_x = static_cast<int>(std::round(p.x * scale_width));
int proced_y = static_cast<int>(std::round(p.y * scale_height));
```

returning the point unchanged only when the control unit advertises
`MaaControllerFeature_NoScalingTouchPoints` (`:1040`). The screenshots themselves are
resized to the target on every grab (`postproc_screenshot`, `cv::resize` at `:1082`),
which is why recognition and input share one space. The manual states the same rule in
`2.4-控制方式说明.md:68`: "MaaFramework 会在 `ControllerAgent` 中统一把缩放后的识别坐标
换算回原始截图坐标."

**No ADB input unit opts out of that conversion.** `AdbControlUnitMgr::get_features()`
returns the input unit's features when one is available (`AdbControlUnitMgr.cpp:103-108`),
`InputAgent` picks the first available unit in the documented order EmulatorExtras >
Maatouch > MinitouchAndAdbKey > AdbShell (`InputAgent.cpp:19-33`, `:129-136`), and the
units return `MaaControllerFeature_None` (`AdbShellInput.cpp:27-29`) or
`UseMouseDownAndUpInsteadOfClick | UseKeyboardDownAndUpInsteadOfClick`
(`MaatouchInput.cpp:43-45`, `MuMuPlayerExtras.cpp:102-104`) — never
`NoScalingTouchPoints`.

**Our side therefore:** clicking in the 1920x1080 space our vision produces is the
documented usage, not a coincidence. Every touch goes through the asynchronous
`controller.post_click` / `post_swipe` and is awaited —
`tools/window_step.py:536`, `:853`, `:1164` (`wait_job(controller.post_click(*point), timeout=10, ...)`),
`:886`, `:1156` for swipes, after `controller.post_connection()` at `:775` — which is
what `2.2-集成接口一览.md` describes (`MaaControllerPostClick` returns an operation id;
status and wait are separate calls).

## The controller

* Discovery uses the toolkit, not a hand-written guess: `src/maalimbus/adb_device.py`
  calls `Toolkit.find_adb_devices(adb_path)` and builds
  `AdbController(record['adb_path'], record['address'], int(record['screencap_methods']), methods, record['config'])`,
  i.e. the methods the toolkit measured for this device.
* `2.4-控制方式说明.md:8` spells out the same division of labour for ProjectInterface V2:
  the interface may configure Win32 `screencap`/`mouse`/`keyboard`, while
  "Adb 控制器的 screencap/input 使用 `MaaToolkitAdbDeviceFind` 自动检测和选择最优方式，无需手动配置".
  `assets/interface.json` follows that: its three Win32 controllers name their methods,
  and its `mumu-adb` controller is `{"type": "Adb", "display_long_side": 1920, "adb": {}}`.
* Input is only ever sent when discovery offered EmulatorExtras (MuMu 12 serves the touch
  through the host, which is what once moved the user's mouse); read-only passes build the
  same controller with `MaaAdbInputMethodEnum.Null`. That policy is our own choice, stated
  in `src/maalimbus/adb_device.py`'s docstring, and it is stricter than the framework
  requires.

## ProjectInterface V2

`assets/interface.json` is checked against `3.3-ProjectInterfaceV2协议.md`:

| Protocol rule | Where | Our asset |
| --- | --- | --- |
| `interface_version` is the number `2` | `:44`, `:422` | `2` |
| controller `type` ∈ `Adb/Win32/MacOS/PlayCover/Gamepad/Linux` | `:161` | `Win32` x3, `Adb` x1 |
| `display_short_side` / `display_long_side` / `display_expand` / `display_raw` are mutually exclusive | `:122-126` | one `display_long_side: 1920` per controller |
| Win32 `screencap`/`mouse`/`keyboard` come from the documented names | `2.4`, `MaaDef.h:359-434` | `Background`/`ScreenDC`, `SendMessageWithCursorPos`/`SendMessageWithWindowPos`/`Seize`, `PostMessage`/`Seize` |
| Adb input/screencap are auto-detected, not configured | `:146` | `"adb": {}` |
| `task.entry` and `option.cases[].pipeline_override` name real pipeline nodes | `:576`, `:653` | checked by tool (below) |
| Official Win32 example | `:446` | our `windows-window` profile matches it method for method |

## The task pipeline

Nodes are checked against `3.1-任务流水线协议.md`: every field used is a protocol field,
every `next` / `on_error` / `interrupt` / `on_timeout` names an existing node (or carries
one of the `[JumpBack]` / `[Error]` / `[Stop]` / `[DetectionMissed]` markers), and
`"target": true` means "the box this node just recognized", which is what the Click nodes
mean by it. `assets/resource/base/pipeline/mirror.json` holds 89 nodes, 56 of them
reachable from the five task entries; the other 33 are drivable by name from the toolkit
(for example `MapObserve`, which `tools/map_live_observe.py` runs directly) and are
reported as a note rather than a failure.

## What the review found and changed

**Defect: two pipeline nodes named custom actions the agent never registered.**
`MapObserve` uses `limbus_map_observe` and `BattleObserve` uses `limbus_battle_observe`,
but `agent/main.py` registered only 11 names — neither of those among them. A node whose
`custom_action` was never registered cannot run: the framework has no implementation to
call (`docs/zh_cn/1.3-Custom&Agent.md`). The classes were present all along
(`agent/recognition.py:891 MapObservation`, `:926 BattleObservation`), so the fix is the
registration itself, now at `agent/main.py:51-57`.

**Guard: `tools/verify_pipeline_spec.py`.** The protocol rules above are executable:
it loads `assets/interface.json`, every `assets/resource/*/pipeline/*.json` and
`agent/main.py`, reports what the protocols do not define, and exits 1 on a violation
(`--interface/--pipeline/--agent-main/--report`). `tests/test_pipeline_spec.py` pins it
with 9 tests, including the negative cases (an unknown controller type, two scaling modes
on one controller, an override naming no node, a node naming an unregistered action).

Current result: `python tools/verify_pipeline_spec.py` → `ok — 0 problem(s)`.

## Not claimed

* No ProjectInterface / MXU run was performed in this pass; the interface was read, not
  driven. The Win32 controller names were checked against the manual's tables, not
  exercised on a window.
* The toolkit's auto-detection timing (the manual's "启动时测速") was not measured; only
  that we consume its answer.
* The 33 pipeline nodes unreachable from the task entries are reported, not deleted: some
  are toolkit entry points and some are reserved.
* The conformance checker covers the fields this project uses. A protocol feature we do
  not use (Gamepad, PlayCover, Win32 `Interception`, …) is not asserted either way.
