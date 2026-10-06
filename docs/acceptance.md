# Acceptance evidence

## 2026-10-05 offline map identity repair

- `src/maalimbus/map_vision.py` now identifies the Mirror Dungeon map page from the
  localized floor header plus the theme-pack line beneath it; artwork, currency and
  season icons are never anchors. `agent/recognition.py` promotes only that page to
  scene `MAP`, and `ThemeObservation` records `theme_map_postcondition` with
  `selected` true solely when the fresh floor header names the pack this run planned.
- Actual Maa OCR/recognition replay over the retained `231221/terminal.png` (binary
  `build/portable check 249aba9398a84dbfacd55c2b79065cd7/maafw`) identifies scene
  `MAP` and hits only `OfflineMapHeader`; the retained pack page is not promoted and
  hits no map node. The replay controller asserts that click/swipe/touch/key are
  never called: `build/map-frame-replay-verification.json`, no device input.
- Route reading stays an explicit refusal. The retained map frame shows no provable
  unvisited node, so `route_decision` returns `current_position_not_proven` and
  records no click target; `tools/verify_map_replay.py` deliberately sends no input.
- 153 Python tests pass (145 before this change). Node identity, floor-1 routing and
  any live continuation from the stopped session remain unproven and unauthorised.

## 2026-10-05 23:13 actual downward pack selection

- Real-frame Maa intercepted replay passed five cases: one downward Swipe on the
  original230455/frame-0001.png, zero on missing mode/header/Refresh and altered
  covers with uncertain HARD OCR. No device in replay; unchanged post-frame keeps
  selected false. Terminal frame OCR also failed closed, retained as a robustness
  issue rather than a threshold relaxation.
- Actual MuMu session231221 used Maatouch once to drag To be Cleaved downward,
  after foreground/process/lease checks. Fresh terminal.png visibly proves entry
  into Exploring Floor1 / To be Cleaved map. Result stoppedconfirmed, UNKNOWN,
  verified_clear false. Map classification/routing must be repaired offline before
  further input. This is live pack-selection evidence, not floor completion.

## 2026-10-05 23:05 free receipts and Hard selection page

-224322 acknowledged first named free gift, exposing the second named receipt.
  224508 acknowledged second receipt, exposing extra gift search. Fresh224916
  verifies both Owned labels and distinct catalog icons; this is initial gift
  ownership evidence, not final dungeon rewards. Unknown new page stopped input
  until classification and ownership proof were repaired offline.
-225222 refused extra gift search at0/3 and zero selected cost.225439 confirmed
  Forgo;225512 read-only capture showed Normal floor1 packs.230146 toggled Hard
  once; highlighted mode recognition failed closed and was repaired offline.
  230455 fresh native proof confirms HARD, clears only difficulty pending, and
  retains `terminal.png` with all three pack names. No pack drag has occurred.
- Latest complete Python suite:145 passed. Maa replay checks cover wrapped receipt
  names, Owned icon identity, modal veto, free-search refusal and highlighted Hard
  mode. Derived images are not live selection or map proof. User's downward-drag
  instruction agrees with native Swipe; actual-frame geometry validation and live
  map postcondition remain pending. No floor or final reward is accepted.

## 2026-10-05 22:36 initial gifts

- Read-only actual MuMu222911 unchanged at0/2. Native223048 clicked the independently
  OCR-identified Bleed header for saved team1, exposing three actual candidates.
- Native223230 selected first priority Wound Clerid. Read-only proof task223418
  verified fresh exact title, row1 selection border and1/2; uncertain intent was
  retained until that proof. Native223506 selected second priority Little and
  To-be-Naughty Plushie; fresh exact title, rows1/2 and2/2 confirmed in-frame.
- Native223639 submitted2/2 once. Actual terminal screenshot shows Wound Clerid
  E.G.O Gift GET modal. Task is stoppedconfirmed; no receipt Confirm sent yet.
  Retained private pending prevents repeat Commit. Gift GET does not prove any
  floor clear or Enkephalin-module reward receipt.
- Actual Maa intercepted group/pick/proof/commit replays passed original/changed
  icon cases and rejected missing counters, wrong profile/foreground, wrong title
  and absent selection marker. No incomplete/unverified intent is reset by replay.
  Retained GET observation native Maa OCR passed with zero input; GET title without
  independent Confirm vetoes underlying selection UI. Python full143 passed before
  last veto change;12 focused tests passed afterwards.
- Next: bounded per-gift acknowledgements, actual Hard difficulty and floor1 entry;
  all remaining full-goal acceptance remains open. FGO was not reopened.

## 2026-10-05 22:27 MuMu star stage

- Latest usage refresh allowed ordinary work (58% five-hour/76% weekly consumed).
  No credits purchase/reset. Verified one foreground Android package and shared
  controller lease for each bounded session. CLI now records its actual Windows
  executable/PID/integrity before constructing the controller; latest PID35540
  ended with `stop_confirmed:true`. No MaaLimbus/FGO controller remained in CIM.
- Real entry confirmation, saved team1 row/header confirmation, low-level warning
  and star page retained in215631,220118,220441 sessions. Tutorial was already
  absent at the relevant initial frames: no native tutorial-exit success claimed.
- Real single-choice sessions222020/222045/222108/222131 selected Lix1,3,4,6.
  Each fresh available balance matched prior minus10/20/30/40, ending7. No Enhance.
- Session222313 entered the confirmation modal and stopped; its default conversion
  was checked. Session222509 disabled it; actual terminal frame shows unchecked
  checkbox and Cost0. Session222652 confirmed and actual terminal capture shows
  initial E.G.O Gift selection, count0/2. All are retained real Maa captures, not
  derived images. Owned7541 is visible before confirmation; final settlement and
  clear still unproved. No gifts/floors/rewards have been accepted yet.
- `build/star-replay-verification.json`: source/changed-buff/derived-balance plus
  missing-grid/over-budget/pending-input. Derived balance is explicitly synthetic.
  Entry/conversion/confirmation replay reports retain native Maa OCR/TemplateMatch
  with intercepted clicks and zero-input negative cases. Full suite143 passed.
- Local Lix import saved/read back seven profiles and preserved rotation/deployment;
  latest user's1,3,4,6 overrides older1,4,5,6. Highest-level compatible identity policy
  is offline-only; no actual automatic roster/filter/identity-switch acceptance yet.
- Remaining: initial gifts/native Hard floors1–5, reward receipt and module budget,
  team rotation/re-entry, native automatic formation/MXU settings, JP real pages,
  Windows/PI/package/update validation and FGO error option/Release. Goal stays active.

## 2026-10-05 MuMu continuation

- Usage allowed: 26% five-hour and 72% weekly consumed at start. No credits bought/reset.
- Clean initial git state; latest previous Limbus evidence was October 1. Old recorded
  PID39436 absent. New controllers65148/47524 paths/arguments/parents read via CIM;
  shared OS lease held throughout and confirmed task stop before subsequent observation.
- Maa AdbController Encode screenshot + Null input captured already foreground Android
  `com.ProjectMoon.LimbusCompany` at 1920x1080. No game restart.
- Maatouch actual navigation: HOME -> Drive -> mirror entry. Retained original and
  changed-art home/menu frames pass actual Maa OCR/Pipeline with intercepted clicks;
  missing independent anchor produces zero input. Random inset targets and 180..480ms
  pre-delay retained in recognition journals. Full suite128 passed before tutorial guard.
- Enter was attempted against underlying text while a tutorial was present. Postcondition
  did not occur; session stopped confirmed. Read-only terminal frame proves tutorial remains.
  Added tutorial veto; dismissal and this final guard require offline/native verification.
- `evidence/runtime/live-20261005-214739`, `live-20261005-215020`,
  `adb-probe-20261005-215059`; `build/home-replay-verification.json`,
  `build/drive-adb-replay-verification.json`. No resource purchase/refill/conversion.
- No five-floor clear, reward receipt, deployment/rotation/re-entry, JP live acceptance,
  MXU Android preflight integration, new Windows package or FGO Release claimed.

## Custom deployment choices and callback failure boundary

- Twelve PI child dropdowns apply only in custom mode. All twelve positions must
  be complete and unique before atomic save; other teams/preferences are retained.
- A derived replay exposed an exception escaping Maa's ctypes callback and
  continuing old-order selection. All recognition/action callbacks now explicitly
  fail and latch the Agent instance closed, even if journal writes fail.
- 125 tests, 17 actual Maa derived deployment cases and seven battle-planning
  regressions pass. Six callback faults produce zero clicks, no order proof or
  battle start. `build/deployment-replay-verification.json` retains actual errors.
- Clean d14d119 Windows development package: 622 manifest hashes/self-test pass.
  Nine frozen-Agent deployment IPC cases pass, including custom save and five
  invalid-config/evidence cases with zero input. Four frozen-Agent battle
  regressions pass (1/1/0/0 P), plus three source navigation regressions.
  `build/packaged-deployment-replay-verification.json`,
  `build/packaged-battle-replay-verification.json`, `build/battle-package-integrity.json`
  retain this package's scope. No release, game controller, GUI replacement or UAC.
- The old 08c2adc GUI exited normally. Actual d14d119 MXU displays positions1..12;
  changed positions1/3 survive normal exit/restart, with all twelve persisted
  options identical. New GUI PID23688 is disconnected, one unchecked task,
  auto-run false; no live game task, input or UAC. Frozen Agent replay resolves
  these actual saved choices against installed PI, saves the full order and
  selects the first three derived slots while retaining the other team/preferences.
  `build/native-deployment-ui-verification.json` and
  `build/mxu-deployment-options-replay-verification.json` retain evidence.
  GUI Start dispatch and live geometry remain unverified; five floors/rewards/
  rotation are incomplete. Game remains HIGH/minimized; no permission bypass.

Each requirement needs implementation plus matching verification scope. Status is not inferred
from a task returning success, a manifest loading, or a process staying alive.

| Requirement | Current status | Required evidence |
| --- | --- | --- |
| Maa Win32 native input/screenshot | Capture verified; live input blocked by game HIGH vs Maa MEDIUM integrity | Running game capture and recognized click with page postcondition |
| PI V2 labels and EN/JP resources | Maa resources parsed; native Chinese MXU/controller/task/12-position display verified; EN/JP game acceptance pending | Actual Maa parser + MXU UI |
| Variable cover/background recognition | Actual Maa saved-frame replay: reference, changed cover, unknown | Four supplied frames + live frame; negative and changed-art replay |
| Saved teams / deployment / rotation | Library and experimental deployment-order derived replays passed; profiles persist; live deployment/rotation pending | Save/restart persistence + two different confirmed dungeon teams |
| Five hard floors | Not verified | Floor 1..5 battle and completion observations |
| Battle planning / turn execution | Experimental one-shot native P planning and fresh-frame diagnostics replayed; turn/EGO/victory pending | Full selected-skill/clash/survival proof + actual turn and victory/map return |
| Rewards then repeat | Not verified | Reward receipt and next-run entry with next team |
| Gifts / enemy buffs / theme pack selection | Floor gifts and weighted theme-title/native drag derived replays passed; enemy buffs and full-loop integration pending | Live selection quota, confirmation, acquisition and next-floor postcondition |
| Human-paced jitter and bounded sessions | Finite Maa node hits; inset clicks/delays, bounded setup/stop jobs and monotonic CLI deadline tested | Full-run cancellation and timeout checks still required |
| Stamina conversion / refill budgets | Pure budget boundaries passed; no spending implementation yet | Zero-spend default, budget boundaries and balance postconditions |
| Mail / daily rewards | Design | Claimed/empty mailbox and mission reward evidence |
| GitHub update / rate-limit resume | Metadata/cache and isolated download/checksum/manifest staging implemented; 612-file development ZIP offline staging passed. MXU UI and installer pending | Public asset download + installed version/config preservation + rollback |
| Windows package | Local development package built; packaged Agent IPC replay passed; MXU UI/live acceptance and release audit pending | Portable build + actual UI/runtime + installed version/config preservation |
| FGO error option and Release | Error option built/installed, config preserved; actual GUI exit + public Release pending | Option persistence/error action; full release gate + published asset |

## 2026-10-01 evidence

- 39 tests passed (policies, profile/ordered run persistence, Windows identity,
  team positions, EN/JP strings, GitHub deadlines and error/cache behavior;
  includes a real Windows two-process controller-lock exclusion test).
- Actual Maa 5.12.2 parser/OCR/Pipeline: three navigation replay cases and six team
  library cases passed. The #2 title change and resource dialog are derived fixtures.
  Already selected, missing slot, stuck click, paid dialog and unknown behavior are
  verified offline. User frame #2 is the Sinners library, not dungeon deployment.
- Live read-only Windows process identity: game integrity RID 12288; controller
  RID 8192. Earlier Seize calls did not change the page. All task entries now check
  identity/privileges before input. No new live click attempted after this finding.
- `build/native-replay-verification.json`, `build/team-replay-verification.json`,
  `build/windows-preflight.json` are local evidence, excluded from release.
- FGO prepublish audit returned ready with a missing-project-license warning;
  this is a privacy/source-tree audit, not full-suite or release validation.
- FGO's full current Python suite subsequently passed 710 tests after stale
  controller-scenario timing/retry assertions were corrected. Production behavior
  unchanged. Error options, license and release package/publishing are still pending.

## Runtime bounds refresh

- 43 tests pass, including finite pending setup/stop jobs, timeout cancellation,
  interrupted sessions and the distinction between task status and dungeon clear.
- CLI setup/load time now consumes the same monotonic session budget; wall-clock
  changes cannot extend it. If a stop does not complete, `stop_confirmed` remains
  false and the controller lease stays held until the process exits.
- Game PID40196 is still HIGH integrity RID12288; the inspected Python controller
  is MEDIUM RID8192. This is a read-only refresh, not a new live attempt.

## Floor-gift recognition refresh

- 48 tests pass. Imported 332 public cropped gift icons from pinned LALC with
  per-file hashes/source paths and keyword groups. Only local reward labels,
  ownership strips and gift icons are considered; covers/identities are not.
- The production recognizer supports `FLOOR_GIFTS` / `gift_mode: recommend` with
  a configured team. Owned is associated by column, block-list wins, uncertain
  titles/icons and overlapping candidates are refused. The default rank remains
  unowned preferred → unowned other → owned. Each ranking retains target/provenance
  and explicitly sets `selected=false`, `reward_received=false`.
- Actual Maa OCR/CustomRecognition/Click routing passed five derived public-icon
  cases: preferred, owned preferred, all blocked, paid zero-input and icon-only
  identity with the JP resource. This does not verify Japanese rendered text,
  selection quota, reward confirmation/receipt or a live floor transition.
  The helper is not yet wired into the full dungeon loop.
- Three navigation and six team-library Maa replay regressions passed. Private
  local result: `build/gift-replay-verification.json`.
- Original FGO installation is now clean 36e2f79, with nine configuration files
  preserved and a retained rollback directory. Packaged Agent replay passed;
  GUI error-option/exit and public Release remain unverified/unpublished.

## Native Windows launcher and continuation schedule

- Compared MaaEnd's published `assets/interface.json`: Win32 foreground/background
  controllers declare `permission_required: true`. LALC's `update_to.bat` starts
  its application with standard Windows `RunAs`. MaaLimbus now declares the same
  permission requirement and includes `tools/start_native.ps1` with normal UAC.
- Launcher/wrapper scripts parse successfully. The wrapper invokes only the native
  bounded Maa CLI, records separate stdout/stderr, and enforces the exact created
  process's outer deadline. Identity and one-controller gates are preserved.
- A real UAC request was issued this turn; Windows returned operation cancelled.
  No new wrapper/runner or live transition was established. No permission was
  bypassed and no second request was issued. The game remains at Before Entry.
- App heartbeat `maalimbus` is active every 30 minutes on the current thread.
  It checks usage availability and resumes the entire goal after limits recover,
  remaining quiet on unchanged/limited state. This is scheduling proof, not proof
  of future executions or live dungeon completion.

## README and license reference correction

- Chinese/English README now follows the pinned MaaFramework title/badges/language,
  introduction/start, statements/licenses, development, acknowledgements and
  communication structure. Actual feature coverage remains explicit.
- Original MaaFramework LGPL and Lix AGPL notices remain; the GNU GPL v3 text
  referenced by LGPL has been added. Main-project AGPL was a project choice,
  not a framework requirement; no third-party material was relicensed.
- `docs/readme-license-reference.md` maps the user's four specified references
  to the current application and lists remaining packaging/artwork rights gaps.
  Documentation alignment is not evidence of live completion or release readiness.

## Local Windows package and packaged IPC verification

- Fixed frozen Agent/Runner root resolution and import-time native library setup.
  Packaged resources are resolved from the executable's installation, not cwd or
  PyInstaller extraction. EN/JP and gift catalog load from the actual package.
- 57 tests passed, including installed path resolution, unsafe archive prevalidation
  and public source archive privacy exclusions. Two packed executables built.
- Actual Maa AgentClient connected to the packaged Agent. Installed resource/OCR/
  Pipeline passed reference navigation (two replay clicks, TEAM_LIBRARY boundary)
  and UNKNOWN (zero input). Both preserve `verified_clear: false`; no Win32 game
  controller was constructed. Record: `build/packaged-replay-verification.json`.
- Local development ZIP manifest verified; source/third-party notices are included.
  Builder never overwrites an install or publishes a release. Current game process
  remained HIGH integrity 12288 vs controller MEDIUM 8192; no UAC was requested.
- Actual MXU UI, live input, five floors/rewards/rotation and complete source/asset
  redistribution audit remain pending. This is a local development packaging gate.

## Native theme-pack selection

- Stable five-glyph/title recognition replaces whole-card matching; 95 pinned
  names, team-specific weights and zero-weight blocks persist in old-compatible
  profiles. PI selects names/weights from choices and writes independent nodes.
- Actual Maa production graph replay passed seven derived cases: save/read
  preference, changed artwork, NEW exclusion, unknown, NORMAL, paid, all blocked.
  Three permitted cases route exactly one native Swipe; four negative cases send
  zero input. After dragging a fresh frame is observed and the task intentionally
  stops with `selected=false` / `verified_clear=false` at the unfinished map boundary.
- Fixed short-title OCR boxes extending several pixels past the card; bounded
  padding permits that case without accepting adjacent titles. Fixed option
  overrides replacing custom parameters and losing their mode/other settings.
- `build/theme-replay-verification.json` retains local scope and frame provenance.
  No UAC/game input was requested. Japanese rendered titles, live selection,
  difficulty switching/refresh policy, deployment/battle and complete loop remain pending.
- 68 unit tests and six team-library Maa regression cases passed. New Windows
  development package from clean `4178821` includes the theme component: 611
  manifest hashes/privacy checks and Agent self-test pass. Frozen Agent IPC
  confirms saved team 2 keeps its name/other weights while updating one choice;
  native drag and paid zero-input cases pass using installed resources.
  `build/packaged-theme-replay-verification.json` and `build/theme-package-integrity.json`
  retain evidence. The GUI was not opened, no game input was sent, and game
  PID40196 remains HIGH 12288 vs inspected controller MEDIUM 8192.

## Experimental native deployment preparation

- Added a separate opt-in preparation task using saved team order, with explicit
  standard-order persistence. Count must be recognized, agree with all local
  ordinals and match the desired prefix before each next click. No 0/1 fallback,
  reset or battle-start input. Unconfirmed selections are not clicked again.
- Actual Maa production graph passed ten derived cases including saved/preset,
  resume, already complete, wrong order, missing count, paid, stuck, missing badge
  and unconfigured. Small standalone digits missed by full-frame OCR are handled
  by local `only_rec` with retained ROIs. 79 unit tests pass.
- `build/deployment-replay-verification.json` is offline evidence. Grid centers
  come from pinned Lix; badge strips are experimental, not live-validated geometry.
  Capacity semantics for overflow, actual sinner identity, Japanese rendering,
  battle start and five-floor/reward/rotation acceptance remain pending.
- Clean `ded609b` Windows development package built; 612 manifest hashes,
  private-data exclusions and Agent self-test pass. Frozen Agent over Maa IPC
  verifies ordered choice, stuck no-repeat and paid zero-input cases with saved
  team 2/name/keywords/weights preserved. Records:
  `build/packaged-deployment-replay-verification.json` and
  `build/deployment-package-integrity.json`. Three reference navigation/changed
  cover/UNKNOWN regression replays also pass. No live controller or UAC request.

## GitHub update staging

- Shared ZIP prevalidation now also refuses Windows device names/data streams,
  invalid characters, existing extraction destinations and file/directory collisions.
  The downloader accepts only one stable package/checksum pair from the selected
  GitHub repository/tag, checks metadata sizes/digests, checksum and all manifest
  files, and refuses private config/evidence roots or unlisted files.
- HTTP download failures persist safe retry state; restart during a rate-limit
  delay performs no download. Incomplete `.part` files are removed only from the
  newly created stage. Failed full archives/extracted contents remain quarantined
  with `status=failed`; neither a failure nor `staged` executes/replaces an install.
- 103 tests pass. `build/update-stage-verification.json` proves complete staging
  of the actual retained clean `ded609b` development ZIP, with its original
  hash and all 612 manifest files. Release metadata and transport were derived
  offline fixtures; no public stable Release or live network download was tested.
- Game PID40196 remains HIGH 12288 vs current Python MEDIUM 8192, recorded in
  `build/update-development-preflight.json`. No game input/GUI/UAC was requested;
  no active MaaLimbus Agent/Runner found. Full dungeon acceptance remains pending.
- See `docs/update-staging.md`. MXU update integration, actual install/rollback,
  source/asset distribution audit and public Release remain pending.

## Experimental native battle planning

- Four pinned small glyphs retain source hashes/notice; one English win-rate
  marker and local damage glyph(s) are required. Resource/defeat classification
  wins; duplicates/missing markers and Japanese resources refuse input.
- Seven actual Maa derived cases passed: plan/stuck each exactly one P, five
  negative cases zero input. A fresh changed frame/Neutral OCR observation is
  retained, but plan/coverage/turn/victory/clear remain false. No Enter/EGO/mouse
  action; an unchanged page is not retried. 112 unit tests pass.
- Three navigation regressions passed from retained normalized Maa frames,
  with source mapping in `build/battle-navigation-regression-refs/provenance.json`.
  The replay helper avoids double resampling these images (`--prepared-frames`);
  raw reference handling is unchanged. UNKNOWN remains zero input.
- `build/battle-plan-replay-verification.json`, `docs/battle-planning.md` retain
  offline scope. Live glyph/ROI/skill coverage, Japanese UI, EGO/survival, turn
  execution and victory/map return are unverified; MirrorHard still stops at entry.
- Read-only `build/battle-development-preflight.json`: game PID40196 HIGH12288,
  current Python MEDIUM8192. No UAC/game input/GUI/live task was started. Latest
  frozen development ZIP remains `ded609b`, not this battle-planning code.

## Packaged battle planning refresh

- Clean `8b309b8` development package built with 619 manifest file hashes,
  private-root exclusion and actual frozen Agent self-test passing. Maa IPC
  installed production graph passed four derived cases: normal/stuck one P each,
  resource/unsupported JP zero input. Normal frame Neutral text retained; plan,
  skill coverage, turn, victory and clear assertions remain false.
- `build/battle-package-integrity.json`, `build/packaged-battle-replay-verification.json`
  and `build/windows-package-latest.json` point to the new package. No GUI/game
  input, UAC, installation replacement or public publication occurred.
- New ZIP also passed isolated offline staging with all 619 hashes/ZIP checksum
  checked; `build/update-stage-verification.json` now describes `8b309b8`. Metadata
  and transport are derived fixtures, not published-release/download evidence.
- All verification Agent children exited; CIM found only game PID40196/parent18536.
  Read-only `build/packaged-battle-preflight.json` still records game HIGH12288 vs
  controller MEDIUM8192. Full five-floor/reward/rotation acceptance remains pending.

## Reference control profiles and actual native UI

- Clean `08c2adc` package: 622 manifest files and frozen Agent self-test pass.
  Its four actual Maa IPC regressions pass with keys 1/1/0/0; no game controller.
- Compared MaaEnd `850e5fa` PI source and Lix `431b432` input defaults/launcher.
  Window/background/foreground combinations now match MaaEnd, with the existing
  `windows` name retained. CLI reads the same PI configuration. 114 tests pass.
- Opened the actual unmodified MXU executable. Native screenshots confirm the
  generated Don Quixote window/title icon, Chinese labels, all three controller
  choices and the five current task entries. Language and log retention survive
  restart. UI smoke actions only dismissed welcome/onboarding and opened the
  task picker in the bound MaaLimbus window; no task was added or started.
- `build/native-ui-verification.json`, `evidence/runtime/native-ui-chinese-check/main-frame.png`
  and the actual package debug logs retain display evidence. GUI PID52748 is
  still open; no Agent/Runner is alive. This proves UI display, not live game input,
  team settings execution, update installation or the complete MirrorHard loop.
- Fresh game identity remains PID40196 HIGH12288; GUI MEDIUM8192. Game is
  minimized with 0x0 client area; FramePool/Background capture attempts failed.
  Both access-denied and empty-window evidence are retained, not reduced to a
  speculative single cause. No new UAC or game input was sent.
- Full five-floor combat/reward/rotation integration and real-game acceptance
  remain incomplete. FGO was not reopened. New PNG branding does not change the
  executable's embedded Explorer icon; the running MXU window uses the PI icon.
