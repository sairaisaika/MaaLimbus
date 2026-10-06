---
type: Project
title: MaaLimbus
tags: [project, maaframework, windows-native, limbus-company, mirror-dungeon]
---
# MaaLimbus

MaaFramework Win32 controller + ProjectInterface V2 + MXU + Python Agent.
Goal: Hard Mirror Dungeon floors 1–5, verified rewards, saved-team rotation and repeat;
then budgeted Enkephalin conversion/refill, mail and daily missions. English/Japanese.

## Latest continuation: 2026-10-06 01:05 local
- The real entry chain is now established by three authorized single clicks on MuMu:
  map node click -> **node info panel** (`Clear Rewards` + `Enter`, scene `NODE_PANEL`)
  -> `Enter` -> **pre-battle team page** (`Preset #1 / Zilu/Zigong`, `2/12`,
  `To Battle!`, scene `PRE_BATTLE_TEAM`) -> `Battle!` -> **combat HUD** (`WAVE`/`TURN`
  corner + `Win Rate`/`Damage`, scene `BATTLE_HUD`).
- The user authorized pressing `Battle!` exactly as the page showed. Evidence:
  `evidence/runtime/map-probe-20261006-000748/`,
  `evidence/runtime/map-panel-enter-20261006-000900/`,
  `evidence/runtime/map-settle-20261006-000930/`,
  `evidence/runtime/team-page-battle-20261006-010230/`. Each step used the gated probe
  (nonce in `build/map-probe-authorization.json`), one click, no key, foreground
  unchanged.
- New/updated: `map_vision.pre_battle_team_page()`+`battle_target()`,
  `battle_vision.battle_hud()`, scenes `PRE_BATTLE_TEAM`/`BATTLE_HUD`,
  `tools/team_page_battle.py`; 157 tests pass. Not claimed: any turn, skill, damage,
  victory, floor clear, reward or rotation. Android touch battle control is still not
  implemented and the Windows `P`-key path stays forbidden on Android, so the battle
  is parked for a decision.

## Prior continuation: 2026-10-06 00:20 local
- Two user-authorized bounded clicks on MuMu established the real entry flow.
  (1) One click at sampled target (997,452) inside the node requested at (1005,465)
  opened the **node info panel** (`Clear Rewards`, `85` reward icon, `Enter`), not a
  battle: `evidence/runtime/map-probe-20261006-000748/`. `map_vision.node_panel()` /
  `enter_target()` now identify that page (exactly one `Clear Rewards` plus exactly
  one `Enter` in their own bands) and the agent promotes it to scene `NODE_PANEL`.
  (2) One click on that panel's `Enter` (enter_box 1668,780,124,63; sampled target
  1705,815; delay712ms) reached the **pre-battle team / identity selection page**, not
  a battle: `Preset #1 / Zilu/Zigong`, twelve identity cards with two `SELECTED`,
  `Total Participants 2/12`, `To Battle!` —
  `evidence/runtime/map-settle-20261006-000930/`. The production classifier reported
  `TEAM_LIBRARY` for that page, so its scene identity is still open. Both clicks used
  the gated probe (nonce in `build/map-probe-authorization.json`), one click each, no
  key, foreground unchanged; 156 tests pass.
- Open and deliberately untouched: the team page's preset-to-saved-team mapping and
  the rotation ledger's `index2` (0-based, the fifth team) continuation. No preset was
  changed and `To Battle!` / `Clear Selection` were never pressed. No floor clear,
  battle, reward or rotation is claimed.

## Prior continuation: 2026-10-06 00:05 local
- Live MuMu verification of the map identity, read-only first and then through the
  real pipeline. The game is still on `Exploring Floor 1 / To be Cleaved` (7548
  Starlight, 600 Enkephalin). Actual Maa OCR on a fresh MuMu capture and on the
  retained `231221/terminal.png` both give scene MAP, floor1 and pack `To be
  Cleaved`, with the header box scaling exactly1.5x between1280x720 and1920x1080:
  `build/map-live-crosscheck-verification.json`. `tools/map_live_observe.py` ran the
  new `MapObserve` pipeline node (DirectHit + `limbus_map_observe`, registered in
  `tools/run_native.py`) through an `Maa AdbController` with `Null` input and
  recorded route `current_position_not_proven`, `next_node` null, zero input:
  `evidence/runtime/map-live-20261006-000159/result.json`.
- Offline replay of that same node passes on the map frame and fails closed on the
  pack page with no input: `build/map-observe-replay-verification.json`. Node
  identity, current-position proof, floor routing, battle, floor clear, reward and
  rotation remain unproven; route stays an explicit refusal until a live frame
  proves a current position and an unvisited node. No previous input was repeated
  and no pack was dragged again.

## Prior continuation: 2026-10-05 23:45 local

- Map recognition repaired offline as required after231221. `src/maalimbus/map_vision.py`
  identifies the map page from the `Exploring|Before Entry Floor 1-5` header plus its
  pack line only; `agent/recognition.py` promotes that to scene MAP and
  `ThemeObservation` now records `theme_map_postcondition`, selected true only when the
  fresh header names the pack this run planned. Actual Maa OCR replay over the retained
  `evidence/runtime/live-20261005-231221/terminal.png` identifies MAP (pack page stays
  THEME_PACKS) and the replay controller sent zero input:
  `build/map-frame-replay-verification.json`. 153 Python tests pass (145 before).
- Route reading is deliberately an explicit refusal: the retained floor1 frame has no
  provable unvisited node, so `route_decision` returns `current_position_not_proven`
  and records no target. Node identity, floor routing, live continuation from the stopped
  session, floor clear, reward, rotation and re-entry all remain unproven. No device
  input was sent in this continuation and no previous input was repeated.

## Prior continuation: 2026-10-05 23:13 local
- Actual native downward Swipe selected To be Cleaved and reached the floor1 map.
  `evidence/runtime/live-20261005-231221/terminal.png` visibly shows Exploring
  Floor1 / To be Cleaved, party portraits and connected route nodes. Process60476
  stoppedconfirmed. Scene UNKNOWN triggered the bounded boundary; no further input.
- `tools/verify_real_theme_drag.py` now intercepts native Maa Swipe over the retained
  230455/frame-0001.png: real case1 downward drag, missing mode/header/Refresh and
  changed-cover OCR uncertainty0 drags. Unchanged post-frame never proves selection.
  `build/real-theme-drag-verification.json` retains the report. Terminal frame mode
  OCR was below threshold; do not lower thresholds to force it. Local mode OCR
  robustness and native map/routes must be repaired offline before next live input.
- Next implement floor1 map recognition/routing on231221 retained frame. No floor
  clear, battle, final reward, rotation or reentry evidence. Preserve all progress.

## Prior continuation: 2026-10-05 23:05 local
- Current authoritative frame: `evidence/runtime/live-20261005-230455/terminal.png`.
  Fresh native read-only proof confirms HARD floor1 theme packs; task stopped.
  Both free initial gifts are owned, validated by Owned labels plus catalog icons
  in224916. Extra gift search was refused without purchase (225222/225439).
  Mode switched once from Normal to Hard in230146; fresh230455 resolved pending.
- Pack selection has not happened. User confirms the card must be dragged downward.
  Existing native Swipe uses an inset randomized start/end and480–680ms duration;
  next validate its geometry on this actual1920x1080 frame before bounded input.
  Current cards: To be Cleaved, Faith & Erosion, The Forgotten. All three local
  Lix configured weights are10; no pack preference has been invented.
-145 Python tests pass. Actual/derived replay evidence is distinguished. Android
  battle input rejects Windows P-key action until a verified touch target exists.
  No floor clear, final reward, rotation or next entry is proven. Module budget0
  remains pending. Do not repeat previous grace/gift/search/mode transactions.

## Prior continuation: 2026-10-05 22:36 local
- Read-only current MuMu capture222911 revalidated the gift page and target package.
  Native223048 opened Bleed category. Native223230 selected Wound Clerid; fresh
 223418 verified title, highlighted row1 and1/2. Native223506 selected Little and
  To-be-Naughty Plushie; fresh same-session row/title/count proof verified2/2.
  Native223639 submitted the exact two selections and reached the first
  `E.G.O Gift GET!` modal (Wound Clerid), confirmed stopped. Latest actual frame:
  `evidence/runtime/live-20261005-223639/terminal.png`.
- Next: acknowledge each explicit free gift receipt with retained name/postcondition,
  verify actual Hard difficulty and floor1 entry. Do not repeat initial Commit:
  private `initial-gift-progress.json` retains selected1,2 and commit_pending.
  `GIFT_GET` blocks the underlying gift page; incomplete receipt modal is unknown.
- Maa group/pick/proof/commit replays include changed icons and missing counter,
  foreground/profile/title/selection negative cases; no device input in replay.
  Full suite143 passed before receipt veto; latest12 vision/callback tests and real
  Maa retained receipt observation pass. No floor, battle or final reward evidence.
- Private grace/gift progress JSON is excluded from Git as well as packaging.

## Star stage: 2026-10-05 22:27 local
- MuMu Maa-native entry/team-confirm/level-warning -> star selection -> initial
  E.G.O Gift page verified with retained actual captures. Current stopping point:
  `evidence/runtime/live-20261005-222652/terminal.png`, 0/2 gifts selected.
- User's final Lix zero-based grace choice is 1,3,4,6, no Enhance. Actual Maa
  selections showed available107 ->97 ->77 ->47 ->7. Base costs10+20+30+40=100.
  Extra remaining-starlight conversion was explicitly disabled and visually proved
  (unchecked box, converted Cost0). Confirmation entered the gift page. Owned
  starlight was7541 in the confirmation; no final resource settlement claim.
- Imported seven whitelisted team profiles from user's local Lix configuration;
  rotation5,4,1,6,2,7,3 and deployment orders preserved. Highest-level keyword
  identity selection policy exists with tests; native filter/paging/selection and
  MXU controls are still pending. Never substitute the policy test for live proof.
- Full Python suite143 passed; actual Maa star-selection/entry/checkbox/confirm
  replays passed including zero-input negative cases. Last task confirmed stopped;
  no floor, battle, reward, rotation or repeat-run success yet.
- Next: native initial gift selection with real postconditions, five-floor flow,
  reward budget (modules remain0/pending), native automatic formation and MXU,
  cached Windows packaging, and FGO error options/Release without reopening FGO.

## Development contract
- Read this file and docs/design.md before changes. Preserve existing work.
- Maa owns screenshot/input and bounded Pipeline scheduling. Pure Python ranks choices;
  Agent returns recognition boxes and state updates. Do not import LALC's controller/runtime.
- Crop stable text/edges; record normalized ROI, locale, source commit and frame provenance.
  Dungeon artwork, season number, currency amount and full-screen background are not anchors.
- Stop on unknown, defeat, expired session or unconfigured resource consumption; save evidence.
  Configurable error behavior defaults to leaving the game open. Never infer completion from task status.
- One controller, bounded session, finite node hits; random timing stays within configured limits.
- Retain source/license notices. No credentials, account screenshots or private configuration in releases.
- Do not claim five-floor success without each floor, reward and rotated-team postcondition.

## Acceptance
See docs/acceptance.md. No live dungeon completion has been verified yet.

## History
- 2026-10-05: User switched priority to MuMu after cancelled Windows UAC.
  Added bounded Maa AdbController CLI and shared lease/read-only probe. Actual
  Maatouch navigated HOME to Drive to mirror entry; tutorial overlay blocks entry.
  Source home and outlined-menu OCR replays pass original/changed-art/negative;
  128 Python tests pass before tutorial guard. No floors/rewards/spending/rotation.
  Latest live sessions/evidence: live-20261005-214739, live-20261005-215020 and
  adb-probe-20261005-215059. Both tasks stopped confirmed. No FGO launch or UAC.
- 2026-10-01: Switched idle native MXU to d14d119 after the old GUI exited.
  Actually displayed twelve deployment choices, changed positions1/3 and verified
  persistence after normal restart. Actual saved options resolved against installed
  PI passed frozen-Agent IPC derived deployment, retaining another team/preferences.
  One unchecked task, disconnected, auto-run false; no game input/UAC or clear.
- 2026-10-01: Added twelve PI deployment choices with atomic complete/unique
  saving. Native derived replay exposed a Python exception escaping the Maa C
  callback and continuing old-order clicks; all app callbacks now return explicit
  failure and latch the Agent closed. 125 tests and 17 deployment replays pass,
  including six callback faults with zero input. Clean d14d119 package has 622
  hashes/self-test, nine frozen deployment IPC cases and four battle IPC
  regressions passing. Old GUI remains 08c2adc; no game input or clear proof.
- 2026-10-01: Matched MaaEnd window/background/front Win32 profiles and added
  generated Don Quixote native icon plus Chinese UI. 114 tests, clean 08c2adc
  622-file package/self-test and four frozen-Agent IPC regressions pass. Actually
  opened MXU and verified icon/controller/task labels in native screenshots,
  retaining logs. Game remains minimized 0x0 and HIGH; no game input/UAC or clear.
- 2026-10-01: Added experimental native one-shot battle planning using pinned
  small English UI/damage glyphs and Maa ClickKey P. Fresh frame/risk text is
  diagnostic only; no Enter/EGO, retry or victory claim. 112 tests, seven actual
  Maa derived battle cases and three retained-frame navigation regressions pass.
  Live planning, turn submission, JP and full five-floor integration remain pending.
- 2026-10-01: Added isolated GitHub update staging with checksum/manifest checks,
  persisted download rate-limit backoff and partial cleanup. Shared Windows ZIP
  prevalidation rejects reserved names, streams and file/directory collisions.
  103 tests and full offline staging of the retained 612-file development ZIP pass.
  No installation/execution, MXU update button or public-release download proof.
- 2026-10-01: Added experimental native deployment preparation with saved order,
  explicit standard-order preset, adaptive observed count and per-click local
  ordinal verification. Ten actual Maa derived graph cases and 79 tests pass.
  Stuck/unconfirmed choices are not clicked twice; battle start remains pending.
- 2026-10-01: Added fixed-glyph/title theme-pack recognition, saved team weights,
  PI preference choices and bounded native drag. Seven actual Maa derived
  production-graph replays pass; 68 unit tests pass. Corrected OCR edge padding
  and independent custom-parameter option nodes. No live theme/map proof; no UAC.
- 2026-10-01: Built first local Windows development package with unmodified MXU,
  Maa and frozen Agent/Runner; fixed installed roots/import-time native library
  paths. 57 tests and actual packaged Agent IPC reference/unknown replays passed.
  Manifest/privacy checks passed; no live game input or new UAC. Full dungeon,
  desktop UI and release audit remain pending.
- 2026-10-01: Reworked Chinese/English README against pinned MaaFramework
  structure, added direct build/interface references and truthful feature scope.
  Distinguished the project's existing AGPL choice from MaaFramework LGPL;
  retained third-party licenses, added the incorporated GPL v3 text and documented
  unresolved artwork distribution rights. No change of third-party licensing.
- 2026-10-01: Audited MaaEnd permission-required Win32 and LALC RunAs startup;
  corrected PI permission flag and added ordinary UAC/bounded CLI launcher with
  separate logs. Actual UAC request was cancelled; no new controller/input proof.
  Added current-thread 30-minute usage-recovery heartbeat, preserving full goal.
- 2026-10-01: Imported 332 pinned public gift icons/keyword groups with file hashes
  and source paths; added local floor-gift ownership/candidate recognition and
  Maa ranking targets. Five actual Maa derived OCR/Click replays pass, including
  paid/blocked zero-input cases; 48 tests plus 3 navigation/6 team regressions pass.
  No live acquisition/quota/next-floor claim. FGO error option is locally installed
  with all nine configs preserved; GUI exit and public release remain pending.
- 2026-10-01: Replaced unbounded live connection/resource/stop waits with finite
  public Maa job polling and a monotonic whole-session deadline. Timeout and
  interruption stop once; failed stops remain unconfirmed and retain the lease
  until process exit. Technical completion never marks a dungeon clear. 43 tests
  pass. Read-only identity refresh still shows HIGH game / MEDIUM controller;
  no live input attempted.
- 2026-10-01: Native entry OCR replay corrected for the retained `Mirro` reading;
  changed covers and unknown frames passed actual Maa replay. Identified supplied
  team frame as Sinners library, implemented bounded native selection and fresh
  header/row verification, with six replay cases (derived switch, no live deployment).
  Atomic profiles/ordered five-floor reward checkpoints and GitHub metadata/cache
  recovery implemented; 39 tests pass, including cross-process controller exclusion.
  Win32 screenshot works; live input is blocked
  by HIGH game / MEDIUM controller integrity. CLI and GUI task entries now reject
  mismatched privileges. Full hard dungeon and desktop packaging remain unverified.
- 2026-10-01: Recovered empty repository and running Windows game. Pinned/read MaaFramework
  cc5fef6 and LALC 431b432; inspected four user reference frames. Native design and evidence gates started.
