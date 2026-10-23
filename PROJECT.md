---
type: Project
title: MaaLimbus
tags: [project, maaframework, windows-native, limbus-company, mirror-dungeon]
---
# MaaLimbus

MaaFramework Win32 controller + ProjectInterface V2 + MXU + Python Agent.
Goal: Hard Mirror Dungeon floors 1–5, verified rewards, saved-team rotation and repeat;
then budgeted Enkephalin conversion/refill, mail and daily missions. English/Japanese.

## Current continuation: 2026-10-12 the reward successor and the receipt that could never be booked
- October12 board order stands. Card2/card3 were proved live: `pi-20261012-135557`
  walked MAP→NODE_PANEL→PRE_BATTLE_TEAM→DEPLOYMENT→BATTLE_HUD→BATTLE_RESULT→GIFT_GET
  (the first real live win) and died on `floor_gift_receipt_successor_not_proven`; the
  renamed duplicate was fixed in `ac8940d`, and `pi-20261012-151818` is the post-fix
  loop — it recovered the booked receipt (`floor_gift_receipt_recovered`), fought a live
  battle to wave 6/8, took a real floor gift, and then stopped on the **same** reason one
  page later, so the first fix was not the whole defect.
- That second stop is now fixed, and it was in the successor rule itself:
  `runner.unselected_reward_successor` tested two of its four anchors by exact
  membership, and the live reward page prints its counter on one of those lines —
  `Selectable 0/1` — so `'Selectable' in texts` was never true. Every anchor is a
  substring test now, matching the `Confirm`/`Cancel` anchors that already were.
  The retained frame `pi-20261012-151818/frame-0178` proves it: `reward_state` reads
  `{'chosen': 0, 'required': 1}` and the successor proof is
  `{'count': {'chosen': 0, 'required': 1}, 'title': 'Select Encounter Reward Card'}`,
  which is exactly the value the runner hands the transaction (runner.py:2320, 2336,
  2344). The older retained reward frame splits `Selectable` and `0/1` into two tokens,
  which is why the offline tests passed while the real page stopped the run; the new
  tests rebuild the merged shape from that frame
  (`tests/test_gift_receipt_settling.py`), and `window.py` already knew the merged form
  (`tests/test_window.py:897`), so the runner anchor was the one blind spot.
- The successor rule reading is only half of that stop: the receipt itself could never be
  booked once the game left the notice page. `runner.py` attempted retained-evidence
  recovery only on a fresh `GIFT_GET` notice, and `_resolve_floor_receipt` called
  `observe_receipt` with no successor at all, so the settling path accepted five anchors
  while the recovery path accepted one. The live `pi-20261012-151818` receipt
  (`pending` kind `receipt`, title `Phlebotomy Pack`, proof `frame-0177.json`,
  `commit_sent` true, `completed` false) would have stopped any resumed run on the
  `REWARD_CARD` page it is standing on. Both paths now read the page through one rule
  (`floor_gift_transaction.RECEIPT_SUCCESSOR_PAGES`,
  `runner._receipt_successor_offers`), and the post-condition matches the page: a notice
  successor must attribute the next commit, any other accepted page must have closed the
  receipt. Replayed on the real files, `frame-0178` takes the live state from
  `completed False / pending receipt / receipts 0` to `completed True / pending None`.
  The new runner test also caught a second defect in the same step: `runner.py:2131`
  booked a receipt intent from the loose middle-band reader on **any** page with a commit
  outstanding, and the real reward page prints `2~3 E.G.O Gift` into that band
  (`frame-0002.json`, box `[602,591,154,28]`, 0.981), so the uncaught `ValueError` would
  have aborted the next step; the call is now limited to an outstanding commit, never a
  page that just booked its own receipt, and an unprovable intent stops the run as
  `unverified_floor_gift_receipt_intent` before any input. Suite `1447 passed, 1 skipped`
  (`tests/test_gift_receipt_settling.py` 12, including a control that keeps the receipt
  pending on the same frame with its reward anchors stripped).
- The identity teacher finally has its assembly and the twelve-slot semantics:
  `pre_battle_identity.identity_report`, `slot_row`, `learned_references`,
  `agrees_with_saved_team`, `agrees_with_saved_order`, wired into the runner as
  `runner.pre_battle_identity_evidence` and the `pre_battle_identity_report` event with
  the `identity_sha` state key — one reading per distinct frame, bound to that frame's
  own pixel hash, no input, `detector_read=False`. A deployment seat comes from the
  **printed order badge**, never from the grid position: the retained frame seats Hong Lu
  in grid slot 5 under badge 1, so a grid reading would report a false contradiction.
  `learned_references` labels an emblem only where the caption teacher already resolved
  it, which is the only route into a labelled reference store.
- Bands measured, not assumed: over 1878 retained PRE_BATTLE_TEAM frames the skill line
  sits 183..196 below the card origin, the printed title 204..230, and a level band
  161..199 or 218..219, so `CAPTION_WINDOW` moved 185→200 and `LEVEL_WINDOW` 205→222.
  The real reading is 12/12 measured with 3 resolved (Faust #10212, Don Quixote #10313,
  Hong Lu #10613) and 9 named gaps; `frame-0009` is a NODE_PANEL and reads 0 measured /
  12 missing. Suite `1445 passed, 1 skipped`; the two controller-lease failures recorded
  in `1b360f5` were the global `%LOCALAPPDATA%/MaaLimbus/controller.lock` held by a real
  running app (`lease_path` redirects every `controller.lock` there) and clear when no
  app is running.
- Still required: a live run whose journal carries `pre_battle_identity_report` (the
  installed app predates the wiring), the GET-overlay acknowledgement bound to a real
  purchase, and a full floor 2→5 run.

## Previous continuation: 2026-10-09 interactive settings and star resume
- October12 user requests settings audit and script-owned Team22 Burn+Tremor
  Mirror validation with corresponding sinner E.G.O loadouts/self-label NN.
  Actual fresh TEAM_LIBRARY independently reads #22 and sidebar #33–40, confirms
  forty slots. Expanded native source options/global/profile/queue/Lux checks to
  forty; independent queue-target test and native22/40 Resource replay passed,
  929Python61.04s/1symlink skip. Current runtime preflight is NOT ready:
  incomplete inventory, absent identity/EGO executors, untrained/off model and
  prior scope unsettled; build/team22-runtime-readiness.json. No game equipment,
  entry or resource input. docs/team22-validation.md records acceptance and UI
  findings. User opened installed settings; elevated MXU makes helper input
  ineffective. Project UI patch uses normal privileges for MaaLimbus.exe while
  preserving explicit Win32 administrator restart; real Rust build pending.
  Keep installed running app unchanged until a verified safe replacement.
- Latest October11 index supersedes the initial184-entry checkpoint below.
  Normal browser read of HuiJi Data:Personalities.json succeeded despite direct
  HTTP403; revision145235 has189 playable IDs/one NPC9999 excluded/no duplicate.
  Imported five missing IDs and cross-referenced public EN titles, all189 EN/ZH
  aliases available; five JP aliases remain missing. HuiJi Buffchoose.tabx
  revision145587 has188 identity system flag rows. Explicit empty fields for
  Rodion10917 stay unknown; Don10315 lacks a system row, not guessed. Source
  attribution/CC BY-SA4.0 and derived-table hashes retained. New index separates
  Wiki flags from128 older static facts. Exact account reconciliation now129
  owned IDs/78 unresolved observations across12 real pages, completeFalse.
  12focused/923fullPython61.36s/1Windows symlink skip passed,
  build/wiki-owned-inventory-full-tests.txt. No new device inputs for this import.
  Full account text/end coverage and trained/evaluated Mirror model remain open.
- October11 box clarification: box is owned identities per sinner, not bounding
  boxes alone. Full revisioned personality index/account reconciliation and
  Mirror self-label learning are the finishing priorities. New identity-index
  has184 playable IDs with exact EN/JP/ZH titles;128 have older static facts,
  remaining keyword facts are null. Current-source completeness remains false;
  Wiki JSON403 and old static mirror revision are recorded, never called full.
  Maa-native Owned checked/ALL unchecked templates plus unique sinner headers
  validated all12 actual galleries. Ordinary Click opened inventory; the earlier
  detail view was returned via its native-matched arrow, not repeated holding.
  Known guide close/back and original/successor JSON/PNG intent binding retained.
  Latest private snapshot matches127 owned IDs,80 unresolved observations,
  inventory_completeFalse; no absent-ownership inference or guessed levels.
  build/owned-inventory-real-verification.json binds all12 frames and unchanged
  four game-private hashes. No equipment edits/resources/claim/rotation/Release
  or installed-app update.917fullPython61.89s/1Windows symlink skip passed,
  build/owned-inventory-full-tests.txt. Current page Gregor owned gallery, no
  active controller; full index refresh, missing OCR/scroll/end coverage and
  trained/evaluated Mirror learning remain open. Roadmap updated accordingly.
- October11 user requested Maa-native neural self-label learning, twelve sinner
  boxes and Mirror assessment, with MuMu notification before real-device work.
  Roadmap: docs/neural-learning-plan.md. Offline stage1 implemented:12canonical
  classes/game-number mapping, finite image-bounded proposals, explicit complete
  review/hash binding, episode-separated train/validation/test, YOLO export and
  actual exported-byte validation, offline YOLO11/ONNX recipe, default-off native
  Agent shadow plus12disabled DoNothing NeuralNetworkDetect nodes. No input node
  uses them. Raw Wiki JSON returned403; provenance explicitly records public
  search-index sinner names/numbers and unimported data, not a current cost rule.
  Actual Maa ONNX replay passed correct/wrong/all-class expectations and exact
  box with a synthetic constant model, not trained sinner recognition:
  build/sinner-neural-native-protocol-verification.json. Native six-task resources
  still parse.20focused/894fullPython68.46s/1Windows symlink skip passed,
  build/sinner-learning-full-tests-final.txt. Read-only retained Team7 assessment
  is progression90/100 (Hard5/victory, no payout), HP/time/causal-gift quality
  unknown, censored/strategy-training-ineligible: build/team-seven-neural-assessment.json.
  Reviewed sinner dataset currently0samples/training_readyFalse/modelFalse;
  no training, production model, device/game input, installation or Release.
  Fresh read-only MuMu foreground is Lawnchair launcher, not Limbus; private
  game hashes unchanged. Next stage requires user opening Limbus and preserving
  current page for read-only EN/JP/card-boundary/identity/occlusion sampling.
  Do not leave an unpaid page, claim or consume resources. Existing full scope
  remains open; new neural source is not part of installed/candidate packages.
- October10 clean c12960b was rebuilt as an isolated v0.1.2 Windows candidate:
  actual freeze/Agent-root self-test/Runner help terminalexit0, latest package
  build/windows-package-f76fd5f7fa2a40bc9a9299c8b324327e/release-assets,
  ZIP233535948bytes/827files/SHA9b968cb94eaf119a5903571f99dfd49ad7c17679a66aa72f621a3a597aaf1c11.
  Actual ZIP86native/17Python notices and5DLL digests match build provenance;
  eight exact public source files include Rewards/budget/receipt and latest Lux/
  MainTask preparation. Actual packaged native six routes and saved/0/5/6 budget
  nodes parse; frozen Analysis includes Rewards/Lux and no FGO module:
  build/latest-reward-lux-candidate-real-verification.json. Production offline
  stage and isolated same-version install using the older172a0d7 public package
  baseline passed installed Agent self-test, sentinel preservation and actual
  post-swap injected-failure rollback: latest-reward-lux-install-real-verification.json.
  Initial attempt to copy the running desktop failed on a locked WebView cache
  before installation. Its incomplete temporary copy is marked failed and retained
  after automatic approval rejected cleanup; not used as evidence. Verification
  instead copied only the hash-bound public package manifest, excluding runtime
  cache and private state. Desktop2a684f6/v0.1.2/private hashes and same GUI58496
  remain unchanged; no game input/Release/public download/newer-version GUI update.
  Full corresponding-source/static-dependency/artwork distribution audit and all
  unfinished tasks/JP/NN/shop/skill-order remain open.878Python/1permission skip
  previously passed; this turn changes only records, not runtime implementation.
- October10 Lux MainTask preparation now checks active Mirror exclusion before
  creating task defaults, saving a team choice, observing pages or creating an
  input device. Existing conflicting/malformed Lux intent also refuses before
  settings writes; the same team choice leaves existing bytes intact.57focused
  and878fullPython65.58s/1Windows symlink permission skip passed, log
  build/lux-preparation-full-tests.txt. Actual retained menu/native six-task
  parsing and current Team7 saved/explicit2 refusal for both Lux tasks passed
  with four real private hashes unchanged and the two absent task/transaction
  files still absent: build/lux-navigation-retained-verification.json. This is
  source-only, desktop2a684f6/v0.1.2 and same GUI58496 remain untouched. Fresh
  read-only MuMu check03:04UTC still shows FGO; no game launch/input or controller.
  Team7 Hard5/unpaid and unanswered budget stay unchanged. Stage/farm/receipts,
  mail/daily/stamina/shop/skill-order/JP/NN/public update and Release remain open.
- October10 same native GUI PID58496/window2165444 was switched to English and
  Japanese, capturing six task labels, Mirror options and Japanese independent
  software-update/device settings. UI language restored to zh-CN, tasks disabled,
  autorunFalse, no connection/Start/game action. tools/verify_native_locale_evidence.py
  audits native executable/window identities, labels, screenshot digests and four
  unchanged private game-state hashes: build/native-locale-real-verification.json.
  This is UI localization evidence, not Japanese game recognition/execution.
  Captures are original JPEG bytes; prior mistaken .png extensions were corrected
  to .jpg without changing bytes and the earlier settings hash manifest regenerated.
- Fresh actual read-only ADB foreground check now shows FGO on the saved MuMu
  address, not Limbus: build/main-task-foreground-readonly-verification.json.
  No controller, start-app or game input; FGO left alone. Team7 scope4734 retained
  Hard5/victoryTrue/rewardFalse evidence and budgets remain unchanged, but the old
  reward dialog was not freshly reverified. Do not treat the old offer as current
  screen evidence, launch/restart game tasks or replay prior inputs.
- MainTask now persists a bounded zero-input agent-result for expected controller
  identity rejection and busy lease instead of poisoning Agent callback state.
  Wrong identity still stops before observer, settings/budget or game input; a
  later explicit start can recheck the identity. All six refusal routes, busy
  lease and reuse checks passed.32focused and862fullPython66.52s/1Windows symlink
  permission skip passed, log build/main-task-preflight-refusal-full-tests.txt;
  actual native six-task resource parsing passed without device input. Source-only
  fix, desktop remains2a684f6/v0.1.2 and active GUI is not replaced. Stage/farming,
  mail/daily/stamina/shop/skill-order/NN/game JP/public updater/Release remain open.
- October10 actual installed native GUI v0.1.2 rendered in PID14156/window262340
  after the initial standard UAC wait. Computer Use captured six main tasks,
  expanded Mirror settings, independent software-update/device sections and the
  imported Team2 twelve-card order. Actual HongLu remove/re-add restored position12;
  Save displayed success and persisted the same complete order/name/Charge+Tremor.
  Actual native GitHub check returned unsupported_release_tag for maalimbus.
  No Start/connect/game input; tasks remain disabled/autorunFalse and four actual
  game-state hashes unchanged. Evidence: build/native-settings-real-verification.json
  and build/native-settings-20261010/*.jpg. Normal close exited PID14156; one normal
  relaunch created PID58496, initially waiting for standard consent60280. The
  same process then exposed window2165444; actual reopened Team2 editor renders
  all twelve saved positions matching the prior order, independently captured in
  team2-after-restart.json/JPEG. Native Team2 visual persistence after normal
  restart is verified. Keep the app; do not relaunch/replace active processes. Desktop
  remains2a684f6/v0.1.2; unpaid current5 budget remains unanswered and unchanged.
- October10 Lux reconciliation now checks fresh successor PNG identity before
  clearing pending and retains both successor digests. Missing/altered successor
  image preserves exact pending bytes without input. Invalid transaction JSON or
  non-object state stops through the executor result path before observing.
  24focused and854fullPython64.83s/1Windows symlink permission skip passed;
  actual retained menu/current-Mirror exclusion and native six-task parsing passed
  with no controller/game input. Log build/lux-successor-proof-full-tests.txt.
  Source fix is not installed; active GUI/UAC instance is not replaced. Lux
  stage/farming/receipt, remaining tasks, JP/NN/shop/skill-order/public updater and
  Release requirements remain open. FGO untouched and deferred.
- October10 clean2a684f6 local app update completed: actual freeze
  build/local-app-20261010013503 terminalexit0, distv0.1.2/modifiedMXU proof valid.
  Stage and actual installed Agent-root self-tests passed;18private file hashes
  match backup-5034a5d0558b4df2a37e971979766260. Actual installed PI/pipeline equal
  source, frozen Analysis includes maalimbus.lux_task and no FGO modules. Installed
  native experience/thread/rewards routes and default saved reward-budget node
  passed with unchanged private state: build/lux-navigation-installed-verification.json
  and build/installed-lux-navigation-native-verification.json;
  log build/local-app-lux-navigation-install.txt. No GUI/controller/game input,
  new payout or Release. Four actual source private hashes still match the earlier
  budget proof. Desktop now includes Lux menu execution but not proven stage/farm/
  GUI interaction/restart. Team7 unpaid5weekly0 budget remains unanswered. Candidate
  stays172a0d7, and all remaining scope stays open; FGO untouched/deferred.
- October10 Lux navigator now continues through independently proven Drive in
  the same invocation (maximum two menu inputs). Each input retains a distinct
  HOME/Drive report and durable original PNG/JSON byte hashes; changed/missing
  original evidence refuses pending reconciliation, and fresh Drive/preflight
  must still match. Unknown Lux stage remains pending/STOP, with no stage,
  farming, resource or clear claim.19focused and849fullPython62.09s/1Windows
  symlink permission skip passed; retained-frame two-input simulation and altered
  proof rejection passed. Native six-task resource parsing and actual retained
  PNG plans/current Team7 exclusion passed with four real private hashes intact
  and zero device/controller input. No GUI/controller is running; unpaid5weekly0
  Team7 and unanswered real budget stay unchanged. Other full-scope requirements
  remain open, FGO untouched/deferred.
- October10 experience/thread native MainTask now dispatches bounded Lux menu
  navigation using its saved team. Active Mirror runs and malformed ledgers block
  before navigation. Actual retained1920x1080 HOME/Drive frames identify unique
  Drive/Luxcavation controls at.9; task/team/frame intent is durable before one
  random bounded touch. Pending HOME-to-Drive reconciles only on a proven Drive
  menu; unknown Lux stage successor remains pending and refuses repeated input.
 17focused and847fullPython62.22s/1Windows symlink permission skip passed; actual
  native six-task resources and retained PNGhash/menu plans/current Team7 exclusion
  passed, four actual private hashes unchanged, zero controller/device input:
  build/lux-navigation-retained-verification.json. Stage selection/farming/cost/
  receipt/JP/GUI dispatch remain unfinished. This addition is source-only; desktop
  stillclean b3cb668/v0.1.2 and prior install evidence remains accurate. No GUI,
  game controller, resource consumption, new payout, build or Release this turn.
  Current Team7 unpaid5weekly0 and unanswered budget unchanged; no old input replay.
  Full scope remains open and FGO untouched/deferred.
- October9 safe local app update completed: build/local-app-20261009210545
  terminalexit0, dist clean sourceb3cb668/v0.1.2 with valid modifiedMXU proof.
  Stage and actual installed Agent-root self-tests passed;18private files retain
  exact backup hashes (MaaLimbus.backup-e4d29b134d8046c5b84aab80c7c3d929).
  Actual installed PI/pipeline equal source; frozen Analysis includes reward_task
  and reward_task_budget and no FGO modules. Installed native Resource parses all
  saved/0/5/6 choices without changing the rewards action or private hashes.
  Evidence: build/reward-task-budget-installed-verification.json and
  build/installed-reward-task-budget-native-verification.json;
  log build/local-app-reward-task-budget-install.txt. No GUI/controller launch,
  game input, new payout or Release. Native GUI rendering/interaction/restart
  remains unaccepted. Desktop now includes bounded rewards execution and budget
  choices, superseding the earlier2c12793/v0.1.1 snapshot. Published/newer updater
  delivery and full distribution gate remain open; release candidate stays172a0d7.
  Current Team7 unpaid5weekly0 and unanswered budget/private source state unchanged.
- October9 native rewards task gains explicit saved/0/5/6 module budget choices.
  Saved default does not read/write policy; explicit choice binds only the current
  verified unpaid five-floor run. Unresolved/already-sent claims, unknown caps,
  incomplete old transactions or unverified runs reject before policy writes.
  Only module cap/scope/pending change; weekly/Lunacy/refill/conversion and prior
  receipt/ledger stay intact. EN/JA/ZH task descriptions reflect Mirror payout
  support and unfinished mail/daily collection.26focused and836fullPython61.22s
  /1Windows symlink permission skip passed. Actual Maa Resource four cases and
  isolated current Team7 application passed, four actual private hashes unchanged,
  zero controller/input: build/reward-task-budget-native-verification.json.
  Real Team7 paid5 budget remains unanswered/unmodified; no game inputs or new
  payout. Native GUI interaction/restart and other task/JP/shop/NN/update/Release
  requirements remain open. FGO untouched and deferred.
- October9 rewards native MainTask now dispatches bounded Mirror payout execution
  through current-scope budget/native cost and durable input-intent gates. Full
  four-input receipt audit plus independent HOME is required before reward/return
  bookkeeping and queue rotation. Post-rotation transaction-write failure recovers
  only against exact archived event hashes; no repeated rotation or input. Missing
  runs and foreign budgets stop, and device attempts remain reported on failure.
 22focused tests and823fullPython56.74s/1Windows symlink permission skip passed.
  Actual native six-task resource parsing and retained-current-budget refusal plus
  old actual receipt-chain completion in isolated state passed with zero device
  input and four actual private configuration hashes unchanged:
  build/reward-task-offline-real-verification.json. This is source-only; native
  GUI Start/restart, live Team7 paid5 receipt and mail/daily execution remain open.
  Current Team7 Hard5 victory/unpaid5weekly0 and unanswered budget remain unchanged;
  no controller/GUI launch, installation, game input or Release this turn. Desktop
  remains2c12793/v0.1.1 and candidate172a0d7/v0.1.2. Other task/shop/JP/NN/update
  and distribution requirements remain unfinished; FGO untouched and deferred.
- October9 generic reward receipt audit replaces fixed250/Pass81 assumptions
  with unique actual numeric captions matching transaction values. Each offour
  input reports must bind scope/count/PNGhash/exactOCRcontrol/touch350–750ms;
  actual modulecost/weekly and full matching question plus independentHOME are
  required. No ledger/transaction/rotation writes.9focused positive/negative
  checks,815fullPython57.43s/1Windows symlink permission skip and actual retained
  oldTeam2 chain audit passed:
  build/generic-reward-receipt-chain-real-verification.json. This is read-only
  foundation for task execution, not a completed rewards/mail/daily task or a new
  Team7 receipt. Current5module budget still unanswered; no device inputs,
  private state changes, GUI launch, desktop replacement or Release.
- October9 clean172a0d7 candidate rebuilt with native notice gate: terminalexit0,
  Agent-root self-test and Runnerhelp passed. Full806Python65.20s/1Windows symlink
  permission skip and24focused passed before building. Actual ZIP827manifestfiles,
  233443237bytes/SHA85646f5efbaae3d1f0d98f3a40aacece587c1968ad00e2a4903851c8fe5008ac,
  build/windows-package-7fa769def4f242fbac564fa5fe37a00b/release-assets.
  Exact archive production offline stage and startupv0.1.1→v0.1.2 install/
  private sentinel/Agent-root self-test/cachecurrent check also passed.
  Actual ZIP86 MaaDeps notice hashes andfiveDLL hashes match build-info;
  build/native-notices-candidate-real-verification.json.17Python notices retained.
  Not published, no desktop replacement/GUI/game input. Complete transitive
  source/static dependencies/artwork and native GUI/restart remain open.
- October9 MaaDeps notice retention is now a Windows build gate. Fixed runtime
  and development archive hashes, five actual DLL byte identities and unique
  nonempty required component copyright files validate before output. All86
  original development copyright records/sha/member provenance are retained.
  Actual cache-based gate passed against the current candidate in
  build/native-notices-builder-real-verification.json;24focused package/notice
  tests passed. Gate source is not yet rebuilt into the current candidate;
  complete transitive corresponding source/static dependencies/artwork remain open.
  No GUI/controller/game input, real budget or state changes.
- October9 clean352a1c7 rebuilt v0.1.2 candidate with17 generated original Python
  notices: terminalexit0, Agent-root self-test/Runnerhelp passed. Actual ZIP740
  manifest files/SHAa813bcbca431bf9d791e1b1124bb741f5eec679f3b086288ce32f3fd0a33a6e6;
  build/windows-package-bfda0b4bb71b42e69b7590871bbf0a78/release-assets.
  Every generated notice in the ZIP matched its recorded hash. Real offline startup
  v0.1.1→v0.1.2 staging/install/private sentinel/Agent-root self-test/cache recheck
  passed for this exact rebuilt archive: v012-notices-candidate-real-verification.json.
  Public release/GUI restart remain unverified, desktop unchanged2c12793/v0.1.1.
  Further audit traced pinned Maa source to MaaDepsv2.12.2; downloaded runtime and
  development archives match GitHub asset digests. All five non-Maa runtime DLLs
  match retained dependency runtime bytes: native-dependency-binary-verification.json.
  Original development copyright notices retained under build/maadeps-notice-audit,
  still not package-integrated, not complete native/static dependency/artwork audit.
  No GUI/controller/game inputs, no paid claim or current budget authorization.
- October9 distribution inventory found frozen Python component notices missing
  from the actual v0.1.2 candidate. Builder now retains build Python3.13.1 and
  eight installed distribution license bundles with exact versions/member hashes.
  Actual isolated collection copied17 original notice files and verified hashes:
  build/python-runtime-notices-real-verification.json. Missing/empty/unsafe metadata
  cases and package gates passed17focused; full799Python56.25s/1Windows symlink
  permission skip passed. This is build-environment notice proof,
  not full frozen binary-origin/native dependency/artwork audit. Existing candidate
  c729294 and desktop were not modified; a future clean rebuild must include the
  new generated Python-runtime bundle. No GUI/controller/game input or budgets changed.
- October9 actual v0.1.2 candidate from clean c729294 built with exit0,
  Agent-root self-test/native Runner help and corresponding-source license gate.
  ZIP SHA256 cc1fce440d1d39055a1adbda833a03669a3895e77b12765591a665c1df09df64,
  722 manifest files. Actual startup_update with retained offline release/asset
  transports discovered v0.1.2 over v0.1.1, staged and installed the real archive,
  verified the installed Agent and preserved private sentinel. A second check
  used cache/requestedFalse with no repeated installation. Independent isolated
  installation and injected post-swap rollback passed. Evidence:
  build/v012-candidate-real-verification.json and startup-candidate-real-verification.json.
  This candidate is unpublished; public GitHub download and native GUI restart
  remain unverified. Desktop stays source2c12793/v0.1.1; no game input or budget
  changes. Team7 Hard5 reward remains pending explicit current5-module approval.
- October9 version advanced to v0.1.2 in project metadata and native PI for a
  newer candidate than desktopv0.1.1. Builder now binds exact runtime/source/notice
  license bytes after pinned ZIP hashes, rejects missing/duplicate/changed members
  before extraction/freezing, and records provenance in build-info.20focused
  package/export tests and native six-task parsing passed.795fullPython56.66s/
  1Windows symlink permission skip passed; actual cached pinned archive gate passed in
  build/v012-pinned-source-license-verification.json. This does not complete the
  separate transitive dependency/artwork audit or public GUI update acceptance.
  No game inputs, resource budgets or actual reward transaction changed.
- October9 current Windows candidate rebuilt from clean eaef7b8 with modified
  MXU proof, pinned upstream sources and all latest task settings. Actual build
  terminal exit0/staged Agent self-test/native Runner help passed. ZIP233192565
  bytes/722manifest files/SHA256ccd99b98891be262c2dd83cded3dd1352d78f89a2d95bd772760e7792388042e;
  build/windows-package-c8cd87104e8c473ea88dc36f687faf6f/release-assets.
  Runtime/source/retained MXU and Maa license bytes match independently in
  native-source-license-actual-verification.json; complete distribution audit
  remains open. Project source companion matches actual latest runner/options/PI.
  Production updater staged actual ZIP through offline retained transport; isolated
  installed Agent-root verification/private sentinel and injected failure rollback
  passed. build/latest-candidate-real-verification.json, update-stage-verification.json
  and update-install-verification.json. No desktop replacement, GUI or game input.
  Candidate stillv0.1.1, same as desktop; not a newer-version updater acceptance,
  not publicly published or uploaded to replace the old draft. Need a newer
  version and remaining distribution/GUI checks before public update E2E.
  Team7Hard5 unpaid budget question remains unanswered, resources unchanged.
- October9 Mirror battle auto-assignment task setting now routes saved/win_rate/
  damage/observe through an independent inert node into actual Runner settings,
  CLI and page planner. Defaults retain Win Rate; Damage requires its own proven
  button, never falls back to Win Rate. Observe refuses battle START and assignment.
  START still submits an already assigned turn in the two automatic modes, no
  victory inferred. Existing OCR thresholds and input/successor gates retained.
 85focused plus retained-frame fake Runner observe/no-input test passed. Actual
  native six-task resource parsing preserves other options with damage selection.
  Team7 retained093211/frame0001 proves independent WinRate/Damage caption boxes;
  three plans/missingDamage rejection in mirror-battle-retained-frame-verification.json,
  zero device input. Full regression initially exposed three old six-option fixtures;
  corrected fixtures and final790Python passed/1permission skip.
  Source-only after desktop2c12793 installation; new setting GUI/liveDamage remain
  unverified. Individual skill-order editor remains open. No paid input/Release;
  Team7Hard5 unpaid budget question still unanswered.
- October9 latest desktop installation completed from clean2c12793:
  build/local-app-20261009153206 and local-app-reward-preferences-install.txt.
  Staged and actual installed Agent-root self-tests passed.18private files retain
  exact backup hashes (MaaLimbus.backup-180ebf347364451586e9d1a19df1967a).
  Updated verifier accepts explicit log/source/work paths; actual installed PI
  and Mirror pipeline equal source; frozen Analysis contains no MaaFgoHelper.
  build/reward-preferences-installed-verification.json. Actual installed native
  Resource resolved all three independent removal controls, no controller/input
  and unchanged private hashes: installed-preference-removal-native-verification.json.
  No GUI launch/render/save/restart acceptance, no paid game input or Release.
  Team7 remains unpaid with current5module budget unanswered; no resource policy
  changes. New City/garden/cost/scopedreward/removal source is now installed.
  Installed frozen launcher check-only made an actual GitHub check: public tag
  maalimbus remains unsupported semver, no download/install. Immediate retry
  uses cached requestedFalse deadline; updater cache/result files alone update.
  This does not accept newer public-version installation/restart.
- October9 Mirror preference removal: task editor adds independent priority-gift,
  blocked-gift and theme-rule removal controls (default keep). Known selected
  entries are removed in the same validated atomic profile save as additions;
  simultaneous add/remove of the same rule refuses. Active-team changes refuse,
  other entries, systems, deployment, stars and other teams remain preserved.
  Actual native Resource independently resolved all three controls and isolated
  add/remove persistence passed with zero controller/input.19 focused tests and
  native six-task parsing passed. Final783Python passed56.12s/1Windows symlink
  permission skip (build/mirror-preference-removal-full-tests.txt). Source-only:
  installed GUI rendering/save/restart
  not accepted, desktop remains67c71d6; no install or Release. Current Team7
  completed Hard5 remains at unpaid5modules/weekly0, budget answer still pending.
- October9 paid-reward offline continuation: current five-module/zero-weekly
  offer now prepares under an explicit matching scope and maximum; old six/one
  remains supported. Obscured Net Amount is not required as a wallet balance.
  Completed prior transaction can roll into preserved history only with completed
  payout/home receipt-chain metadata; pending, same or previously recorded scope
  rejects. New validation failures leave old state byte-identical. Receipt amount
  is the unique positive high-confidence number in the exact acquired-reward
  layout, never fixed250; acknowledgements still do not credit payout.
  tools/verify_reward_rollover_offline.py passed against retained native current
  offer with isolated policy/state and exact old transaction preservation. Real
  policy/transaction/ledger hashes unchanged, zero device inputs. Actual current
  receipt/confirmation layout and payout remain unverified; budget question still
  unanswered. Final777Python passed55.70s/1Windows symlink permission skip;
  build/reward-rollover-full-tests-final.txt. No install, GUI launch or Release;
  desktop remains67c71d6.
- October9 10:08local actual47324 terminal69inputs at reward cost gate, final
  battle victory→complete summary→RUN_REWARD_DIALOG. Independent fullsummary
  frame0311 and modal0312/0313 PNGhashes verified by
  tools/verify_team_seven_floor_five.py, build/team-seven-floor-five-real-verification.json;
  scope4734/team7 ledgerfloors[1,2,3,4,5]/victoryTrue/rewardFalse. Actual five
  floors cleared, final rewards not received. Current offer5modules/weekly0/3
  allOFF, quotedStarlight142/BPXP30/projection50/EXP100 are not receipts.
  Prior six-module authorization in user-mirror-settings remains scoped to
  oldd7c149...; current scope not authorized. User async question asks this
  round5modules or retainpage, no answer yet; no paid input/toggle/GiveUp/ToWindow.
  Runner now correctly reports budgetpending for foreignscope. Current native
  cost Bcrop originally -5 .890937 refused; signed-crop experiment abandoned.
  Narrow Bcrop1444,790,36,50 proves5 .994387 while independentA5 .9982,
  currency/sign1.0 and weekly0 .999095; thresholds unchanged. Six cases each
  current5/old6 positive/negative native passed zero input,29focused passed.
  Full761Python passed56.94s/1permissionskip. Desktop67c71d6 unchanged/noGUI/controller;
  paid action/receipt logic still needs current five-module offer support and
  explicit new scoped budget before live claim. Original completed paid6
  transaction and oldreceipt remain untouched; full software scope stays open.
- October9 08:35local actual28824 terminal120inputs at selected reward1/1;
  bounded window ended normally, not a timeout restart. Fresh30532 confirmed
  that already-picked reward once, reached four trial gifts0/2 and stopped
  before gift input. Existing complete title/compound-trial parser ranked
  Metronome220 and ThornyRopeCuffs290 under savedTeam7 heuristic; each selected
  once0→1→2. Selectonce/twofullnamedGETackonce reached SELECTFLOOR5.
  verify_team_seven_floor_four.py hashes bothreceiptPNGs and exactfloor5/scope4734,
  build/team-seven-floor-four-real-verification.json; ledgerfloors[1,2,3,4].
  No repeat reward pick/gift input. TyrannicalPride floor5 dragged once; early
  map missingproof STOP retained pending. Freshreadonly independently proves
  MAPfloor5/TyrannicalPride zero input; latest bounded120step report
  build/team-seven-floor-five-after-theme-live.json/tool66369 continues and
  resolves pending without repeatSwipe. Check actualprocess/result before next
  controller; active only observe/no distreplacement/timeoutrestart. Floor5
  and finalpayout still unverified; newmodulebudget0pending, no resource spending.
  Desktop67c71d6/source fix not installed; full software/UI/remaining scope open.
- October9 07:40local garden fix full758passed/1permissionskip57.17s. Fresh
  actual59116 stopped zero input because OCR changed a closing quote to an
  apostrophe; complete words now tolerate only surrounding quote punctuation.
  Final80focused and3native positive/negative cases passed; original fresh
  quote-variant frame also passed offline. Actual51548 Refuse once reached
  EVENT_RESULT, build/team-seven-garden-refuse-quote-fixed-live.json,1input;
  no healing/gift/floorclear claimed. Generic legacy plan reason says reward
  row, but the garden_refusal_choice journal note records actual bounded refusal.
  Fresh bounded120step report build/team-seven-floor-four-after-garden-live.json
  continues from result; tool25782. Verify actualCIM/result before new control.
  Active only observe, no repeat Refuse/themeSwipe/oldGET or desktop replacement.
  Ledger[1,2,3], new modules0pending/lunacyrefillconversion0; source fix not
  installed desktop67c71d6. Full software/remaining floors/payout goal open.
- October9 07:34local actual43468 terminal53inputs at EVENT_CHOICE/frame0134,
  no_event_choice_observed; not floor4clear. Refuse/Accept texts were complete
  but excluded by the eight-character row filter. Added short-label extraction
  plus independent exact garden dialogue/question/Choices/two-control gate,
  all .9. This exact offer uses bounded Refuse, no inferred healing/gift value;
  unsupported Accept/Refuse questions STOP.79focused and3actual native retained
  positive/missing-question/missing-control cases passed zero device input.
  Existing factory Yes/No policy remains separately gated. No duplicate theme
  Swipe or completed gift inputs, ledger[1,2,3]; full regression in progress.
- October9 07:11local City supplement/sourcefdeb723 pushed;756Python passed
  55.19s/1permissionskip,16focused and3native retained cases passed. Actual
  City/SmokingGunpowder picked once each0→1→2, Selectonce and two complete named
  GET acknowledgements reached SELECTFLOOR4. verify_team_seven_floor_three.py
  binds scope4734/team7/receiptPNGhashes/exactfloor4; ledgerfloors[1,2,3],
  build/team-seven-floor-three-real-verification.json. No repeat gift inputs.
  Line2 floor4 dragged once; early unproven map STOP kept pending. Freshreadonly
  independently proves ExploringFloor4/Line2 at high confidence with zero input.
  Latest bounded120step PID43468,parent45500/python.exe/tool94394, report
  build/team-seven-floor-four-after-theme-live.json continues; startup resolved
  theme pending without anotherSwipe. Active only observe; no concurrent
  controller, timeoutrestart or desktop replacement. Floor4/finalpayout remain
  unverified. No new module/lunacy/refill/conversion spending; desktop67c71d6
  still lacks City supplement, real GUIinteraction and all software gaps open.
- October9 actual36328 terminal102inputs at four trial gifts0/2, no gift input.
  Local catalog lacked For You Who Love the City. Independent observed-title
  supplement binds actualframe0285 SHA83ddf622... without pretending upstream
  provenance, artwork, keywords or complete healing text. Exact title only;
  truncated/changed titles and missing trial numbers refuse. Native retained
  positive and two image-negative cases passed zero device input;16focused
  passed. Current heuristic selects City then SmokingGunpowder (97.5/177.5),
  no invented healing bonus. Floor3 remains unverified until actual receipts
  and exact next-floor successor; previous floor1–2 receipts are not replayed.
- October9 06:39local localfreeze build/local-app-20261009103412 terminalexit0;
  modifiedMXU proof reused valid, installedsource67c71d6 clean, staged/actualAgent
  selftestTrue,18privatefiles preserved in backup-e062c25efd8a498e90254c87515d0e92.
  tools/verify_latest_local_install.py independently verifies installedsourcePI/
  mirrorpipeline,privatehashes,actualAgentselftest and frozenAnalysis noFGOmodules.
  build/latest-local-settings-installed-verification.json. Latest previously
  source-only task preferences and header/map fixes now installed, not yet native
  GUIrender/click/save/restart accepted. No GUIlaunch or resource consumption.
  Fresh bounded120step PID36328,parent60516/python.exe/tool25901, report
  build/team-seven-floor-three-after-perversion-live.json continues from MAP;
  active only observe, no replacement/concurrentcontroller/timeoutrestart.
- October9 06:35local actual66592 terminal28inputs at centered freePerversion,
  firstarrival zero gift input. Freshknownsinglefree identity/controls/outlines
  allowed pickonce, Selectonce/fullnamedGETackonce to MAP. completedTrue/
  pendingNone; shared read-only receipt/hash audit passed for both thisPerversion
  and earlierTomorrow, build/team-seven-perversion-real-verification.json.
  Not floor3clear; ledger[1,2]. ActualCIM finds no GUI or controller now, so safe
  local installation of newer settings/Agent can proceed with private backups
  and actualinstalledAgent selftest. Do not replay completed gift inputs.
- October9 06:08local actual66504 terminal33inputs at MAPframe0102,
  map_click_opened_no_panel after bounded candidates; not floor3clear. Retained
  VainPride offered icon(1087,409) only survives bright component threshold, was
  omitted by ring-only bright fallback. Added bright compact icon candidates
  behind path/rings, with wide dense icons before small badges, still requiring
  an actual NODE_PANEL successor. Initial ordering regression was corrected;
  59map/route/progress tests passed. Idle full751passed/1permissionskip56.36s,
  followed by final priority adjustment and59focusedpassed9.82s. The earlier
  two canonical-lock tests separately passed idle(2passed0.37s). No gameplay stop
  was forced for testing. Fresh readonly showsfloor3/VainPride; actual bounded
  node-resume one rejected candidate then bright icon opened NODE_PANEL.
  build/team-seven-bright-node-resume-live.json proves actual forward input,
  not floorclear. Current bounded120step PID66592,parent43576/python.exe,
  tool45509/report build/team-seven-floor-three-after-node-live.json continuing;
  check process/terminal before next controller. Ledger still[1,2]; no resource
  spending or desktop replacement; all software and full-goal gaps remain.
- October9 05:38local actual10396 terminal55inputs at floor-end four-card0/2.
  CrownOfRoses and CurriculumVitae each picked once0→1→2; Selectonce and two
  fullnamedGET acknowledgements reached SELECTFLOOR3. verify_team_seven_floor_two.py
  binds scope/team7/previousfloor1/twoPNGhashes/fulltitles/exactfloor3; ledger[1,2],
  build/team-seven-floor-two-real-verification.json. No repeat gift inputs.
  VainPride theme dragged once; early stalefloor2 then realfloor3 map stopped
  because wholeOCR combined ExploringFloor and omitted3. Narrow fallback now
  accepts one exact high-confidence joinedlabel OR the existing two separate
  labels, still requires packheader plus independent digit and fullcaption crops
  agreeing at .9. Six realnative replay cases (oldfloor5/currentfloor3 and
  missingdigit/missingFloor negatives) passed zero input. Freshreadonly independently
  proves MAPfloor3/VainPride, build/team-seven-floor-three-header-fixed-readonly.json.
  Latest bounded120step PID66504,parent62028/C:/Python313/python.exe/tool39384,
  report build/team-seven-floor-three-header-fixed-live.json; no repeatedSwipe.
  Check current process/result before another controller. Desktop remains old
  d0d5352 while GUI alive; no replacement/resource/FGO input. Full Python result
  retained in build/floor-three-header-full-tests.txt:749passed/1symlinkskip,
  one Windows installation-lock test could not acquire the canonical lock already
  held by actualrunner66504. This is not an all-green full suite; recheck that
  lock test after the real controller exits, never stop gameplay just for a test.
- October9 05:05local actual33496 terminal61inputs at centered free
  Tomorrow'sFortune GIFT_PICK/frame0177, no gift input. Current fresh single-free
  title/Acquire/Refuse/Select/outline gates allowed one pick, then Selectonce and
  one fullnamedGETack to MAP. Transaction completedTrue/pendingNone; read-only
  tools/verify_team_seven_tomorrow.py checks actual receipt title and both PNGhashes,
  build/team-seven-tomorrow-real-verification.json. This is an in-floor free gift,
  not floor2clear; ledger remains[1]. Bounded120step continuation PID10396,
  parent65236/C:/Python313/python.exe, tool98870, report
  build/team-seven-floor-two-after-tomorrow-live.json. Check actual terminal/result
  before next controller; no repeated pick/Select/GET. No resource consumption,
  desktop replacement or FGO input. Installed UI/latest task fields remain open.
- October9 02:08local actual30736 terminal103inputs at four-cardGIFT_PICK0/2,
  zero gift inputs. Fresh020501 picked BrokenRevolver then BloodSweatandTears
  onceeach0/2→1/2→2/2, matching savedTeam7 Rupture preference and fully parsed
  visible trials (bounded heuristic, not universal optimal). Subsequent Select
  once/two fullnamedGET ackonce each reached THEME_PACKS/SELECTFLOOR2.
  verify_team_seven_floor_one.py checks current4734/team7, both receipt PNGhashes,
  fulltitles/completedtransaction and exactfloor2 successor before recording
  ledgerfloors[1]. build/team-seven-floor-one-real-verification.json. No pending
  gift input remains; do not repeat these picks/Select/GET. Floor2 bounded120step
  continuation report build/team-seven-floor-two-progress-live.json started;
  check actual process/result before any next controller. No new paid resources,
  desktop replacement or FGO input. Newrun final payout remains unverified.
- Team7 initial tray now progressed: saved formation_keywordsRupture and priority
  1,2,3 justified one Rupture group opening, then BarbedLasso once0→1. Native OCR
  split FluorescentLamp into same-baseline words after that selection; fixed only
  the existing title-band fragment join, second-line/low-confidence full-name
  negatives and two actual retained layouts pass. FluorescentLamp once1→2.
  Selectonce and two namedGET ackonce each; last successor was transientUNKNOWN,
  preserved pending, freshzero-inputGIFT_SEARCH exact headers/0of3 proved next
  page. verify_team_seven_initial_receipts.py checks scope/threeinputtargets/
  touchdelays/PNGhashes/twofullreceipts before completing already-sent ack, no
  repeat. build/team-seven-initial-receipts-real-verification.json. SearchRefuse
  once→GIFT_SEARCH_FORGO, Confirmonce→transitionUNKNOWN; fresh zero-input report
  team-seven-after-search-current-readonly independently shows THEME_PACKS.
  Do not repeat either. No paidSearch/module/refill/conversion input.
  Bounded120step runner PID30736/parent24284/C:/Python313/python.exe started from
  that page; report build/team-seven-after-search-progress-live.json, tool71745.
  Check its actual terminal/result before any next controller; alive is not clear.
  Final750Python74.91s/1symlink skip passed,7initialfocused passed. Fullscript
  tests prove no gameplay completion; current floors[] unchanged.
- Mirror preference editor now owns per-saved-team additive gift allow/block and
  preferred/blocked theme selection with explicit weight.332gift/95theme catalog
  identities populate native dropdowns. Independent inert nodes collect all
  choices; whole-edit validation precedes a single atomic profile save. Preserve
  roster/system/star and existing preferences; changed active-team preferences
  STOP, identical reapplication is allowed.23focused and actual Maa resource
  seven-choice/isolated two-profile/active-rejection verification passed with no
  controller or device input; build/mirror-preferences-native-verification.json.
  Source only, not installed UI/render/persistence acceptance. Final748Python
  passed83.54s/1Windows symlink permission skip; recorded in
  build/mirror-preferences-full-tests.txt. Battle-card editor still open.
- Final modified MXU artifact native build terminalexit0. ExecutableSHA5f0541fdcfce8ff63937e74a5aa2f1d3162817719c1d0d184fc7b3bfa9c5aa39 and complete corresponding sourceZIP SHA c9837cfe5b80fbcc9c13a1633306db17b0e3c2acadabf0788475d4f64d43e8d4 validated. Local assembly installed clean d0d5352 exit0/stage+actualAgent selftestTrue, preserved18privatefiles/backuppath, build/local-app-interactive-install.txt and interactive-client-installed-verification.json. Frozen installed launcher check-only genuinely returns currentv0.1.1/publictagmaalimbus unsupported/cached requestedFalse, noinstall/download/input; ISO retry timestamp corrected and18focusedpassed. No public Release or installed settings interaction claim.
- Same actual GUI PID22484 exactdist/MaaLimbus.exe now has top-level handle10360354/titleMaaLimbus v0.1.1; previous no-window/consent observation is stale. Tasks disabled/autoRunOnLaunchFalse independently verified. Kept this process, no restart/replacement; installed native settings render/save/restart/manual-check click acceptance remains open. Standard UAC remains user-only.
- MaaLimbus is prioritized. FGO source, configuration, ledger and release remain in their own repository; no FGO app/game work in this continuation. User withdrew quota checks.
- Actual Team7 STAR stall was an untouched current-scope zero-budget entry stub, with no active controller. Explicit existing user-launch choices2,4,5,7/cap100 were adopted once, with original state/config/frame hashes and backup; unknown or spent transactions reject adoption. Real native inputs bought each once,116→106→86→56→16, Enter once, then confirmation once with conversion unchecked/cost0. INITIAL_GIFTS first-arrival STOP is deliberate, with zero gift input. build/star-entry-resume-real-verification.json checks six touches,350–750ms, PNG hashes and unchanged ledger860b8fbd...; current scope4734/team7, no new floor clear. Do not rerun adoption or star inputs.
- Project-owned MXU overlay replaces twelve-dropdown formation with a twelve-card click-order editor, clear/reorder/save and name/system fields; bulk global validation still applies before Mirror, preserving other build metadata and rejecting active-team edits. Browser preview demonstrated exact Team2 order/HongLu last and save result; it is not installed native persistence evidence.
- Software updates and device connections are separate MXU settings sections. Explicit GitHub check uses the launcher check-only path, existing persistent cache/limits and current-version metadata, without installation/restart/game input. Device settings reuse native MXU connection controls. Modified native source is built against pinned MXU2.7.1; custom executable acceptance requires executable/overlay/patch/full corresponding source hashes. A build or preview is not installed GUI acceptance.
- Final732 Python checks/1 Windows symlink skip passed84.54s;38 focused and4 artifact tests plus2 click-order Node tests passed. First native build finished exit0; reproducible modified MXU artifact rebuild is still running, inspect its actual terminal result. Desktop remains94475d8 until safe closed-app replacement; no public Release of these changes.
- Mirror task UI currently exposes team modes and nested starlight sources/priorities/caps. Battle strategy, theme/gift editors and the four unfinished daily/lux/conversion policies still need real task integration; a task entry does not count as support. Full goal remains active.

## Historical continuation: 2026-10-08 global build settings
- Mirror task star rules now own follow-team/follow-task/auto plus a per-build editor, 10 Lix0..9 basic choices and explicit caps (task default0). Actual ledger team resolves before runner purchase state; auto freezes one current-price/available-balance affordable priority subset before input, preserving scope/pending across windows. Unknown prices, missing team cap, enhanced imports and active-team edits reject; no Enhance/conversion/seasonal optimality claim. 27focused and715Python56.79s/1symlink permission skip passed, native independent patches/isolated two-team save resolution passed with no controller/input, PI0problems. build/mirror-starlight-native-verification.json. Source only: desktop94475d8 and draft5151009 do not contain this feature, GUI/render/restart/live-auto purchase remain open. No private profiles/ledger/resource consumption modified; isolatedGUI18516 still alive, do not replace/restart it.
- Actualv0.1.1 candidate5151009 clean built719files/ZIP887f594e.../Agent selftest passed.703Python56.42s/1skip passed. VersionedZIP+SHA256SUMS draft uploaded and GitHubdigest matches; draftnotpublished. Real offline stage and isolated actualdesktopv0.1.0→v0.1.1 install/private sentinel/failedvalidationrollback passed. Desktop unchanged. IsolatednewMXU childPID18516 HIGH12288 actualpath/visiblewindowtitlev0.1.1/readonlywelcome screenshot verified; no GUI input, no mainUI or publicdownload acceptance. Bootstrap34480 exited by official elevation lifecycle, do not restart or replace activeisolatedapp. build/versioned-candidate-real-verification.json. Sourceledger4734 hash unchanged/gameSTAR retained.
- Preparingv0.1.1 updater-compatible Windows candidate: clean-source build, versionedZIP/SHA256SUMS, manifest/private-source validation, launcher and pinnedMXU/Maa corresponding source archives.51focused passed before addingMaa source requirement; no publicRelease/install claim. Candidate still must be built, staged, installed/rollback-tested and distribution gaps inspected. No game/controller input.
- Final696Python52.96s/1symlink skip passed.94475d8 conditional-UI local assembly finished exit0/selftestTrue,17privatefiles retained; reused unchanged50b9ae2 liveAgent, rebuiltlauncher/assets/docs. Actual installedAgent root/data binding selftest passed, queue-count5 includes exactlyfive children, old active4734 ledgerhash unchanged. GUI14460 closed normally before replacement; no GUI/controller alive. build/six-task-conditional-installed-verification.json. Six-menu visual proof50b9ae2 remains valid; newly conditional child display still awaits freshGUI validation. Public newerRelease/realupdate install remains open.
- Installed six-task50b9ae2 freeze finished exit0/selftestTrue,17privatefiles retained. Same GUI PID14460 eventually rendered (MEDIUM8192/WebView) without restart. Actual six-menu screenshot and Mirror three modes visible, QA-created Mirror card disabled and saved-mode restored, autorunFalse, no game connection/Start. build/six-task-gui-real-verification.json hashes five frames. New conditional queue child nesting displays only selected count;16focused/native0input/PIpassed, source only until closed-app update. Final692Python55.01s/1symlink skip before this UI-only nesting passed.
- Native learning preparation added: reviewed labels must bind actual verifier image hashes, run scopes split together, duplicate leakage/changed/external evidence rejects.4focused passed. Actual oldHard5 summary + newTeam7 STAR manifest has2reviewed samples/2episodes and insufficient class coverage, training_readyFalse/model_trainedFalse/productionFalse. No NN training or input enabled; docs/learning.md follows official Maa ONNX Classify/Detect protocol and keeps page/budget/receipt gates independent.
- Six main entries now replace standalone diagnostic/menu tasks: open_game/mirror_loop/experience/thread/rewards/stamina. MainTaskAction owns shared lease and real controller preflight; mirror applies global edits and calls same native runner using parsed Maa action.param. Native resources six routes plus independent lux defaults7/2 passed zero input; PI0problems. Experience/thread resolve saved profiles but stage/cost policy remains unimplemented; rewards/stamina also capture and FAIL without input, descriptions explicitly say development.691Python52.40s/1skip and47focused passed; subsequent native-parameter/Windows adapter focused9passed.
- Real OpenGameTask PID20860 terminal: existing MuMu foreground independently verified, no start_app/touch sent, terminal STAR_GRACES screenshot retained and active4734 ledgerhash unchanged. build/open-game-main-task-real-verification.json. Android cold start persists once-only launch intent and needs actual foreground, unknownpending no retry; Windows only verifies an existing connected game, no UAC bypass. Coldlaunch/GUI six-menu dispatch still unverified. Dist stilldd8cc4f pending newfreeze.
- Final freeze dd8cc4f completed exit0, staged and actualinstalledAgent selftestTrue,17privatefiles preserved including binding. Fresh installedexe selftest independently proves runner_root=actualapp and private_state_directory=D:/fgoa/MaaLimbus/config; active4734 entered ledgerhash retained. build/private-state-installed-verification.json. No GUI/game launch or task dispatch; source clean/pushed, six main tasks/public newerRelease install remain open.
- First shared-state freeze a49ab83 completed exit0, staged/installedAgent selftestTrue and17privatefiles preserved, binding retained. Further audit found PRE_BATTLE_TEAM profile access still bypassed binding and runner frozen resource root used package extraction; both now resolve canonical runtime paths. Standalone binding test no longer relies on another test importing Agent first. Final683Python54.30s/1symlink skip,17focused and11package/preservation passed. Agent selftest now checks actual runner root/registry and resolved private directory; final freeze pending, do not dispatch stale installed Agent. GUI remains normally closed/no game controller.
- Private-state split repaired: data_directory resolves an explicit local-only user-data-root binding; all Agent profiles/progress/preferences and config-relative run ledger share the same source config. Invalid/missing/chained/linked bindings STOP. Actual GUI57260 closed normally, fresh CIM no app/controller; tools/bind_local_state.py retained both private folders in unique backup and bound development app to config without altering active4734/team7. build/private-state-binding-verification.json.683Python54.73s/1symlink skip and25focused passed. Existing frozenAgent still needs refresh; GUI dispatch/restart not yet proved. No game/resource input.
- Real next-team/reentry now proved: paidHard5 team2 receipt remains intact, queue rotation5 selects7.190502 HOME→Drive→entry/loadout4inputs;190556 Team7 clicked once, freshheaderTEAMS#7 .996528.190636 Confirm once→LEVEL_WARNING;191203 warningConfirm once→STAR_GRACES;191246 zero-input freshSTAR records entered. Newscope4734bfe68803421c8d261dccbc9120be/team7/floors[]/rewardFalse, no new resources. build/rotation-reentry-real-verification-20261008.json binds actualPNGhashes/inputtargets and priorpaidreceipt. NewrunHardmode still unproven until theme page; no new clear/payout claim.
- Found and fixed old reconcile abandoning an empty preparing run at each new loadout window, creating stale report scopes a235/81e and latest4734. Keep original abandoned/history and explicit backup; tools/verify_rotated_entry_intent.py verifies original1Confirm/nativeTeam7/target/timing/beforeafterhash/freshwarning then adopts already-sent intent into4734, no repeatinput. New RunStore phasepreparing/entry_pending/entered, once-only durable entry andwarning confirmation, independentSTAR/initial/theme/map successor. Emptylegacy needs migration; pending refuses retry/discard.679Python56.05s/1symlink skip,30focused passed. Current realSTAR no controller alive, no starpurchase; dist stillb78109e until software exits/newfreeze.
- GUI PID57260 actually appeared by same-process observation, MEDIUM8192. Own-window screenshot startup-updater-settled proves main unconnected/notasks; startup-updater-global proves native GitHub auto-update section and20Team global panels visibly rendered. No restart/no gameinput by UI QA. New saved-order dropdown andsix-task dispatch still pending.
- Sourceb78109e pushed/clean and freeze build/local-app-20261008225819 actually finished exit0, installedAgentroot selftestTrue,15privatefiles retained. Desktop shortcut now targets launcher/MaaLimbusLauncher.exe. Actual bootstrapPID22352 exited/copied outside helper, real GitHub check persisted ETag/deadline and opened official MXUPID57260. Actual latest tag is non-semver `maalimbus`: initial startup result incorrectly called it current; new source reports unsupported_release_tag,12focused passed, fresh cache-only readonly result corrected without install/game input. build/startup-updater-actual-verification-20261008.json distinguishes actual request/process from unverified GUI/new-version install. PID57260 remains alive with no matching top-level window observed, no restart. New status fix not yet frozen; don't replace dist until GUI exits. Source full672Python52.89s andnative/PI passed before the focused status correction. No Release/new-version E2E acceptance; six main tasks still open.
- Latest local build/local-app-20261008224855 actually finished exit0, sourcebbe4026 clean, staged and installed Agent self-tests passed;15privatefiles preserved in unique backup. New mirror single/rotation UI installed, not yet visually dispatched. No game controller or new run entered.
- Added native global GitHub automatic-update selector and separate software launcher: copies frozen helper outside install, waits its original parent exit, reads persistent cache/deadlines, stages newer stable release only, validates/installs/rolls back before opening unmodified MXU. Default enabled, disabled makes no request. Direct MaaLimbus.exe skips this path. MXU2.7.1 built-in update skips projectv0.1.0 as debug; project version not artificially raised. Source/packaged/updater controller.lock now one LocalAppData lock; external helper excludes only its own outside-install PID from CIM guard. Final672Python52.89s/1symlink skip,34focused, native resource replay and PI schema passed. Old20-section-only test corrected for new software section. Launcher desktop/public release/new-version UI E2E not yet accepted. Six main task restructure remains open.
- New native mirror task options reference saved builds: keep ledger/single/ordered rotation, count1..20 and fixed team dropdowns. GlobalSettingsApply resolves the choice before loop entry; TaskPreferences validates saved slots, refuses active queue changes, preserves receipt history and retains idle nextteam if in new queue; loop_store uses saved preference queue. Native single/five-queue resource replay passed zero device input. 660fullPython51.88s/1symlink skip, 34focused, PI schema passed. Newly added queue UI not yet installed/visually dispatched.
- GUI startup blocker resolved by observing same PID18632: actual native window and WebView children appeared, no restart. Own-window Maa screenshots prove settings/Team2 editor shown, edit mode persisted and restoredkeep-saved, no gameconnection. After normal GUI exit, local-only seed_local_settings imported12missing private JSONs and seeded24default fields with backup, preserving user edits/source profiles. ActualTeam2 UI config order3,4,9,1,7,2,12,5,8,10,11,6; restart loaded it and file persisted, but visible imported-dropdown order still unverified. build/global-settings-gui-verification-20261008.json hashes six actual frames and explicitly distinguishes visible editor/config order. Restart PID10196 was HIGH integrity; own-window close click did not initially prove exit, no bypass/elevation/forcekill. Latest fresh CIM finds no MaaLimbus.exe, so do not treat old high-process snapshot as live. All taskenabledFalse/autorunFalse; no game input or resource consumption.
- Sourceaea57d2 pushed/clean. Actual freeze build/local-app-20261008215328 terminalexit0/stage selftestTrue/installedAgentroot selftestTrue, dist sourceaea57d2 clean/MXU2.7.1, two private files preserved with unique backup. GUI launch autorunFalse/no enabled tasks verified first; processPID18632 exactdist executable created, no owned top-level window or WebView children found yet. No new game controller/input and no repeated launch. Visual settings/restart still unverified; observe actual process before any replacement or further launch.
- Added 20 native MXU global build sections with name/system and twelve ordered sinner dropdowns. Default keep-saved does not overwrite imported builds. GlobalSettingsApply precedes MirrorLoop, validates all explicit edits before profile replacement, preserves existing allow/block/theme metadata, rejects active-team changes and duplicates. Native resource replay verifies 30 independent option patches for two teams, saved-default exclusion, no controller/device input; build/global-settings-native-verification.json. Ordinary MXU shallow action-param replacement is avoided using distinct inert attach nodes. This is source/native replay verification, not GUI restart acceptance. Main six-task layout and mirror single/rotation UI integration are still open.
- Invalid run ledger now rejects before input instead of skipping bookkeeping. Final 655Python passed/1 Windows symlink-permission skip in52.72s; 19 focused global/package/preservation passed. PI schema passed. Actual payout/HOME/rotation5 nextteam7 checkpoint below remains current; no new game input or controller.
- Corrected Windows release source/notice pin to official MXU2.7.1 commit9fa8cc51e8ff8cd89d99f3ea55fe3a7a82e6ede3, reproducible git-archive SHA B350877C03598922B14D1804923E331361ACF64534494945274B80B5D28CEC35. Previously retained2.5.1 source did not match2.7.1 runtime; no Release published.

## Previous continuation: 2026-10-08 17:35 local
- Desktop rebuild fix: make_local_app previously removed the complete old app directory, including actual MXU config. It now checks CIM/project/path/controller lease, retains unique backup, copies/hashes all private folders, validates actual installed Agent root and restores old app on failure. Three focused preservation/rollback/running-app tests and final647Python53.10s passed/1symlink-permission skip. Actual freeze build/local-app-20261008213753 terminalexit0/stage selftestTrue and installedAgentroot selftestTrue, source8d28d24 clean/MXU2.7.1. Two actual MXU private config hashes preserved, backup retained, build/local-app-settings-preservation-20261008.json. No destructive cleanup of old app/stale staging; GUI restart/version still pending.
- Latest user instruction removes Codex quota checks entirely. Continue native development; do not buy/reset credits. User explicitly says continue current reward: scoped current6modules authorized, existingweekly1 unchanged, other resourcebudgets0. Six main tasks requested: open_game/mirror/experience/thread/rewards/stamina. Global build records own sinner order/systems; mirror owns single/rotation selection, battle/theme/gift preferences, luxcavations reference default saved builds. See docs/task-settings.md; do not retain old quota/budgetwaiting instructions as current.
- Actual payout now acquired:172241 Claim once (output-only KeyError step missing fixed; no retry),172338 exact weekly question Confirm once,172353 full RewardsAcquired250,172516 receiptack once followed by PassLevelUp,172543 stablePassLevel81,172624 passack once thenloading,172705 freshreadonly HOME. All native touches randomwithinbox350-750ms, four durable per-control intents. No repeatedClaim/Confirm/toggles. Currentmodules64visible atHOME but no valid beforewallet proof; modulebalance_delta_verifiedFalse. Oldpartial841 behindmodal explicitly corrected to unknown: NetAmount summary is not wallet, correction retains originalvalue/proof.
- verify_final_reward_receipt.py independently hashes acquired/pass/HOME PNGs, checks four inputreports/current scope/actualtouch, and completes paid transaction. build/final-reward-real-verification-20261008.json payoutTrue/HOMEreturnTrue; realHard5 run team2 now receipted, savedrotation5/nextteam7, activeNone. This is saved queue advancement, not visually confirmed nextteam or reentry; both still pending. Do not launch readonly with run-store merely to observe HOME: it would start a new ledger run.
- Added freshpreflight CLI --reward-action claim/confirm/receipt/pass: exact scope6/currentnative6modulesweekly1, actual question/full receipt/PassLevel+XP+numericLevel, durable intent before touch. Confirmation never credits payout; separate actualreceipt+independentreturn verifier does. Before modules/starlight not displayed stay unknown, never fake balances.30focused paidtransaction tests and644fullPython53s passed/1Windows symlink-permission skip.
- TaskPreferences model references global ProfileStore rather than copies;7tests prove5teamcycle/singleteamre-edit/luxdefaultsharedbuild/invalidsavepreservesold. Model not yet connected to MXU six-task/global-settings UI; do not claim frontend complete. CurrentPI task menu still legacy diagnostics until propernative entries/interactive settings implemented. Native upstream PI global_option/setting schema locally read; use that for MXU integration, not Lixfrontend.
- Updater ecdf1ed install/rollback guards now retested after PID1236 GUI exit: latest build/update-install-verification.json real isolated retainedpackage swap/Agent rootselftest/privateconfig preservation and injectedverificationfailure rollback passed. No desktop replacement by updater/publicRelease proof/MXUupdatebutton yet. Dist now source8d28d24 clean with actual installedAgentroot verification. Fullgoal remainsactive: actualnextteam/reentry, GUItasks/settings/updateractivation, shopdaily, JP/Win/PI E2E, nativepersona, trainedNN, Windows/FGORelease remainopen. FGO paused/no game launch.

## Previous continuation: 2026-10-08 17:20 local
- Continued independent updater work while modulebudget question6/18/0 remains unanswered. Hard5 realclear/victoryTrue/rewardFalse unchanged, no paid Claim/toggle/Confirm or resources/game input; FGO unchanged/paused/no launch. Desktop Agent package remains e1a1171/MXU2.7.1, no new freeze/Release.
- Added update_install closed-app transaction + tools/install_update.py: revalidate stage/public manifests/PI identity-version, reject unsafe roots/source checkout/linked paths/downgrade/unresolved old journal; CIM identity check, external shared controller lease, sibling candidate/retainedbackup, nested config/evidence/logs/build hash preservation. Public files and actual installed Agent resource-root self-test required; failure restores old directory and keeps failed candidate. Crash/rollback ambiguity blocks retry rather than deleting backups. MXU button/public Release/actual desktop UI restart still unverified.
- Isolated retained development package filesystem replacement and actual Agent self-test succeeded; injected post-swap validator failure restored previous directory/private sentinel. build/update-install-verification.json retains real isolated evidence, not desktop update or published release proof. Final624Python52.92s passed/1symlink permission skip;13focused passed/1skip, real shared Windows lock exclusion passed.
- Subsequent stricter CIM guard found MaaLimbus.exe PID1236 with no ExecutablePath. Actual verify_update_install stopped before replacement; build/update-install-process-blocked.json. Did not terminate GUI, bypass identity/UAC, replace dist or start game/controller. Earlier isolated proof remains historical; do not repeat install until process identity/exit is verified. Complete goal still active with payout/rotation/reentry/JP/nativepersona/GUI/shopdaily/NN/full update/Release/FGO items open.

## Previous continuation: 2026-10-08 17:06 local
- Quota37%primary37%weekly allowed; no reset/purchase. Two repos/docs/git and CIM rechecked, no livecontroller before/after freshread; FGOd9367d1 unchanged/paused/no launch. Hard5realclear remains accepted, rewardFalse, no rotation/reentry. Existingmodulebudgetquestion remains unanswered; maxmodules0/pending/otherbudgets0 unchanged, no repeatedquestion.
- Cost recognition fixed without lowering thresholds: independent exact ExplorationReward/Floor5/HARD/7of7/Claim/ToWindow/WeeklyBonuses anchors gate native modulecurrency template and deduction-sign template at.95, two digitonly_rec crops at.9 must uniquely agree, weekly0–3/3 nativecrop at.9. Assets preserve actual0458 sourcePNGhash/ROIs/templatehashes; identity comes from moduleicon, not a lone digit or giftcover. Only retained1920x1080 English layout supported; changed/JP layout staysunknown.
- Six actualnative retained-frame cases (0458/0459 positive, missingcurrency/sign/digit/title negative) passed zero deviceinput;33focused and611fullPython49.23s passed. Freshwindow170553 PID43476terminal0input stillRUN_REWARD_DIALOG; frame0001 actualnative currency/sign1.0, digit6 .933789/.953475, weekly1/3 .999948 proves visiblemodulecost6. build/final-reward-cost-fixed-current-readonly-20261008.json. This is cost recognition only, not spending approval or payout.
- Paidcontrols remain gated; no Claim/toggle/Confirm/resourceconsumption. Actual before module/starlight balances and rewardreceipt/balanceafter recognition remainopen; RewardClaimTransaction offlinefoundation notactivated. run_wiring Confirm credit removed already; no new reward_received. Full nativeGUI/JP/Windows/PI/autofilter/NN/shopdaily/updaterinstallrollback/rotationreentry/WindowsRelease/FGORelease scope remainsopen.

## Previous continuation: 2026-10-08 16:10 local
- Quota29%primary36%weekly allowed, no reset/purchase. Both repos/docs/git and CIM checked; no controller live. Real completed Hard5 run remains scope d7c1499436f647208adc50860692a5c2/team2/rotation4/floors1–5/victoryTrue/rewardFalse; build/floor-five-real-verification-20261008.json. Actual paid Claim has never been sent. Budget question6/18/0 remains unanswered; modules0/pending and other resourcebudgets0 unchanged, FGOd9367d1 paused/no launch.
- Fixed old run_wiring payout credit: RUN_REWARD_CONFIRM and RUN_REWARD_BONUS inputs now produce no reward_received event. Neither a click nor confirmation can unlock rotation/reentry. Positive ledger-only rotation fixtures explicitly supply independent receipt evidence; they are not live payout acceptance. Full595Python47.68s and44focused passed.
- New RewardClaimTransaction foundation reserves exact same-scope explicitly approved modulebudget, current known currency/cost/weekly offer and before module/starlight balances. Changed scope/offer/cost, overspend, unknown balances, unresolved priortransaction reject; claim_sent andconfirm_sent persisted before hypothetical input, restarts cannot retry. Confirm leaves pending and reward_received/completedFalse. Foundation is NOT wired to any live paid input or actualreceipt recognition. No fabricatedreceipt/creditedpayout.
- tools/probe_reward_cost_ocr.py diagnostic retainedframe0458 only native reads digit6 .985492 in1428,790,50,50 but independent75x70cost reads-6 .733909 below.9. production_gate_enabledFalse; no lowered threshold/currency assumption/cost approval. Must finish independent moduleicon/cost/balance evidence and actualreceipt recognition before enabling live paid controls, even after userbudget reply. No device input thisturn; no automaticbudget change or newquestion. Fullsoftware/updater/rotation/reentry/Release/FGO scope remainsopen.

## Previous continuation: 2026-10-08 15:39 local
- Quota24%primary35%weekly allowed, no purchase/reset. Both repos/docs/git and CIM rechecked; no controller active. FGO d9367d1 unchanged/paused/no launch. Previous144554 PID45480 terminal19:09UTC/107inputs at RUN_REWARD_DIALOG, reward_module_budget_pending, no paid Claim. This is actual terminal, not observation timeout.
- **Hard five floors now truly cleared**: actual144554 frame0457 full ExplorationComplete, DungeonProgress Floor1–5 eachHARD, lastreachedFloor5HARD, floor5 7/7 andTotalProgress100%; final battle victory→RUN_CLAIM→reward modal frame0458/0459. Independent run_summary.completed_hard_summary demands exact full summary and all five HARD columns; no inferred pending/page-alone clear. Seven actual/negative Python tests andfour actual/negative native retained-frame OCR cases passed zero deviceinput. tools/verify_floor_five_clear.py checks frame0457/458/459 PNGhashes/same run scope/team2 and actual ledger acceptedfloors1–5/victoryTrue/rewardFalse; build/floor-five-real-verification-20261008.json retainsproofs. Prior floors' receipts remain retained. No payout/rotation/reentry claim.
- Actual reward modal shows weekly1/3 (ON/OFF/OFF), Claim minus6 EnkephalinModules; offered Starlight160/BPXP75/projection50/EXP120. These are offers, not到账. Modulebudget0/pending unchanged; user budget question is pending, no paidclaim/toggle/toWindow/giveup. No new controller. Next implement scoped durable cost/claim/receipt verification offline, then only proceed after explicit actual-cost budget response; never auto-credit reward just from Confirm or module OCR without currency proof. Desktop remains nativeGUI freeze9bc4acd/selftestTrue/MXU2.7.1; new pure offline verifier does not require rebuilding Agent. All complete software/updater/JP/rotation/reentry/Release/FGO requirements remain open.

## Previous continuation: 2026-10-08 14:45 local
- Quota11%primary33%weekly allowed; no purchase/reset. Both repos/docs/git and CIM rechecked; FGO d9367d1 unchanged/paused/no launch. Previous140541 PID57492 terminal18:21UTC/63inputs at new single-free BloodyGadget Owned offer, not floor5clear. Ledger stillfloors[1,2,3,4]; theme selected1–5/pendingNone. DiskFragment pick/Select/fullGETack completed before this window, no repeat.
- Single-free observation now preserves high-confidence Owned label. Only known unselected single-free owned gift may be refused; beforeinput durable refuse_owned intent, exact current RefuseGift target. Followup requires full Continue without choosing an E.G.O Gift? question and both Cancel/Confirm labels, same scope/pending, confirm_sent persisted before input. Unknown postcondition retains pending and no repeat. No other forbidden abandon/reward controls enabled. Eightfocused tests,571fullPython48.46s passed; two four-case native actual/negative retained-frame probes passed zero device input. Initial regression affected receipt method scope, caught by full suite and corrected before confirmation.
- Actual144025 refusalonce→UNKNOWN_DIALOG stops. Actual confirmation once→short-lived old GIFT_PICK stops; fresh read-only successor REWARD_CARD0/1. tools/verify_owned_refusal_successor.py checks original input targets/touches/before PNGhashes/pending proofs/current scope and fresh successor PNGhash/exact reward controls, explicitly completes already-issued confirmation. build/owned-refusal-real-verification-20261008.json. No new gift acquisition/floor5clear/payout/rotation/reentry claim. Module/lunacy/refill/conversion0. Full scope remains open.

## Previous continuation: 2026-10-08 13:38 local
- Quota recovered0%primary31%weekly; no reset/purchase. Both repos/docs/git and actualprocesses rechecked, FGO unchanged/paused/no launch. Retained124955 frame visiblycontains5, fullframe detection missed it. Native diagnostic only_rec digit362,125,48,52 reads5 .999851; fullheader55,120,370,65 readsExploringFloor5 .999164. Production uses both .9 gates with exactExploring/Floor high-confidence labels and independentpack header; both crops must uniquely agree before replacing incompleteheader. No pendingfloor used as observed digit; blinking still boundedreadonlyretry.
- Three native cases actual/missingdigit/missingFloor passedzerodeviceinput; full563Python46.46s passed. Fresh133716 readonly realMAP/ExploringFloor5/SinkingDeluge verifiesfix with0inputs, build/floor-five-header-fixed-readonly-20261008.json. Theme pending still preserved until nextboundedrunner startup independently resolvesactualfloor5/map, no secondSwipe. Acceptedfloors[1,2,3,4], no floor5clear/finalpayout/rotation/reentry. Module/lunacy/refill/conversion0. Completegoal remainsopen.

## Previous continuation: 2026-10-08 floor-digit retry
- User confirms floor numeral can blink; new pending-theme MAP path rereads only within configured rounds/interval/deadline, no drag/input retry. Two offline cases prove later readable phase stops waiting and persistently missing phase exhausts at3observations with0inputs. Full563Python passed46.15s. Actual floor-five-blink-resume-live report PID66644 terminal with0inputs after bounded rereads, stillmissingdigit, pending retained. This did not resolve floor5; further native digit recognition must use retained frames and strict independent header/pack gates. Unverified narrow-crop experiment discarded, no synthetic digit or pendingfloor used as observation. Goal remains open, acceptedfloors[1,2,3,4].

## Previous continuation: 2026-10-08 12:38 local
- Quota87%primary29%weekly allowed; no purchase/reset. Both repos/docs/git/process identities checked, FGO unchanged/paused/no launch. Three-free description exemptions limited to complete known TrialPlanGuide ShopSkillReplacementCost and First-aidKit HPheals25%ofMaxHP clauses in each own body region and exact high-confidence owner title. Actual/unknown payment or trials anywhere else still veto. Complete four-line conditional healing grants bounded25 survivalheuristic; incomplete condition has0benefit, not predicted healing/ML. Sixnew tests,561fullPython45.05s,3native real-frame positive/negative replay passedzero input.
- tools/verify_floor_four_free_successor.py checked original120756 lastIllusoryHuntack scope/pending proof/target/touch/both PNGhashes and independentnewthreefree0/1 to complete already-issuedack withoutreinput. Pre-orderDiscount actualGETframe0003, IllusoryHunt0004; no repeated Select/GET.123646 actualFirst-aidKitpickonce;123656 Selectonce+completeFirst-aidKitGETframe0003+oneack→SELECTFLOOR5/Refresh/PackSearchframe0004.
- **Hardfloor4 realclear**: tools/verify_floor_four_clear.py verifiesthree fullnamedGET titles/PNGhashes/current scope/completedtransactions andexactfloor5successor; build/floor-four-real-verification-20261008.json recordsledgerfloors[1,2,3,4]. No finalpayout/floor5/rotation/reentry claim. Module/lunacy/refill/conversion0. No activecontroller atcheckpoint; currentfloor5theme page must passfreshmode/title/geometry beforeboundeddrag/resume. Complete scope andFGORelease remainopen.

## Previous continuation: 2026-10-08 12:09 local
- Quota83%primary/29%weekly allowed; no reset/purchase. Both repos/docs/git/CIM rechecked; no controller alive. FGO d9367d1 unchanged/paused/no launch. Previous113601 PID41012 terminal15:42:57UTC at four-card GIFT_PICK0/2/frame0136, no gift input.
- New actual ClashPower+1 and three-effect trial: former .68 lower text band omitted high OffenseLevel+2 row. Band now .66 with headings/level still separate, all complete unique components retained (maximum3). ClashPower240 conservative survivalheuristic, not game formula. Current full penalties315/605/90/280; team2 Tremor benefit40 yields ranking90/280/315/565, selectingPre-orderDiscount+IllusoryHunt. Five new tests,18focused,555fullPython45.30s passed; actual native3-case retained-frame replay passed zero device input, missing HP/clash amounts reject.
- Actual120724 selectedPre-orderDiscount andIllusoryHunt each once0/2→1/2→2/2.120756 Select once andtwo namedGET confirmations, fullreceipts frame0003/0004 retained. Lastack→newthree-free offerTrialPlanGuide/ImposedWeight/First-aidKit/frame0005. Old global trial/cost screen rejects gift descriptions Shop Skill Replacement Cost and Max HP; receiptpending retained, no repeatedack/selection. This blocker needs independently bounded effect-text vs actual trial/payment detection offline before recovery. Ledger remainsfloors[1,2,3]; no floor4clear/5/finalpayout/rotationreentry claim. Modules/lunacy/refill/conversion0. No controller active atcheckpoint, do not clear unknownpending or restart/replay GET. Fullscope remainsopen.

## Previous continuation: 2026-10-08 11:15 local
- Quota69%primary/26%weekly sufficient; no purchase/reset. Both projects/docs/git and actual CIM identities checked. Prior102111 PID6800 terminal14:43:01UTC at GIFT_PICK/frame0435, no gift input. FGO d9367d1 remains paused/unchanged, no launch.
- Perversion single free offer independently proved; 110507 picked once,110526 Select once. CONNECTING changed pixels while old offer remained, so old settling stopped early with commit pending. Fresh110924 proved full Perversion GET. Fixed only floor-gift Select settling to use remaining configured read-only rounds while offer/UNKNOWN persists; no second Select. Retained actual sequence tests cover delayed GET, exhausted wait and rejection of repeated submission.
- 111130 acknowledged full Perversion GET once, then actual REWARD_CARD0/1. Unsupported successor kept receipt pending. New independent title/Selectable/0-of-1/Confirm/Cancel gate completes only the final named receipt; page label alone cannot complete it. tools/verify_perversion_reward_successor.py verifies original scope, one input, target/touch, pending proof and both PNG hashes before read-only reconciliation. build/perversion-receipt-real-verification-20261008.json records gift completion, explicitly not floor clear.
- 111420 encounter reward picked and confirmed once; fresh111458 readonly returned MAP/ExploringFloor4/AbnormalSeismicZone. No repeated Confirm. Ledger still floors[1,2,3], no floor4 clear/finalpayout/rotation/reentry proof. Modules/lunacy/refill/conversion consumed0. Full550Python passed43.07s,8 new focused passed. Single controller currently terminal; next bounded native resume stops before any new GIFT_PICK input. Complete goal and outstanding native JP/Windows/PI/MXU/filterpersona/NN/shop/dailies/updaterinstallrollback/WindowsRelease/FGORelease remain open.

## Previous continuation: 2026-10-08 10:18 local
- Quota53%primary/24%weekly; no purchase/reset. Both project/docs/git/process identities rechecked. Prior094350 PID46216 terminal14:03:57UTC after120bounded steps/121inputs, lastturn animationUNKNOWN, no livecontroller; freshreadonly1004 provedREWARD_CARD. FGO d9367d1 remainsunchanged/paused/no launch.
- 100508 rewardpick+Confirm reached four floor3 gifts0/2, no gift input. Added complete wrapped gift titles, BasePower trial(integer,weight180 survivalheuristic), retaining all decimalHP/effects; unknownsuffix/CoinPower/missingnumbers refuse. Native three-case realframe replay passedzeroinput. Actual100754 selected MaterialInterferenceForceField andMidwinterNightmare exactlyonce0/2→1/2→2/2;100819 Select+named GET confirmations producedfullMidwinter andMaterial receipts, then a new three-choice freegift page. Missing supported successor retainedMaterial receiptpendingSTOP, no repeatedack.
- New strict three-free layout: threeknownfulltitles/Acquire plates, freshSelect/Refuse, no counter/trial/cost, measuredcolumngeometry, one complete orangeUIoutline+litSelect or allabsent+dim. Rightcard lower edge partlycoveredbyRefuse; independent visibleleftbottom segment nowmeasured, no threshold reduction. Source explicitlythree_free_select_button, not fabricatedOCRcounter. Alltitles/offer signature andbefore-input intents retained. Known nextfree0/1 offer can complete priorlastreceipt onlyafter everyselectednamedGET. Explicit originalscope/input/target/touch/PNGhash reconciliation100819 recordedMaterialack withoutanotherinput.
- Actual101324 pickedPhantomPain once andSTOP on oldoccludededge probe; pendingkept. Offline five-case actual/selected/missingtitle/refuse/outline native replay and explicit original-input/hash proof resolvedselection withoutreclick. Phantom receivesbounded15 heuristic benefit onlyfrom two complete visible1AtkWeight/+15%damage textlines; not universalstrategy/ML.101535 Select sentonce andimmediateoldGIFT_PICK stopped; freshreadonly lateractualfullPhantomGET permitted101637 oneack, no secondSelect.
- **Hardfloor3 real clear**: allthree fullnamedGET hashes+actual101637/frame0002 SELECTFLOOR4/Refresh/PackSearch verified; build/floor-three-real-verification-20261008.json recordsledgerfloors[1,2,3], gifttransactioncompletedTrue/pendingNone. No module/lunacy/refill/conversionconsumption; no finalpayout/rotation/reentry claim. Full542Python passed38.66s,14newfocused passed,3wrapped/BasePower+5threefree native caseszeroinput. CurrentTHEME_PACKS floor4/no controller atcheckpoint; nextfreshmode/card proof before boundedresume. Completegoal remainsopen floors4–5/finalreward/rotationreentry/nativeJPWindowsPIMXU/filterpersona/NN/shopdaily/updaterinstallrollback/WindowsRelease/FGORelease.

## Previous continuation: 2026-10-08 09:42 local
- Quota45%primary/23%weekly; no purchase/reset. Both projects/docs/git/processes checked. Prior091754 PID37956 terminal13:26UTC with62inputs, stopped before four-card floor2 gift selection. FGO d9367d1 unchanged/paused; no game launch. PreviousGUI eb7dc68 clean/self-testTrue verified.
- Compound trials now parse every complete wrapped clause and decimal percentage, including Damage Dealt; optional OCR comma loss cannot discard an effect. Unknown/partial/duplicate/cross-column effects still stop. Exact truncated Acquire E.G.O Gif plate is accepted alongside Gift so four columns remain independent. DamageDealt survival heuristic20 per percentage point (not game formula); prior weights unchanged. Current offer penalties155/55/240/202.5 and team2 preferences prioritize Blood,Sweat,andTears thenTomorrow'sFortune. Four native retained-frame cases passed with zero input; 31focused and528fullPython passed.
- Fresh093745 initially stopped with0inputs when OCR omitted a comma. Corrected after retained-frame offline verification, not retrying a submitted selection. Actual093859 then selected Blood,Sweat,andTears andTomorrow'sFortune each once, actual0/2→1/2→2/2 with durable intents.
- **Hardfloor2 actually cleared**: 093925 sent Select and two named GET acknowledgements. Full Tomorrow'sFortune receipt frame0002 and Blood,Sweat,andTears frame0003; final actualframe0004 independently proves SELECTFLOOR3/Refresh/PackSearch. Transaction completed/pendingNone. Old planner omitted THEME_PACKS successor and reportedunexpected_successor, stopping; fixed allowed successor without repeating any input. Explicit receipt/title/PNGhash/scope/floor3 proof recordsfloor2 inledgerfloors[1,2], build/floor-two-real-verification-20261008.json. Readonlyfreshfloor3 also confirmed. No finalpayout/module/refill/conversion/lunacy consumption or five-floor claim.
- Current gameTHEME_PACKS floor3, no livecontroller at this checkpoint. Nextstep requiresfresh nativeHard+exactknowncardgeometry, not repaint/oldcoordinates/redoGET. Fullscope remainsopen floors3–5/finalpaidreward/rotationreentry/nativeJP/Windows/PIMXU/filterpersona/NN/shopdaily/updaterinstallrollback/WindowsRelease/FGORelease. Do not shrink goal.

## Previous continuation: 2026-10-08 09:15 local
- Quota34%primary/21%weekly at this heartbeat; no purchase/reset. Both repos/docs/git and actual processes rechecked. Prior PID17456 terminal12:58UTC after34 inputs, stopped before any input on Lightning Rod GIFT_PICK. FGO d9367d1 remains paused and unchanged.
- Counterless centered single free gifts now require exact known title, Acquire plate, Select/Refuse controls, no trial/cost text, and agreement between button state and all four orange UI outline segments. Covers do not identify gifts. Multi-card missing counters/trials and JP remain refused. Native five-case retained-frame replay passed with zero device input; missing title/refuse/outline refuse.
- Actual091114 sent exactly one Lightning Rod selection, then stopped because the button was48.69 in the original conservative ambiguity band. Pending retained. Independent retained-frame repair adds four outline checks; explicit original-input/scope/target/touch/before-after PNG hashes reconciliation verified selection without another click. `build/lightning-rod-selection-real-verification-20261008.json` records it.
- Actual091508 sent Select once and the named Lightning Rod GET acknowledgement once; full receipt `frame-0003.json`, actual MAP `frame-0004.json` proves ExploringFloor2/EmotionalJudgment. Gift transaction completed/pendingNone. This is in-floor acquisition, not floor2clear: accepted ledger remainsfloors[1]. No modules/lunacy/refill/conversion consumed. Next bounded session must check current process before controlling.
- Full goal remains open: floors2–5/finalreward/rotation/reentry, native JP/Windows/PI/MXU E2E and filter/personas, trainedNN, shop/dailies, updater install/rollback/fullWindowsRelease and FGORelease. Prior clean4d09733 GUI freeze124824 self-testTrue retained until verified replacement; no public Release.
- Validation: 521 full Python tests passed (34.66s), 24 focused tests passed; five native replay cases passed with device input forbidden. Offline tests do not claim live floor completion.

## Previous continuation: 2026-10-08 08:48 local
- Quota21%primary/19%weekly atthisheartbeat; no purchase/reset. Bothrepo/docs/git/processes rechecked. FGO remainsd9367d1/paused, no game input. MaaLimbus prior64569f2 clean freeze122135/self-testTrue verified, no timeout rebuild.
- **Floor2 Hard entry repaired and real**: independentSELECT FLOOR2/Refresh/PackSearch gates native only_recHARD crop1372,48,64,38 at.9 (actual.99996), wholeHARD/II.827 remainsinsufficient. Current settledpack geometry detectsfixedclipfallback, not covercolors; same-row splitEmotional/Craving now mergedleft-to-right. Unknown stylizedfirsttitle staysunknown. KnownEmotionalJudgment selected once by neutraldefault (savedno packweights), actual084019 Swipe; firstMAPtemporarilysaidFloor1, pendingretained andSTOP. Read-only084059 provesExploringFloor2/EmotionalJudgment, startup084129 resolvedpending withoutrepeatingdrag. user-theme-transaction selectedfloors1,2/pendingNone.
- **Regular battle blocker repaired**: currentfloor2 encounter omitsWAVE entirely; fullOCR also missedturn1, so084129 sent4entry inputs thenwaited30unknown readings andterminal stopped; no newcontroller or timeoutrestart. Actualretainedframe0024 showsTURN1/WinRate/Damage. NewindependentTURN+bothassignmentcontrols gatesnative numericcrop68,90,82,40 at.9. RegularHUDrequiresactualnumericturn and bothcontrols; wave staysNone (neverfabricated1/1). Four native replaycases allpassedzero deviceinput, missinglabel/digit/buttons refuse. Native084553 thenactualWinRate+START once each submittedturn1, terminalpassed but no victory/floor2clearaccepted.
- Python510 fullpassed,21focused, nativefloor2five-case replay nowprovesnarrowHard and refusals, pipeline0issues. Finaldedup removesoldwholeHARD beforeappendinglocalone toavoidfalseambiguity; modeopposition stillvetoes. Newfreeze/live continuationactualresults mustbechecked. Currentstate mayturnanimation/BATTLE; readlatest actualsession/processbeforecontrolling. Don'tredoentry/theme/mode/graces/gifts/GET oroldpending.
- Hardfloor1/twofloor1namedreceipts acceptedunchanged; floors[1], currentteam2/rotation4 requestedorder preserved. Fullgoal stillopen includingfloor2–5/finalpaidreward/rotationreentry/nativeJP/filter/persona/ML/shopdaily/updaterinstallrollback/WindowsRelease/FGORelease. Budgetsmodules0pending, refill/conversion/lunacy0; no paidinput. Singlecontroller/randomnative touches/unknownstop/offlinefix andquiet meaningfulnotifications remainbinding.

## Previous continuation: 2026-10-08 08:22 local
- Usage recovered (primary6%/weekly17% at12:07UTC), no credit purchase/reset. Both repos/docs/git/processes rechecked. FGO unchanged d9367d1 and paused; no game launch. MaaLimbus prior freeze092857 terminal/self-test already verified, not rebuilt on timeout.
- **Hard floor1 now actually cleared**: current scope d7c1499436f647208adc50860692a5c2/team2/rotation4. Native081248 picked Golden Urn once, actual1/2→2/2. Original Dimensional Recycle Bin selection was adopted only from retained051724 exact0→1 input/target/touch and before/after image hashes; it was not picked again or credited to the new policy.
- Native081512 sent exactly Select plus two named GET acknowledgements. Actual full Dimensional Recycle Bin and Golden Urn receipts retained; last acknowledgement led to floor2 theme page but old glyph recognition returnedUNKNOWN and stopped. Offline page-identity repair plus native zero-input five-case replay and fresh081811 proveSELECT FLOOR2 THEME PACK. Exact pending Golden Urn receipt/hash plus this independently verified successor resolved the transaction read-only and recordedfloor_clear1. Proof `build/floor-one-real-verification-20261008.json`; both receipts in private user-floor-gift-transaction.json completed/pendingNone. No module/lunacy/refill/conversion consumed.
- Current actual pageTHEME_PACKS floor2, latest `evidence/runtime/window-20261008-081811/frame-0001.png`; all live PIDs terminal, no controller. **Do not Select/GET-confirm/re-enter/switch mode or redo floor1.** Current tilted pack detail glyphs and Hard glyph do not match; fullOCRHard .827 is insufficient. Page identity is proven separately by three high-confidence captions, granting no Hard proof or drag. Next fix native narrow-mode OCR and fresh tilted-card title/geometry recognition offline before resuming; do not lower thresholds or reuse floor1 coordinates. Visible packs include MagicHellBus, EmotionalJudgment, EmotionalCraving but all exact identities/drag targets still need verification.
- Runtime floor gifts now require complete unique per-column title/card/MountingTrials/EnemyLevel/effect and exact counter. Unknown/new effects, missing identity/counter, unknown pending and commit retriesSTOP. Transparent enemy penaltylevel30/offense90/defense10/damageReduction3/HP1, saved allow/keyword benefit40 and ownedpenalty60; saved blockwins. All current offers had no Charge/Tremor match, GoldenUrn35 vsZippo45 vsLithograph150. This is a conservative heuristic, not universal optimality or auto-learning.
- Persist selection and commit/receipt intents before native touch; validate+1 counter and unchanged offerings, exact full named GET and named/known successor before completion. Canonical truncatedDimensionalRecycleBi never substitutes for full actual receipt. Counterless/JP trials currentlyrefuse; shop purchase/fusion stillunimplemented. Python508 fullpassed,13focusedpassed after mode-veto assertion, pipeline0issues; native five-case floor2 replay allpassed no device input. Windowsfreeze/commit status must be checked against new actual output.
- Full objective stillopen: floors2–5/final paid reward/rotation/reentry not accepted; modules0pending, lunacy/refill/conversion0. Native automatic formation, JP/Windows/PI/MXU E2E, trainedNN, shops/dailies/updater install/rollback/fullWindowsRelease and FGORelease remainopen. Heartbeat staysactive and quiet except meaningful progress/blockers.

## Previous continuation: 2026-10-08 05:24 local
- Current game **GIFT_PICK**, actual `evidence/runtime/window-20261008-051724/frame-0032.png`, PID42464 terminal. Counter1/2, firstcardDimensionalRecycleBin selected by old default before stop-page took effect; nothing committed. OtherchoicesBlueZippoLighter/Lithograph/GoldenUrn. Their enemytrial effects are respectivelyDefenseLevel+2/EnemyLevel+1; DamageTaken-5%/Level+1; OffenseLevel+1/Level+2; MaxHP+5%/Level+1. Do not replay firstgift click or Select; nextwork must bind gift/build and freshenemy-effect ranking with durable selection/receipt proof. Catalogue canonical firstname is truncated `Dimensional Recycle Bi`; retain actualdisplaytitle for receipt comparisons. No floorclear/finalreward/rotation accepted yet.
- Native correct-order battle proceeded into cyborg factory. `050053` generic min_length8 filteredYes/No and clickedhelpertext, repeatedlyYes. Source-guide lookup and offline retained actual16/20/24 prove exactcityquestion→No. Unsupportedbinaryquestions nowSTOP; helpercaptions excluded, currentquestion and both high-confidence labels required. Actual `051115` sent twoNo in this preexisting event state; finalresult provesfactoryexploded/AllIdentitieslose30HP, not no-cost/no-loss success.
- Leftstory taps did not advance complete factoryresult. Native one-shot `051346` onrightresult changed HP-loss text toAllCyborgsloseUpgradeFactoryAtWorkPassive. New exactfactory-context rightpanel binding `051543` thenchangedEVENT_RESULT→EVENT_RESULT_READY→BATTLE_HUD in2inputs. Subsequentbattle→encounterreward→GIFT_PICK051724 retained. Do not claimfactoryanimation or technicalpassed as floorclear.
- stop_page nowvetoes at observation before any action (oldafter-actionguard allowedfirstgiftselection); regressionzero-input. New event semantic-progress guard excludeschangingRECclock; repeatedsamecontent stops after3unchangedreadings. FullPython495passed. Git751f049 alreadypush (battle submit intent persisted beforeinput); newevent/stop fixes included with thischeckpoint. LastlocalGUI build085939 froze andselftestednewdeployment+submit protection; latestfrozenbuild result must be read fromactualbuild output, not assumed.
- Usage95%primary/15%weekly, ordinaryallowedTrue but remainingwindow insufficient for new largegiftpolicy phase. Finish currentverification/checkpoint only, thenquietlywaitfor scheduledrecovery; never buy/use resetcredit. Goal and heartbeatstayACTIVE; no controller/game inputs whileawaitingofflinegiftfix. FGOpaused. Current Hardscope/team2/order, star100/remaining16/noEnhance/noConversion, initial2receipts and module/refill/conversion0pending remainunchanged.

## Previous continuation: 2026-10-08 04:55 local
- Actual team2 deployment order is now proven by `evidence/runtime/window-20261008-045214/frame-0008.png`: positions map to3,4,9,1,7,2,12,5,8,10,11,6; HongLu is backup12. Counts were individually0/12 through12/12, durable sequence matches and pending is empty. Earlier042218 order remains a recorded failure, never accepted retroactively.
- First diagnostic battle produced real VICTORY in `044013/frame-0043.png` after three submitted turns. No floorclear or reward accepted. Pause-menu RetryStage reset battle with the same order; its transient DEFEAT animation was caused by retry, not a combat-loss inference.
- Fixed native pause-menu veto, fresh ClearSelection identity/control binding and actual ResetDeploymentOrder modal transaction. Clear click044512 opened confirmation; confirm044740 proved0/12. Persisted confirm_sent forbids replay; unknown/mismatched counts retain pending. Actual first-card1/12 missed by wholeOCR; native only_rec fixed numericROI1700,754,128,58 replayed actual1/12,8/12,12/12 without device input. Current native sequence completed in045214.
- Current bounded native battle window PID and terminal state must be checked using `build/correct-order-battle-progress.json` / latest runtime directory and process command line. Do not start another controller while it remains live. Window was started after correct order,40steps, stop-pageGIFT_PICK; active tasks are observation-only for other sessions. Never restart on monitoring timeout.
- Full Python490passed; actual Maa participant replay3cases passed. New code not yet frozen/published at this checkpoint. Hard041437, themeToBeCrushed042100, star100/remaining16, two initial gift receipts and budgets unchanged. No Hard five-floor clear, final paid claim, rotation/reentry acceptance. FGO paused.

## Previous continuation: 2026-10-08 04:28 local
- Current real page **BATTLE_HUD**, latest actual session `evidence/runtime/window-20261008-042218`, nativePID22880 terminal. First WinRate touch sent, no START sent. Do not restart/redo entry/mode/graces/gifts/pack.
- Scope d7c1499436f647208adc50860692a5c2/team2/rotation4, zero floor clears. Hard proof041437 unchanged. Star2,4,5,7 spent100,116→16,noEnhance,unchecked/Cost0. Employee Card and Portable Battery Socket real receipts041101/041119; optionalsearchrefused0spend. Historical ledger evidence preserved, no inheritedfloor1.
- **Pack real successor verified**: scopedtheme intent now uses freshpack_candidates+saved profileweights/recommend_pack (no weights=>neutral_default explicitly logged). Actual To be Crushed dragged once; immediateUNKNOWN causedstop, freshread-only `042100` saysExploringFloor1/To beCrushed. Theme pending resolved with that exact floor/name proof, no repeateddrag. Native MAP→NODE_PANEL→PRE_BATTLE042128 retained.
- **Deployment failure found before START**: initial `042218/frame-0001.png` has4 participants preselected from old encounter: Ryoshu1/Meursault2/Gregor3/YiSang4. Old runner skipped those and added3,9,7,2,8,10,11,6, then submitted12/12. This does NOT match requested3,4,9,1,7,2,12,5,8,10,11,6. Do not accept this battle as saved-order proof or claimcorrectteam deployment.
- Offline repair: newdurable DeploymentTransaction requires ClearSelection for inherited counts, proves0/12 thenexact+1 count for each saved-order click; mismatch/pendingSTOP, fullteamorder_verified required beforeToBattle. SubmissionUNKNOWN persists submit_pending untilrealBATTLE/DEPLOYMENTproof; nextencounterselection resets onlyafterproven submission. No actual reorderedprebattle test yet. Currentbattle alreadyentered; nextstep investigate game-native return-to-stage UI safely or continue this battle as diagnostic only, then enforce freshorder on nextstage. Never claimcurrentdeploymentcorrect.
- Module reward/refill/conversion budgets0/pending; final claimdialog/confirm/bonus now STOP with reward_module_budget_pending (0/pending) or reward_module_cost_not_proven, preserving visible screen; actualcostrecognition and budgetedclaims remainunimplemented. ML/mapmodel/fullrelease stillincomplete. FGOpaused.
- Python482 fullpassed beforedeployment repair; 78focused+newdeployment crash/count regression passed; finalfullpending. Latestpublished720d9bc GUIfrozen/selftested; newtheme/deploymentcode needsfreezeaftercommit. MonitorACTIVE butalwaysreadthislatestPROJECT becauseprompts lag.

## Latest continuation: 2026-10-08 03:14 local (journal UTC 07:14)
- **交接说明写在 `docs/handover-2026-10-08.md`**：入口（桌面 GUI 快捷方式／`tools/start-mirror.ps1`／`tools/run_ledger.py`）、仓库与提交状态（哪两处**未提交**、为什么不能单独提交 `assets/interface.json`）、已实机走通的链路、未解决的问题与建议顺序、用户的硬约束、文件地图。
- **最要紧的未解问题**：用户指出「明确说了用 team 2，还是跑到 team 1 去了」，而账本记录的是 `rotation 4`（轮换表 `[5,4,1,6,2,7,3]` 第 4 位＝2，`RunStore.team_slot` ⇒ 2）与 `active run 93baf3c9 team 2`。两边不一致：脚本只记录「点了出战位第几格」，**没有证据钉住「第 N 格在游戏里就是第 N 支保存队」**，`DUNGEON_TEAM` 的 slot→保存队映射要先补证据。
- **出战前队伍页被 OCR 拆词骗过，现已认得出**：`run-continue-26`（job `pwsh-226`，dir `evidence/runtime/window-20261008-030555`）step 0-3 依次走过 `RESUME_DIALOG`（held run 的弹窗，24 分钟前那次 `unexpected_successor` 的修复生效）→`MAP`→`NODE_PANEL`→`TUTORIAL`，step 4 停在 `TEAM_LIBRARY`（`page_is_observe_only`）。现场用 `adb exec-out screencap` 拍下来是**出战前队伍页**（`Preset #1`＋12 张身份卡＋`Total Participants 0/12`＋`To Battle!`），而 `agent/recognition.py:189` 只在 `pre_battle_team_page(...)` 非空时才把 `TEAM_LIBRARY` 提升成 `PRE_BATTLE_TEAM`。
- **真因**：`map_vision.CLEAR_SELECTION_PATTERN` 要求 `Clear Selection` 是**一个** token，而 `frame-0015.json` 把同一句读成同一行的两个词 `'Clear' [1640,706,74,22]` ＋ `'Selection' [1706,706,122,22]`（历史帧 `window-20261006-0309xx` 都是整句）⇒ 提升失败 ⇒ 这一页没有计划 ⇒ 停机。这是 OCR 读法漂移，不是 UI 变化。
- **修法**：`src/maalimbus/map_vision.py` 新增 `CLEAR_WORD_PATTERN` / `SELECTION_WORD_PATTERN` 与 `clear_selection_caption(records, size)`——整句命中就用整句，否则只接受**同一行**（纵心差 ≤ .03）、左词在右词左边、且这类成对只有一对时，合成 `Text('Clear Selection', (1640,706,188,22), min(score))`；`pre_battle_team_page()` 改用它。`assets/resource/base/anchors.json` 的 `pre_battle_team.clear_selection` 正则放宽为 `^\s*Clear(?:\s+Selection)?\s*$`（note 指向代码里的配对规则——登记表的 kind 只有 ocr/template/geometry，表达不了配对），证据追加该帧。测试 `tests/test_map_vision.py::test_the_clear_caption_is_read_when_ocr_splits_it_into_its_two_words`（含单词不算、不同行不算、左右反序仍算、两对 ⇒ None）。
- **测试**：`tests/test_map_vision.py` 46 passed；`tools/verify_anchors.py --page pre_battle_team` ⇒ 1 page(s), 0 broken（新帧三条 identity 全 hit，geometry 换帧 stale 属正常）。全量 **446 passed, 1 failed**，唯一失败是 `tests/test_pipeline_spec.py::test_interface_json_is_protocol_two_and_names_real_nodes`，由**未提交**的 `assets/interface.json` 指向还没落地的 loop/team-build 节点造成（见上一节）。

## Latest continuation: 2026-10-08 03:05 local (journal UTC 07:05)
- **GUI 走 Maa 正路：MXU 换成 v2.7.1、自组装 `dist/MaaLimbus/`、桌面快捷方式指向 GUI**（提交 `e9d8944`）。`tools/build_windows_package.py` 原来钉的 MXU v2.5.1（`mxu.exe` sha256 `F91554D8…`）在本机开不出窗口（进程活着、`MainWindowHandle=0`、没有 WebView2 子进程、不写 `debug/`）；换成 v2.7.1（`build/mxu-2.7.1.zip` sha256 `825A62AF…`，`build/mxu-2.7.1/mxu.exe` 31,158,272 B sha256 `1B5487AA…`）后，用它自带的官方 sample 工程实测写出了 `build/mxu-probe-271/debug/2026-10-08-2.log`：「`[App] 窗口已显示`」「`[MAA] MaaFramework 版本: v5.12.2`」「`is_compatible: true`」。新增 `tools/make_local_app.py`：用同一个已核验的 `mxu.exe` ＋ 已解压的 `maafw/` ＋ 当前 `assets/docs/THIRD_PARTY_NOTICES/README*/LICENSE`，按 `tools/build_windows_package.py` 的规则组装 `dist/MaaLimbus/`（把 `mxu.exe` 改名 `MaaLimbus.exe`、`interface.json` 的 `agent` 指向 `./agent/MaaLimbusAgent.exe`、`languages`/`icon`/`license`/`welcome`/`resource.path` 加 `assets/` 前缀、PyInstaller 冻结 `agent/main.py`、跑 `--self-test`），先写 `dist/MaaLimbus.staging` 再整体换名（旧目录里的 frozen agent 因此可以复用）。`tools/install_desktop_shortcut.ps1` 默认改成装指向 `dist/MaaLimbus/MaaLimbus.exe` 的快捷方式（`MaaLimbus.ico` 由 `assets/misc/Don-Quixote.png` 生成在旁边），没有该 app 时才回退到 `tools/start-mirror.cmd`。**用户已亲自双击确认：窗口能打开、能看到界面。**
- **诚实申报（GUI 验证的边界）**：我自己的会话拿不到交互桌面（`CopyFromScreen` 抛 `The handle is invalid`），所以「窗口有没有画出来」只能由用户确认；本机后续几次同一 `mxu.exe` 的启动在我的进程里都是「进程活着、无窗口、不写 `debug/`」，这个现象与上面这条限制一致，没有再做取证，也没有把它当成用户的故障。
- **镜牢主循环抽成库，CLI 与 agent 共用一份实现**（提交 `e9f3d02`）：新增 `src/maalimbus/runner.py`（1753 行），把原来塞在 `tools/window_step.py` 里约 770 行循环拆成两个缝——`Device`（`screencap()/click()/swipe()/key()`）与 `Observer`（`observe()` ⇒ 与 CLI 同形的观察记录）。`MirrorRunner.step()` 一步只做「观察 → `maalimbus.window.plan_step` → 一个输入」，`MirrorRunner.run()` 复现外层步数上限、间隔、停机条件与账本效果；`tools/window_step.py` 缩到 392 行纯接线（argparse 块逐字节不变、print 面与 exit code 不变，`--help`/`--flow-list` 仍 exit 0）。测试 `tests/test_runner.py` 6 例（含 AST 测试：runner 不得 import `maa` 或 `recognition`）⇒ **445 passed**，`ruff --select F,E9` 干净。
- **下一步**：agent 侧的 `MirrorLoop` custom action 与随包发布的观察节点正在做（后台），落地后 `assets/interface.json` 里已经写好的 `mirror_loop`／`team_build` 两个任务与 `team_keywords`／`team_keywords_extra`／`team_build_name`／`run_team` 四个选项才会指向真实节点（**这些 `assets/interface.json`＋`assets/i18n/*` 的改动还没提交**，避免 HEAD 指向不存在的节点）。

## Latest continuation: 2026-10-08 02:40 local (journal UTC 06:40)
- **桌面上有一个能直接启动脚本的快捷方式**：`tools/start-mirror.ps1`（`tools/start-mirror.cmd` 只是包一层，`tools/install_desktop_shortcut.ps1` 负责装）⇒ `C:\Users\<user>\OneDrive\桌面\MaaLimbus 镜牢.lnk` → `tools/start-mirror.cmd` → `window_step.py`，参数在 `$TaskSettings` 里改（默认 binary 自动发现 `build\*` 下最新的 `maafw`、adb 回退 MuMu 的 `nx_main\adb.exe`、`--address 127.0.0.1:16416`、`--steps 400`、`--graces 1,3,5,6,8`、`--gift-keyword charge`、`--run-store config/user-run-ledger.json`），`config/user-launch.json`（私人、忽略）可以同名覆盖。启动前会 `adb connect` 并确认 `get-state = device`、读 `build/map-probe-authorization.json` 的 nonce，并**先用 `--observe-page` 零输入读一次 `scene`**：如果已经在镜牢里就跳过菜单流程，不会重复入场。控制台同时写进 `build/mirror-console-<时间>.log`，结束打印 exit code 与日志路径；`-DryRun` 只打印命令（已验证）。
- **轮换现在可以瞄准**：`RunStore.point_at(slot)`（`src/maalimbus/storage.py`）只改 `rotation`，active 未结算时拒绝（`Finish or abandon the active run before moving the rotation`），slot 不在轮换里也拒绝；`tools/run_ledger.py point --slot N` 是它的入口，测试 `tests/test_run_store.py::test_the_player_can_aim_the_next_entry_at_a_named_team`。
- **队伍档 slot 2 改成用户点的充能＋震动队**：`config/user-team-profiles.json` 的 keywords 从 `Poise+Tremor` 换成 `Charge+Tremor`，出战顺序写成 `Don Quixote, Ryoshu, Rodion, Yi Sang, Heathcliff, Faust, Gregor, Meursault, Ishmael, Sinclair, Outis, Hong Lu`（即用户给的 3,4,9,1,7,2,12，红露排最后）。
- **按用户要求核对了 MaaFramework 的技术指标（m15982），并因此发现并修掉一个真缺陷**：结论与新文件 `docs/maaframework-conformance.md` 记全（证据是 v5.12.2 tag 的源码/手册，留档在 `build/maafw-v5.12.2/`）。
  1. **点击坐标系是对的**：`ControllerAgent::preproc_touch_point`（`ControllerAgent.cpp:1038-1060`）把传入点从「缩放后」换算回原始截图（`scale = image_raw_/image_target_`），只有控制单元声明 `NoScalingTouchPoints` 才不换算，而 ADB 的四个输入单元都不声明 ⇒ `post_click` 收的就是我们 OCR 所在的 1920×1080 空间，和手册 `2.4-控制方式说明.md:68` 那句「统一把缩放后的识别坐标换算回原始截图坐标」一致。
  2. **ADB 方法与设备发现按手册走**：`src/maalimbus/adb_device.py` 用 `Toolkit.find_adb_devices` 的测量结果建 `AdbController`，`assets/interface.json` 里 Adb 控制器是 `{"type":"Adb","display_long_side":1920,"adb":{}}`（手册 `3.3:146` 明确 Adb 的 input/screencap 由框架自动检测），Win32 三个控制器的 `screencap/mouse/keyboard` 全在 `2.4` 的官方名表里（`windows-window` 与手册 `:446` 的示例逐项相同）。
  3. **缺陷**：`MirrorHard` 之外的 `MapObserve`／`BattleObserve` 两个节点写着 `limbus_map_observe`／`limbus_battle_observe`，但 `agent/main.py` 只注册了 11 个名字、这两个不在其中 ⇒ 节点在 PI/MXU 下无法执行（实现一直在 `agent/recognition.py:891 MapObservation`／`:926 BattleObservation`）。已补注册（`agent/main.py:51-57`，现共 13 个）。
  4. **守卫**：新增 `tools/verify_pipeline_spec.py`，把这次读的手册条款变成可执行检查（interface_version、controller type、display_* 互斥、Adb 不得手写 screencap/input、Win32 名表、task.entry/option 的 pipeline_override 必须指向真实节点、节点字段属于协议、`next/on_error/interrupt/on_timeout` 目标存在、`custom_*` 必须在 agent 注册、并统计 89 个节点里 56 个可达），`python tools/verify_pipeline_spec.py` ⇒ `ok — 0 problem(s)`；`tests/test_pipeline_spec.py` 9 条测试钉住它（含四条负例）。
- **测试**：**439 passed**；`tools/verify_anchors.py` 45 page(s), 0 broken。
- **仍未申报**：这次只读了规格与本地资产，没有跑 PI/MXU 端到端；Win32 的方法名是对着手册核的，没有在窗口上实测；33 个从 task 入口不可达的节点只提示不删除（其中一些是工具直接调用的入口）。

## Latest continuation: 2026-10-07 21:30 local (journal UTC 01:30)
- **领奖路径在实机上走通了**：`run-continue-21`（job `pwsh-508`，dir `evidence/runtime/window-20261007-203856`）00:39:00 点奖励弹窗的 `Claim`，00:39:02 粘行修复后这一页被正确判成 `RUN_REWARD_BONUS` ⇒ `a_completed_run_spends_one_weekly_bonus_on_its_rewards`（target `[1116,720,112,40]`）⇒ 周奖励被按下 Confirm（花掉一次），领奖完成；00:39:04/06 收尾总览、00:39:22 回镜牢菜单、00:39:29 再入场、00:39:33-35 选出战位与确认、00:39:40-00:40:09 买 Grace／领初始礼物／拒绝礼物搜索 ⇒ **下一局已经开跑**（全套入口动作一次走完，没有空转）。
- **但账本把这一局记错了**：`config/user-run-ledger.json` 里 `abandoned 476f23dc team 1 floors [1,2,3,4,5] victory true reward false`（`2026-10-08T00:39:35Z`）——**胜利、五层都记着，只有 `reward` 没记**，于是 00:39:33 看到出战位时 `reconcile` 把一局**已完成**的 run 当成「游戏已经不要它了」归档 ⇒ `completed` 仍是 1、轮换停在第 2 位（team 1）⇒ 游戏这一局又开了一队 1。
- **两个真洞（提交 `???`）**：
  1. `src/maalimbus/run_wiring.py` 的 `ledger_event` 只把 `RUN_REWARD_CONFIRM` + `REWARD_CONFIRM_REASON` 当作领奖，而实机上「按周奖励问题自己的 Confirm」才是把奖励交出去的输入（`RUN_REWARD_BONUS` + `a_completed_run_spends_one_weekly_bonus_on_its_rewards`）⇒ 新增常量 `BONUS_CONFIRM_REASON` 与对应分支（仅当 `victory and not reward` 记 `reward_received`；Cancel 什么都不给）。
  2. `reconcile` 现在按账本自己记的事实分流：`victory and reward` ⇒ 用 `entry_returned` 把它落成 **receipt**（结算时间、`completed_runs`、轮换全部照常推进），其余才是 `abandoned`；返回值多一个 `how` 字段（`receipt`／`abandoned`）供驱动记进 entry。
- **测试**：`tests/test_run_wiring.py::test_the_team_picker_receipts_a_run_that_finished_and_was_paid`（走完 1-4 层＋总览＋周奖励问题后，出战位必须把它 receipt 掉：`active` 清空、`receipts[-1]['settled_at']` 有值、轮换 1→2、`abandoned` 为空；同一页再看一次不再动）。**429 passed。**
- **没动实机账本**：当前轮换仍是 team 1，与正在跑的那一局一致（那一次重复的 team 1 是真实发生过的历史）；这一局结算后（新代码已生效）轮换会前进到 team 6。

## Latest continuation: 2026-10-07 21:05 local (journal UTC 01:05)
- **结算面板的修复生效**：`run-continue-20`（job `pwsh-492`，dir `evidence/runtime/window-20261007-203340`）step 0 就是 `BATTLE_VICTORY → RUN_CLAIM`（reason `victory_confirm_clears_the_result_and_carries_the_rewards`，target `[1638,831,164,48]`）⇒ 第 5 层的结算页被正确命名并按下 Confirm，进到「Exploration Complete」总览；账本在同一分钟记下 `00:33:47 floor_clear 5` 与 `00:33:47 final_victory`（`active run 476f23dc team 1 floors=[1,2,3,4]` ⇒ 现在 5 层全清）。
- **新停机点：周奖励的第二问在一张 1920×1080 的帧上被 OCR 粘成一行。** step 1-7 在 `RUN_CLAIM ↔ RUN_REWARD_DIALOG` 之间来回（8 次点击后 `claim_family_made_no_progress` 停机）：`frame-0009.json` 读的是**一整行** `Spend your 'Weekly Bonuses, to claim the bonus [636,486,646,34] 0.97`（配对读法里的 `bonus rewards?` 被并进去），于是 `spend_weekly_bonuses`（要求以 `the$` 结尾）与 `bonus_rewards` 都不命中 ⇒ 这一页被判成 `RUN_CLAIM`（总览的四个词还在它背后可读），驱动便一直点总览的 `Claim Rewards [1638,855,180,80]`，每次都把问题当 Cancel 关掉、回到奖励弹窗 ⇒ 死循环；周奖励仍是 `2/3`（没有被花掉）。
- **处理**：`assets/resource/en/locale.json` 的 `spend_weekly_bonuses` 改成 `^Spend your '?Weekly Bonuses,? to claim the(?: bonus)?$`（两行或粘成一行的两种读法都命中），`src/maalimbus/vision.py` 的 `RUN_REWARD_BONUS` 规则改成「问题行（`spend_weekly_bonuses` 或 `bonus_rewards`）＋ `Confirm` ＋ `Cancel`」，第一条的 roi 放到 `(.33,.42,.68,.51)` 以覆盖 `[636,486,646,34]`，注释钉住 frame-0009 与这次死循环。识别顺序本来就正确（`RUN_REWARD_BONUS` 在 `RUN_CLAIM` 之前），坏的是正则。
- **测试**：扩展 `tests/test_vision.py::test_the_weekly_bonus_question_is_named_before_anything_is_spent`（粘行帧必须判 `RUN_REWARD_BONUS`；负例改为把问题两行**都**拿掉）。**428 passed；`tools/verify_anchors.py` 45 page(s), 0 broken。**
- **下一步**：重启驱动接着走 `RUN_REWARD_BONUS`（账本里这一局已有 `final_victory` ⇒ 按 Confirm 花一次周奖励）⇒ 期待 `reward_received` 与 `entry_returned`，轮换从 team 1 前进到 team 6。

## Latest continuation: 2026-10-07 20:45 local (journal UTC 00:45)
- **停机点：第 5 层 boss 打完后的关卡结算页被判 UNKNOWN，等满 40 轮停机。** `run-continue-19`（job `pwsh-465`，dir `evidence/runtime/window-20261007-201340`）step 24 `page_unreadable_after_waiting`；证据帧 `frame-0218..0220.json`（00:30:03–00:30:17）是结算画面：左「Most Valued Employee／Damage Contributed 23%」＋boss 立绘与台词，右 `Victory [1486,146,276,100] 1.0`、`EX-GLEAR [1334,162,180,86] 0.86`、`LV.91`／`EXP +0`／`3992/5178`、十二张 Lv.60 卡与 `Confirm [1638,831,164,48] 1.0`（现场 `build/live-stall-19.png`）。
- **真因**：`BATTLE_VICTORY` 的规则原来要求 `Victory` **且** `EX-CLEAR`，而这一帧的小字被 OCR 读成 `EX-GLEAR`（C 认成 G）⇒ 不命中 ⇒ 整页 UNKNOWN。这一页**不会自己走掉**（唯一前进输入就是那个 Confirm），所以把它当动画「等」是错的处理。
- **处理**：`src/maalimbus/vision.py` 的 `BATTLE_VICTORY` 改为「`Victory`（右上带 .75,.06,.95,.30）且（`EX-CLEAR` 或右下的 `Confirm`）」，注释钉住 frame-0220 与那次误读；`assets/resource/base/anchors.json` 的 `battle_victory` 证据加上 frame-0220（`battle_victory.confirm_button` 仍是 `[1638,831,164,48]`，两帧位置一致）。计划、锚点与 loop-guard 豁免早就存在（`src/maalimbus/window.py:262-272` 点它，reason `victory_confirm_clears_the_result_and_carries_the_rewards`，该 reason 在 `tools/window_step.py:97` 的 `LOOP_GUARD_EXEMPT_REASONS` 里），这次只是把识别修好。
- **测试**：`tests/test_vision.py` 新增 `test_the_result_page_is_read_when_the_badge_letters_are_misread`（钉 frame-0220：有 `Victory`/`EX-GLEAR`/`Confirm`、`classify == 'BATTLE_VICTORY'`、把 `Victory` 拿掉后不再判它），并把原来那条「只拿掉 `EX-CLEAR` 就不算这一页」的断言改成「`EX-CLEAR` 与 `Confirm` 都拿掉才算不成立」。**428 passed；`tools/verify_anchors.py` 45 page(s), 0 broken。**
- **仍未申报**：只证明了两帧（`window-20261007-015542/frame-0130.json` 与 `window-20261007-201340/frame-0220.json`）上 Confirm 位置一致；`EX-CLEAR` 小字在其它分辨率/语言下的读法没有采样。

## Latest continuation: 2026-10-07 20:15 local (journal UTC 00:15)- **「只认亮盘」的实机验证通过（提交 `408061d`）**：`run-continue-18`（job `pwsh-447`，dir `evidence/runtime/window-20261007-195545`）23:55:49 用亮盘提交 `[1440,771,121,134]`，23:56:48 暗盘先做自动编排 `win_rate_is_the_proven_auto_assign_control [1656,796,46,41]`，23:56:58 再提交 `[1497,771,122,132]`；step 13-32 十轮 `win_rate`／`start_button` 交替全部 `passed: true`，一个回合都没再空转。
- **新停机点：整队阵亡后的 `DEFEAT` 横幅页没有计划。** 这一局在第 5 层团灭（对话框 `Floor in Progress 5/5`、`All participating Sinners have been killed.`、`Remaining Units: 0/12`），step 33 是 `page_before DEFEAT / page_after DEFEAT`、`action record`、`reason page_is_observe_only`、`stopped page_is_observe_only`。证据帧 `evidence/runtime/window-20261007-195545/frame-0222.json`（00:10:26）只读到横幅 `DEFEAT [726,434,470,225]`、Gebura `[332,101,100,28]` 与三行台词，**三个选项行还没画出来**；停机后抓的 `build/live-defeat.png` 显示游戏那时已经进了 `Return to Stage Select`／`Retry Stage`／`Accept results and return to Stage select` + `✓ Confirm`，也就是早已命名的 `BATTLE_DEFEAT`。
- **修复**：`src/maalimbus/window.py:70` 的 `WAIT_PAGES` 加入 `'DEFEAT'`（与 `BATTLE_RESULT` 同一个道理：页面自己会走，点它没有意义），战斗页的两条 `expect` 补上 `'DEFEAT'`；`tests/test_window.py` 的 `WAIT_PAGES` 断言改成三元组，并新增 `test_the_wiped_run_is_waited_into_its_dialog_and_the_battle_expects_it`（钉 `frame-0222.json`：`classify == 'DEFEAT'`、战斗计划接受 `DEFEAT`、`DEFEAT` 页自身仍然没有输入）。**426 passed。**
- **重启实机验证（`run-continue-19`，job `pwsh-465`，dir `evidence/runtime/window-20261007-201340`）**：00:13:43 `BATTLE_DEFEAT → the_wiped_stage_is_picked_for_a_retry`（点 `Retry Stage` 行）→ 00:13:45 `the_retry_is_confirmed_and_the_stage_starts_over`（点它自己的 Confirm）→ 00:14:02 回到 `BATTLE_HUD`，00:14:06／00:15:18 起按「暗盘先编排、亮盘再提交」继续打 ⇒ 团灭后的重试路径在实机上走通。
- **顺手补掉账本的一个死结（提交 `???`）**：`src/maalimbus/run_wiring.py` 新增 `reconcile(store, *, page, proof=None, note=None, on_event=None)` —— 出战位（`DUNGEON_TEAM`）只会在**全新一局**时被画出来（还在进行中的一局会用 Dungeon Progress 弹窗回答 Resume/Halt，证据帧 `evidence/runtime/window-20261006-025617/frame-0002.json`），所以在账本仍记着 active run 时看到它，就说明那一局已经无回执地结束（玩家接受了团灭），此时把旧 run 归档进 `abandoned`（保留它到过的层）并保持轮换不动，否则 `settle` 只会在没有 active 时才开新 run，账本会永远卡在死局上；`tools/window_step.py` 在既有的 `expire` 相邻处调用它并把事件记成 `run_reconciled`。测试 `tests/test_run_wiring.py::test_the_team_picker_files_a_run_the_game_no_longer_holds`（含「同页再看不重复归档」「别的页面不归档」）。**427 passed。**
- **仍未申报**：`BATTLE_DEFEAT` 的重试预算（`--defeat-tries 2`）用完后仍由玩家决定（`defeat_retries_exhausted`）；被游戏判负的那一局要不要自动走 `tools/run_ledger.py abandon` 还没接线。
- **补上「交出去」的开关（提交 `d6acae0`）**：新增 `--defeat-accept`（默认关）——重试预算用完后改为按对话框自己的第三行 `Accept results and return to Stage select`（reason `the_wiped_run_is_accepted_and_the_stage_select_comes_back`），由操作者显式交出一局；关掉时行为不变（`defeat_retries_exhausted` 停机等玩家）。飞行中的重试照旧先跑完，缺锚点仍按名拒 `defeat_accept_row_not_anchored`；`tests/test_window.py` 的 BATTLE_DEFEAT 用例补了这四条断言。**427 passed。**

## Latest continuation: 2026-10-07 19:55 local (journal UTC 23:55)
- **停机点：整整一局的所有步数都花在「Win Rate」上，一个回合都没交出去（提交 `624b067`）。** `run-continue-16`（job `pwsh-385`，dir `evidence/runtime/window-20261007-184958`）跑满 300 步结束，最后 27 条 intent 全是 `win_rate_is_the_proven_auto_assign_control`（target `[1598,796,48,41]`／`[1600,792,46,45]`，即 Win Rate 标签自己），**没有一条 `start_button_submits_the_assigned_turn`** ⇒ 实机在 TURN 3 原地空转约 40 分钟（现场 `build/live-stall-run16.png`，证据帧 `evidence/runtime/window-20261007-184958/frame-1401.json`：`Damage/Rate/Win/MAX/TURN/'1/10'/'3'` 都读得到，**没有 `START`**）。
- **真因**：`src/maalimbus/window.py:804-816` 先看 `start_box`、没有才退回点 Win Rate；而 `start_box` 来自 `battle_vision.start_button()` → 读不到 START 词时退回 `dial_control()` 的颜色读数（`(0.60,0.66,0.78,0.88)`、`area>=4000`、`side>=60`）。这一局 1103 个战斗帧里只有 `frame-0760.json`（23:17:39）与 `frame-0912.json`（23:21:29）真的读到 START 词；而转盘本身在抽样的 163 帧里有 160 帧是暖色的（两种尺寸：`(1440,771,121,134)` area 5501 与 `(1455,800,81,79)` area 1913，1920 记法），它的中心 x≈1500 刚好落在旧带右边缘（`0.78*1920 = 1497`）之外 ⇒ 旧参数只在 11/163 帧答得出，缺了 `start_box` 就整局空转。
- **处理（先走错一步，已纠正）**：`624b067` 先把 `dial_control` 的带放宽到 `(0.58,0.60,0.82,0.93)` 并把阈值降到 `area>=1200`、`side>=45`，结果 `run-continue-17`（job `pwsh-403`，dir `evidence/runtime/window-20261007-194201`）拿它当 START 连点 7 次，TURN 仍停在 3 —— 那个 `(1455,800,81,79)` area 1913 的**暗转盘根本不是提交键**（同一个输入在 run-continue-16 里已经烧掉 300 步）。本步改为**只认被点亮的那个转盘**：`area>=4000`、边长 `100..160`、长宽比 ≤ `1.25`、填充率 ≥ `0.28`，于是亮盘 `(1439,772,121,133)` area 5512 保留，暗盘与技能区的大片暖色高亮（`window-20261007-175552/frame-0307.png` 里 200×145 的假货、`frame-0083.png` 里 172×264 的假货）都被拒掉。
- **被证明的输入顺序**：暗盘是「这一回合还没编排」的样子，**先点 Win Rate（自动编排）才点亮转盘**——`window-20261007-175552` 22:43:44 点 Win Rate（`[1714,796,46,41]`），22:43:46 的 `frame-1010.json` 就带 `START [1580,742,52,24]` 与亮盘 `(1551,773,121,133)`，随后才提交。本步用一次手动受控点击复现（`tools/map_zoom.py --click "1623,816"`，Maa 模拟触控）：静态四十多分钟的暗盘（1280 屏幕 854 像素暖块）当场变成亮盘（2474 像素）并显示 START 横幅；停掉驱动后采样 48 秒（8 张 `build/idle-*.png`）那片区域像素完全不变 ⇒ 那确实是等输入的静止状态。
- **验证**：三个窗口 1651 个战斗帧里 `dial_control` 现在 691 帧答得出，除两帧是同一转盘带光晕（`138x141`、`137x136`）外**全部是转盘自己的 `121x13x` 框**。`tests/test_battle_touch.py` 两侧都钉住：`test_the_dim_dial_waits_for_the_auto_assignment_instead_of_submitting`（钉 frame-1401：无 START 词、`dial_control`/`start_button` 都 None、`begin_turn_plan` 以 `turn_start_not_present` 拒答、给出的是 Win Rate 标签）与 `test_the_lit_dial_is_read_on_a_board_that_draws_no_start_word`（钉 `window-20261007-175552/frame-0020.json`：无 START 词、框 `(1439,772,121,133)` 完全在标签左侧、就是 `begin_turn_plan` 的目标）。**全量 425 passed；`tools/verify_anchors.py` 45 page(s), 0 broken。**
- **仍未申报**：暗盘只等于「未编排」这一步是由画面自证（编排前只有光秃的链条，编排后出现 `Clash!`/`REINFORCE` 与橙色箭头）而不是文档；也没有证明「一次 Win Rate 必然点亮转盘」在所有版面成立。

## Prior continuation: 2026-10-07 18:30 local (journal UTC 22:30)
- **战后剧情比默认等待预算长（提交 `be02dd9`）**：`run-continue-14` step 60 `page_unreadable_after_waiting` 的真因不是页面坏了，而是 VICTORY 之后剧情会连着播好几分钟（`evidence/runtime/window-20261007-174525/frame-0191..0196` 是其中六帧，每帧 sha 都不同 ⇒ 剧情自己在走）。`tools/window_step.py:578` 的 `--unknown-rounds` 默认 12 → **30**（约 3 分钟），help 文本写明这条来由；真正的卡页仍会在 30 轮后停下报出来。观察时另用 `--unknown-rounds 40`。
- **金色地板上的「被给环」被背景吃掉（提交 `4565f69`）**：`run-continue-15` 在 floor 3「Emotional Indolence」上连点 8 次图标都点空（21:59:18–22:00:27 八条 `window_map_retry`），第九次才点中 `[1064,472,190,190]`。诊断帧 `evidence/runtime/window-20261007-175552/frame-0052.json/.png`：`lit_components` 在默认阈值下只有 8 个 40–50px 的**普通节点图标**、没有任何环；把亮度阈值抬到 **150** 时恰好出现一个环（`point (1147,443)`、`box (1113,384,69,119)`、`fill .345`）——正是游戏给的那一步。原因是这一层的地板用**和奖励同色的金色网纹**画，环的像素和背景连成一片。
- **处理**：新增常量 `LIT_RING_MIN_VALUE = 150`，`map_clicks` 在 `chevrons` 之后、`rings`/`icons` 之前用 `lit_rings(image, min_value=LIT_RING_MIN_VALUE)` 生成 `lit_ring` 候选；玩家半径过滤改为只对**被光路证实**的玩家生效（`corroborated = player if walk else None`）——没有走出光路时，被它过滤掉的那个读数本身就是错的（该帧的 (1126,433) 正是被给节点的环，环与火焰同色），于是唯一真候选反被丢掉。
- **测试**：`tests/test_map_vision.py` 新增 `test_the_offered_ring_is_named_first_on_a_floor_painted_the_same_gold`（钉 frame-0052：150 下恰一环、距 (1147,443) ≤20、首候选 kind `lit_ring`、八个图标仍排在它后面），并把三处「只允许诚实的帧内读数」kind 白名单加上 `lit_ring`。**全量 423 passed；`tools/verify_anchors.py` 45 page(s), 0 broken。**
- **仍在实机跑**：`run-continue-15`（job `pwsh-327`，dir `evidence/runtime/window-20261007-175552`）此时 129 intents、`failed intents 0`，正在 floor 1/2 的战斗与商店之间推进；账本 `rotation 2 -> team 1 / completed 1 / active run 476f23dc`。
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）。

## Prior continuation: 2026-10-07 17:55 local (journal UTC 21:54)
- **停机点一：工厂层（Floor 2）的青色光路读不到，驱动把玩家自己和奖品图标当节点点（提交 `3ee766d`）。** `run-continue-13` step 113：`node_markers` 只认出 2 个（玩家自己 (751,425) 与它下方的奖品图标），青色 `?` 节点、左侧 `?`、中间灰节点全没找到 ⇒ `advance_candidates` 把玩家与图标当候选，点两次 `map_click_opened_no_panel` 后 `no_candidate_node_observed`（证据帧 `evidence/runtime/window-20261007-172225/frame-0406.png`；现场 `build/live-stall-113.png`）。根因是 `path_end` 的掩码只认紫罗兰色的路（Floor 1/3），Floor 2 画的是**青色虚线**。
- **处理**：`path_end` 的掩码加一条 `(g>=140)&(b>=140)&(r<=150)&(g-r>=40)&(max>=180)`（`max>=180` 是采样出来的：再低青色地板网格会连成一块，再高光路断成几截）；`PATH_WALK_LIMIT` 320 → 560（目标节点在一个格子步之外约 470px）；光路末端若在 `PATH_SNAP`(70px) 内落着被环标记的青色节点，就**吸附到那个节点**（光路说明是哪个节点，环说明点哪个像素）。`clicks[0]` 变成 `path_node (1039,155)`。
- **停机点二：光路修复后同一局的第一下仍点空（同一次提交）。** `run-continue-14` step 0 观察的是 `frame-0002`（过渡帧），那一帧上各玩家读数互相矛盾：机车对 `train_player` 给 (636,510)、徽章抬起给 (751,425)，而火焰烧在 (694,384)。旧链先信机车 ⇒ 玩家点错 137px（超出 `PATH_REACH`）⇒ `path_end` 拿不到光路 ⇒ 退回 `cyan_node (872,296)`，点空一次后重试才对。
- **处理**：新增 `flame_count(image, point, *, radius=110, band=(.12,.80))`（只在地图带里数玩家的火焰像素，不然会数到顶部的罪孽计数器）与 `player_readings(image, markers)`／`player_of(image, markers)`：把五个玩家读数按「它底下有多少火焰」排序，票多的当玩家（火焰是页面上唯一确定属于玩家的东西）；`map_clicks` 再把光路从其余读数各走一遍，取第一个走得出光路的（光路是从玩家画出来的，所以它也能反过来验证玩家）。
- **测试**：`tests/test_map_vision.py` 加 `test_the_player_is_the_reading_the_flame_agrees_with` 与 `test_the_cyan_path_is_walked_even_when_the_player_is_read_mid_fade`（都钉 frame-0002）。**全量 422 passed；`tools/verify_anchors.py` 45 page(s), 0 broken。**
- **停机点三：战后剧情把胜利横幅的首字母盖住（同一次提交）。** `run-continue-14` step 60 `page_unreadable_after_waiting`：VICTORY 横幅上面压着剧情框（`'ICTORY' [830,444,342,187] .85`，剧情行 `'... I've learned a' [460,83,480,20] .96` 正盖住 V），`^VICTORY$` 匹配不上 ⇒ 整页 UNKNOWN ⇒ 等满 `--unknown-rounds`（默认 12 轮 ×6s）停机。处理：`locale` 的 `victory` 改成 `^V?ICTORY$`（只有一个页面画这个词），并解掉 `tests/test_battle_result_scene.py` 里对正则原文的过度钉死。BATTLE_RESULT 本身在 `WAIT_PAGES` 里（只等不点），所以这只是**认清**，不是加点。
- **仍在观察**：战后剧情会自己走（连续帧 sha 一直变），但比默认等待预算长；再驱动时把 `--unknown-rounds` 放大（例如 40）而不改默认值——它同时兜着真正的卡页。
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）。

## Prior continuation: 2026-10-07 19:30 local
- **停机点：花掉周奖励后，通行证升级通知盖在镜牢入口页上（提交 `36c7902`）**。`run-continue-12` step 0 在第二问点 Confirm（花了 1/3 次周奖励、把这一局的残余奖励领到手：Weekly Bonuses 变 2/3、Weekly Projection Cap 变 10/1000），游戏随即弹出 **Pass Level Up** 通知（`Pass Level 67`／`Battle Pass XP` 十格／`✓ Confirm`），它盖在 **Before Entry** 之上，而入口页自己的 `Enter` 仍可读 ⇒ 驱动把这一帧判成 `MIRROR_ENTRY`，对着被盖住的 Enter 空点，`unexpected_successor` 停机（证据帧 `evidence/runtime/window-20261007-171928/frame-0005.json`，sha `aa7c595bbc77`；现场 `build/live-run12.png`）。
- **处理**：`locale` 加 `pass_level_up`／`battle_pass_xp`，`vision.py` 把 `PASS_LEVEL_UP` 判在 `MIRROR_ENTRY` **之前**（浮层要赢过它盖住的页面），`window.py` 点它唯一的 `pass_level_up.confirm_button`（reason `the_pass_level_up_notice_is_acknowledged_to_clear_the_menu`），`MIRROR_ENTRY` 的 expect 接受 `PASS_LEVEL_UP`；anchors 新增 `pass_level_up` 页（Confirm 几何 `[884,682,160,46]`），`pending` 里已被证明的 `previous_session_expired` 移除。
- **同时修掉一个会乱花钱的兜底**：`run_wiring.earned_its_payout()` 原先在缺少时间戳时退回「receipt 有 victory/reward 就算挣到」，而账本里那张 team 4 的 receipt 写于「receipt 带 `settled_at`」之前，于是这一问被判成「打过的一局」而点了 Confirm —— 实际那一局的奖励来自被周重置作废的 run。现在只要账本里有 `abandoned` 而时间戳无法比较，就**不花**周奖励（不知道就不花）。
- **测试**：`tests/test_vision.py::test_the_pass_level_notice_is_named_over_the_menu_it_covers`（钉 frame-0005；把通知两行拿掉后同一帧必须回到 `MIRROR_ENTRY`，证明优先级）、`tests/test_window.py::test_the_pass_level_notice_is_acknowledged_instead_of_the_covered_menu`、`tests/test_run_wiring.py` 的 `earned_its_payout` 用例加了「时间戳缺失 ⇒ 保留周奖励」。**全量 418 passed；`tools/verify_anchors.py` 45 page(s), 0 broken。**
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）。

## Prior continuation: 2026-10-07 19:05 local
- **停机点：领奖的第二问会花掉「周奖励」，不能见 Confirm 就点。** 在 **Exploration Reward** 弹窗点 Claim 之后，游戏又追一问 **「Spend your 'Weekly Bonuses, to claim the / bonus rewards?」**（`✕ Cancel`／`Confirm`，背后是变暗的奖励弹窗；证据帧 `evidence/runtime/window-20261007-171228/frame-0003.json`，sha `be5d7c3077df`；现场 `build/live-claim-confirm.png`）。`run-continue-11` 只把它当无名对话框，于是 step 1 `page_is_observe_only` 停机。
- **网络事实（Steam 讨论 <https://steamcommunity.com/app/1973530/discussions/0/597403944640085425/>）**：周奖励每週只有 3 次、**每周重置且不累积**；打完不领（弹窗的 `To Window`）可以留到以后领，届时用「未来那一周」的 bonus；跨周进行中的一局会被自动判负（auto-concede），**当周 bonus 直接作废**，但已清层数仍可在下一周领奖。⇒ 这一问花的是有限资源。
- **决策：由账本回答这一问。** 真正打完（receipt：`victory`/`reward`）的那一局才花一次 bonus 点 Confirm；被游戏作废或玩家放弃的那一局（归档在 `abandoned`）点 Cancel 把 bonus 留下。落地（提交 `a76f292`）：
  - `assets/resource/en/locale.json` 加 `spend_weekly_bonuses`（`^Spend your '?Weekly Bonuses,? to claim the$`）与 `bonus_rewards`（`^bonus rewards\?$`）；`src/maalimbus/vision.py` 在 `RUN_REWARD_CONFIRM` 之前用「这一问＋它的尾句＋按钮对」四条判 `RUN_REWARD_BONUS`。
  - `src/maalimbus/window.py` 新增 `RUN_REWARD_BONUS` 计划（`plan_step`/`_plan_step` 新增 `bonus=None`）：`bonus={'spend': True}` 点 `run_reward_bonus.confirm_button`（reason `a_completed_run_spends_one_weekly_bonus_on_its_rewards`），否则点 `run_reward_bonus.cancel_button`（reason `a_run_that_was_not_completed_keeps_the_weekly_bonus`）；缺锚点分别走 `run_reward_bonus_confirm_not_anchored`／`run_reward_bonus_cancel_not_anchored`。两个按钮都不是禁点（这一页两个答案都合法），缺省（没有任何证据）取不花钱的 Cancel。
  - `src/maalimbus/storage.py` 的 `RunStore.record` 在落 receipt 时写 `settled_at`；`src/maalimbus/run_wiring.py` 新增 `earned_its_payout(store, *, settled_now=False)`，用 `receipts[-1]['settled_at']` 与 `abandoned[-1]['abandoned_at']` 比谁更新（没有时间戳时退回 `victory or reward`），并让驱动在开局与每次结算后按它刷新。
  - `tools/window_step.py`：`bonus={'spend': run_settled_itself}` 传进 `plan_step`、记进每步 `entry['bonus']`；结算出 `final_victory`/`reward_received` 时置真，`expire()` 命中时置假。
  - `assets/resource/base/anchors.json` 新增第 20 页 `run_reward_bonus`（identity 四条 OCR；controls `run_reward_bonus.confirm_button` 几何 `[1116,720,112,40]`、`run_reward_bonus.cancel_button` `[702,724,140,36]`；evidence 指 frame-0003）。
- **测试**：`tests/test_vision.py::test_the_weekly_bonus_question_is_named_before_anything_is_spent`（钉 frame-0003；拿掉问句后不得判成这一页）、`tests/test_window.py::test_the_weekly_bonus_question_spends_one_only_for_a_run_that_finished`（spend 真/假两条路径、缺省取 Cancel、缺锚点两条拒因）、`tests/test_run_wiring.py::test_only_a_run_that_earned_its_payout_may_spend_a_weekly_bonus`（过期在 receipt 之前／之后各验一次）。**全量 416 passed；`tools/verify_anchors.py` 44 page(s), 0 broken。**
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）。

## Prior continuation: 2026-10-07 18:35 local
- **过期那一局的奖励领取页也认出来了**。领掉 `EXPIRED_SESSION` 的 Confirm 后，游戏把人放在 **Exploration Reward** 弹窗上：`Weekly Bonuses 3/3 ON`、`Floor 3 [NORMAL] 3/6`、`Starlight 11`、`Rewards 150 / Battle Pass XP x24 / Projection Rate x10 / Manager EXP 75`，按钮是 `✕ GiveUpRewards`／`To List`／`✓ Claim`（证据帧 `evidence/runtime/window-20261007-171021/frame-0006.json`，sha `24ab86917b97`；现场 `build/live-after-expired.png`）。同一个弹窗从「窗口」进时中间那个按钮写 **`To Window`**，从镜牢列表进时写 **`To List`** —— 原先的页面规则只认前者，于是 `run-continue-10` 把整段观察预算花在它身上（`page_unreadable_after_waiting`）。现在两个写法都算同一页（`RUN_REWARD_DIALOG`），`Give Up Rewards` 依旧是禁点（`run_reward.give_up_button`）。
- **测试**：`tests/test_vision.py::test_the_reward_modal_is_named_whichever_way_the_game_leaves_it`（钉 frame-0006；把 `To List`／`To Window` 都拿掉后必须仍判 `UNKNOWN`，证明它是被按钮条命名的）。**全量 413 passed；verify_anchors 43 pages 0 broken。**
- **账本现状**：`expire()` 把那局归档进 `abandoned`（`run_expired 6b4d2790eaf64880b6c3e8a7c6889835`），`status` 为 `rotation 2 -> team 1 / completed 1 / active run none`；接下来重启窗口就是「领掉这份奖励 → 用 team 1 重新进场 → 打满五层让 rotation 前进到 3（team 6）」。

## Prior continuation: 2026-10-07 18:05 local
- **停机点：周记录重置真的把那一局作废了**。`run-continue-9` 点掉通知后走向 `UNKNOWN` →（战斗提示加载页）→ **DRIVE** → 按镜牢入口 → **`EXPIRED_SESSION`**：`The previous session has expired.` / `Please claim your rewards.` ＋ `✕ Cancel`／`Confirm`（证据帧 `evidence/runtime/window-20261007-170653/frame-0009.json`，sha `323539fd0c19`；现场 `build/live-expired-session.png`）。也就是说：周记录一重置，正在打的那一局就被游戏作废，Cancel 与 Confirm 都留不住它（点 Cancel 后照样走 LOADING → DRIVE）——脚本要做的只是把残余奖励领掉。
- **处理**：`window.py` 的 `EXPIRED_SESSION` 计划点 `expired_session.confirm_button`（`advance=True`、`expect=(ANY,)`、reason `the_expired_session_is_confirmed_so_its_rewards_are_claimed`），`expired_session.cancel_button` 登记为 `FORBIDDEN_CONTROLS`（关掉提示就把奖励留在桌上）；`DRIVE` 的 expect 补 `EXPIRED_SESSION`（这一步原本正是 `unexpected_successor` 的成因）。账本侧新增 `run_wiring.expire()`：过期不是「通关」，所以把 active run **归档进 abandoned**（保留已到的 floors、note 里写取证帧路径），**rotation 不动**（同一队下一次再进），驱动在 `EXPIRED_SESSION` 步成功后调用它并记 `run_expired`；这样团灭/过期都不会再把一局永远挂在 active 上。
- **测试**：`tests/test_window.py::test_the_expired_session_claims_its_rewards_and_never_dismisses_them`、`tests/test_run_wiring.py::test_an_expired_session_files_the_run_and_leaves_the_rotation_alone`（abandoned 保留 floors=[1] 与 note 里的证据帧、rotation 仍是 1、只有该页且只记一次）、`tests/test_anchors.py` 页序加 `expired_session`；anchors 新增 `expired_session` 页（Confirm 几何 `[1112,720,116,40]`，Cancel `[702,724,140,36]` 登记但禁点）。
- **全量 412 passed；`tools/verify_anchors.py` 43 page(s), 0 broken。**
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）。

## Prior continuation: 2026-10-07 17:20 local
- **停机点：地图上浮出「周记录重置」通知（提交 `c267045`）**。`--label run-continue-8`（`evidence/runtime/window-20261007-164753`）在 step 64 停机：`page_before NODE_PANEL` → 在节点面板按 Enter 后，地图上盖出两按钮通知，正文两行 **「The weekly record has been reset.」/「Moving over to the Window.」**，下面 `✕ Cancel` 与绿色 `✓ Confirm`；驱动只把它当成 `UNKNOWN_DIALOG`，于是 NODE_PANEL 那一步被判 `unexpected_successor` 停机（证据帧 `evidence/runtime/window-20261007-164753/frame-0252.json`，sha `525d45cc4e7b`；现场 `build/live-stall-node-dialog.png`）。
- **决策**：Confirm 是「离开地牢去 Window」，会把进行中的一局扔掉，所以按用户硬约束「未知待确认绝不清掉」取保守分支——**给页面命名、只点 Cancel 留下这一局，Confirm 登记为 `FORBIDDEN_CONTROLS`**（`window_reset.confirm_button`）；Cancel 是 `advance=True`（点完必须换页才算生效，防止空点被记成推进）。locale 新增 `weekly_reset`／`weekly_moving` 两键；`vision.py` 在通用 dialog veto 之前命名 `WINDOW_RESET`；`window.py` 的 `MAP` 与 `NODE_PANEL` 都接受 `WINDOW_RESET` 作为合法后继；anchors 新增 `window_reset` 页（evidence frame-0252，Cancel 几何 `[730,673,148,45]`，Confirm `[1050,678,150,36]` 登记但禁点）。
- **测试**：`tests/test_vision.py::test_the_weekly_reset_notice_is_named_and_its_confirm_is_not_the_identified_form`（钉 frame-0252；只留两行正文时仍只能是 UNKNOWN，证明按钮对才命名）、`tests/test_window.py::test_the_weekly_reset_notice_is_declined_and_never_takes_the_window`（点 Cancel、缺锚点走 `weekly_reset_cancel_not_anchored`、把 Cancel 的框错注册到 Confirm 上仍被 `control_is_forbidden` 拒）、`tests/test_anchors.py` 页序加 `window_reset`。
- **全量 410 passed；`tools/verify_anchors.py` 42 page(s), 0 broken。**
- **网络检索**：`web_search`「The weekly record has been reset / Moving over to the Window.」只回到 Steam 讨论与 namu.wiki 镜牢页等泛结果，**没有**确认 Cancel/Confirm 语义的公开说明 ⇒ 不据此改行为，按保守分支处理。
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）。

## Prior continuation: 2026-10-07 16:45 local
- **里程碑：轮换账本在实机上自己前进了一格**（m12942 的驱动线与用户长期目标「保存轮换队并再入场」同时闭环）。窗口 `--label run-continue-7`（`evidence/runtime/window-20261007-162956`，`--run-store config/user-run-ledger.json`）从 team 4 的这一局打到结算，journal 里四条 `run_ledger_event` 按序落地：`20:31:29 floor_clear 5`（frame-0025）、`20:31:29 final_victory`（frame-0025）、`20:31:34 reward_received`（frame-0029）、`20:32:06 entry_returned`（frame-0045）。
- **账本读数**：`python tools/run_ledger.py --path config/user-run-ledger.json status` ⇒ `slots [5,4,1,6,2,7,3]`、**`rotation 2 -> team 1`**、`completed 1`、`active run none`；receipt `8de51ee326254dada65ae776aa1c1e11` 带 `team 4`／`floors [1,2,3,4,5]`／`victory true`／`reward true`，每个事件各带一帧 sha256 证据（floor_clear 1..4 来自 `window-20261007-134338/frame-0307.json`、`window-20261007-140234/frame-0271.json`、`frame-0375.json`、`frame-0814.json`，其余来自本窗口 frame-0025/0029/0045）。随后新一局已经**自己用 team 1 进场**并推进（`SHOP → SHOP_LEAVE → MAP → NODE_PANEL`）。
- **这一段补掉的停机点**：① 剧情 cutscene 连点三次时循环守卫误杀——step 185 的第三次 SKIP 恰恰揭出 `EVENT_CHECK_READY`，却被 `the_same_plan_repeated` 判失败停机；把 `the_cutscene_is_skipped_to_resume_the_run` 加进 `LOOP_GUARD_EXEMPT_REASONS`（步数预算兜底）后重启窗口，立刻 `EVENT_CHECK_READY → BATTLE_HUD`（提交 `3e5e1ba`）。② 更早的三条（地图 visit 记忆 `ba0f5a3`、wave 丢首位数字 `cbb4b7f`、`--flow` 逗号链 `d57b020`）。
- **文档**：`docs/acceptance.md` 新增顶部一节「the rotation ledger advanced on its own after a completed run」，并把它下面旧段落的「Not claimed: the rotation ledger still does not advance itself」改成「Since superseded」。
- **仍未申报**：JP/MXU 实机、体力（Enkephalin）兑换、Windows 包 `dist/`（三个输入归档在本机，可用 `tools/build_windows_package.py --mxu … --maa … --mxu-source … --verified-dungeon-clear` 重出）；账本还没有「中途放弃」路径 ⇒ 团灭后选「Accept results」的局会一直挂在 active。
- **全量测试 403 passed；`tools/verify_anchors.py` 41 page(s), 0 broken。**

## Prior continuation: 2026-10-07 16:10 local
- **继续按 m12942「从零开始驱动脚本打镜牢、我只负责看卡在哪里」推进：又抓到三个真停机点，全部修掉并实机验证。**
  1. **地图候选被「已经点过」的记忆锁死（提交 `ba0f5a3`）**：`build/window-run-continue-4.json` 在 floor 1「The Outcast」上点开被点亮的「?」节点 `[1067,389]` → 节点面板 → Enter → 剧情/事件 → 起始礼物 → **回到同一张地图**；此后 9 个候选全部点不开面板，步 14 `unexpected_successor` 停机。用受控探针 `tools/map_zoom.py --click "1087,409"` 手动点同一坐标**立刻打开节点面板**（`build/live-probe-question.png`「The Outcast」＋Enter）⇒ 真因是 `MapProgress.tried` 只按「具名换层」清空，把同一个 visit 里已点过的、仍然有效的节点永久排除。新增 `MapProgress.leave()`：**一步的落点只要离开地图（且不是 None/UNKNOWN）就结束这次 visit**、允许重走同一批点；层号抖动仍然不会清空（run110 的保护不动）。测试 `tests/test_map_progress.py::test_leaving_the_map_offers_its_spots_again_on_the_next_visit`。
  2. **战斗 HUD 因 wave 计数丢首位数字而整页判 UNKNOWN（提交 `cbb4b7f`）**：`evidence/runtime/window-20261007-151655/frame-0529.json` 的左上角读到 `"/10" [98,39,34,24] 0.99` 与干净的 `"TURN" [20,97,42,22] 1.0`，同时 START／Win／Rate／Damage 全部可读，却因为兜底正则 `^\d{1,2}/\d{1,2}$` 要求斜杠前有数字而 `battle_hud()` 返回 None ⇒ 窗口在战斗页等了十轮后 `page_unreadable_after_waiting` 停机（step 150）。正则改成 `^\d{0,2}\s*/\s*\d{1,2}$`（允许丢首位数字；该角只有战斗页会同时有 TURN 与计数）。测试 `tests/test_map_vision.py::test_the_battle_hud_survives_a_counter_that_lost_its_first_digit`。
  3. **冷启动要三条命令（提交 `d57b020`）**：`--flow` 现在接受**逗号链**（`launch,to_mirror,enter_mirror`，按序走完，所有步骤落进同一条 `flow_steps` 记录；未知名字立刻报错并列出可用的三个），新增 `--after-flow` 让窗口在流程链之后继续跑 `--steps` 的页面循环 ⇒ **一条命令就能从冷客户端开局并接着打**，两段之间不再让客户端空闲。
- **实机**：`build/window-run-continue-5.json`（159 步 / 158 次点击，用完预算停下，无停机点）与重启后的 `evidence/runtime/window-20261007-154554`（`--label run-continue-6`，`--run-store config/user-run-ledger.json`）继续推进；账本 `active run 8de51ee3 team 4 floors=[1,2,3,4]`，rotation 仍是 `1 -> team 4`，等这一局走到 `RUN_CLAIM`/奖励弹窗 Confirm/再入场 Confirm 才会旋转到 `team 1`。
- **全量测试 403 passed；`tools/verify_anchors.py` 41 page(s), 0 broken。**
- **待办**：把这一局跑到结算并确认 rotation 前进一格；随后是 Windows 包（`dist/` 仍未产出）与邮件/体力兑换。
- **网络资料（未据此改脚本，来源不可靠）**：`https://www.gamer.org/limbus-company-mirror-dungeon-guide-beat-floor-5-on-any-team/`（事件节点优先、商店换技能/融合礼物、Mountain Trials 选攻/防/HP）、Steam 速查表 `https://steamcommunity.com/sharedfiles/filedetails/?id=3237308577`（八种节点、主题包推荐）、wikiwiki.jp 镜牢页；`limbuscompany.fandom.com` 直连 403。

## Prior continuation: 2026-10-07 15:40 local
- **从大厅驱动一局、盯停机点的结果：抓到三个真停机点，全部修掉**（用户的当前指令 m12942）。
  1. **`GIFT_GET → GIFT_SEARCH` 被判成 `unexpected_successor`（提交 `030c777`）**：起始礼物的 GET 提示点掉后紧接的是可选礼物搜索，而计划的后继表里没有它——同一发点击在早先窗口能过，只是因为 settle 窗口**恰好**抓到中间页；这次是 `late_observation`（`build/window-run-continue-2.json` step 71）。已把 `GIFT_SEARCH` 列进 `GIFT_GET` 的 expect 并注释记下这次失败。
  2. **账本在通关时什么都没记（提交 `a961044`）**：`build/window-run-continue-2.json` 里 step 52 `BATTLE_VICTORY → RUN_CLAIM`、53 领奖、54 弹窗 Claim、55 弹窗 Confirm → 回结算页，之后回大厅并**又开了一局**，但 `ledger_events` 全空、rotation 一动不动。真因：旧规则要求「五层都已入账」才认 `RUN_CLAIM` 是最终胜利，而 **floor 5 永远无法先入账**（地图页靠「站在 floor n」证明 n-1 清除，没有 floor 6 可站）。现在结算页先settle `floor_clear 5`，再在同一个循环的下一轮 settle `final_victory`；窗口改成**反复追问直到该页不再settle任何东西**（`record_ledger_event` 返回列表、报告字段 `ledger_events`），账本自己仍然守顺序（1..5 → victory → reward → entry_returned，最后一步才旋转）。
  3. 上一轮的团灭页与冷启动（见下）。**401 passed**。
- **实机（`--run-store`，从大厅起）**：`build/window-run-from-home.json`（159 次点击）→ `build/window-run-continue-1.json` → `build/window-run-continue-2.json`：从 HOME 一路打到 **BATTLE_VICTORY → RUN_CLAIM → RUN_REWARD_DIALOG → RUN_REWARD_CONFIRM → HOME → 又进场开下一局**（`STAR_GRACES`/`STAR_CONFIRM`/`INITIAL_GIFTS`/`GIFT_GET`/`GIFT_SEARCH` 都实机过了一遍）。账本 `active run 8de51ee3 team 4 floors=[1,2,3,4]`：那一局的五层已通，但结算事件因上面第 2 条而丢失，所以 rotation 当时没动；修正后的窗口会把当前这一局的结算记全并让 rotation 前进到 `team 1`。

## Prior continuation: 2026-10-07 14:00 local
- **用户的当前指令（m12942）**：从零开始驱动脚本打镜牢，我只负责看它卡在哪里、结合网络资料完善脚本。
- **冷启动打通（提交 `98db0dc`）**：`--flow launch` 过去被 `src/maalimbus/adb_preflight.py::foreground()` 拦住（客户端不在前台就抛 `RuntimeError('Limbus is not the uniquely identified foreground app')`）。现在新增 `foreground_any()`／`adb_device.foreground_any_of()`：**只有首个流程步是 `start_app` 的会话**才允许读「当前是谁在前台」并记进 `foreground_before`／`launched_by_flow`，由 Maa 自己的 start-app（绝不用桌面启动器）把游戏拉起来；其它会话仍是严格前检。实机：Android 桌面 → `start_app` → `TOUCH TO START` [846,810,222,41] 0.95 点掉 → `LUNACY` 出现 → `Confirm` 弹窗清掉 → 停在 `HOME`（前检期间 `clicks_sent` 为 0）。
- **团灭页（提交 `41ac26d`＋`b8324d0`）**：5 层 boss 把 12 人全灭后，游戏弹出「Floor In Progress 5/5 / All participating Sinners have been killed. / Remaining Units: 0/12」＋三行选择（Return to Stage Select／Retry Stage／Accept results…）＋ Confirm。新页 `BATTLE_DEFEAT` 默认选 **Retry Stage**（唯一能让这一局活下去的输入），而且**有界**（`--defeat-tries`，默认 2）；两个「放弃这一局」的行只登记、永不自动点；重试次数在 **Confirm 落地后**才 +1。**400 passed**，anchors **41 页 0 broken**。
- **实机从大厅驱动一整段（`build/window-run-from-home.json`）**：`HOME→DRIVE→MIRROR_ENTRY→ENTRY_CONFIRM→DUNGEON_TEAM（按账本选队）→STAR_GRACES（买 5 张）→STAR_CONFIRM→INITIAL_GIFTS→GIFT_GET→GIFT_SEARCH(refuse)→GIFT_SEARCH_FORGO→THEME_PACKS→MAP→…` 一路推进，159 次点击内**没有一次非设计内的停机**；窗口只是把 150 步预算用光（`passed: False` 是预算用尽，不是失败）。
- **轮换账本实机生效**：这一局由 `config/user-run-ledger.json`（`slots=[5,4,1,6,2,7,3] rotation=1 -> team 4`）驱动，报告的 `run_ledger` 记 `team: 4`；站上 floor 2 时账本自己记下第一条 `floor_clear: 1`（`active run 8de51ee3 team 4 floors=[1]`）。
- 教训：`tools/verify_anchors.py` 用默认参数跑（`41 page(s), 0 broken`）；手动传 `--template-root .` 会让 `battle_hud`/`tutorial` 的 evidence 解析失败并报 2 broken —— 那不是真回归。

## Prior continuation: 2026-10-07 04:25 local
- **实机 run114/115/116（`--stop-page HOME`）**：run114 从 floor 4 打到 floor 5 后停在 `page_unreadable_after_waiting`，run115/116 接着把 floor 5 的几场战斗打下去（每步都 `passed: true`，只有地图候选按设计轮换时记 6 次 `map_click_opened_no_panel`）。run115 用满 60 步预算（报告顶层 `verified_clear: False`、exit 1 ＝预算用尽而非失败），所以窗口的步数上限就是长局的唯一约束。
- **header 又一种 OCR 形态（提交 `7abfec1`）**：`ExploringFloor5`（词与 Floor 之间**没有空格**）此前不被 `HEADER_PATTERN` 接受 ⇒ 页面判 UNKNOWN。现在分隔符可选、floor 词用惰性 `\w{3,5}?`（贪婪会把 `Floor5` 整个吃掉、floor 号丢成 None）；测试钉 `evidence/runtime/window-20261007-034308/frame-0198.json`。
- **`--stop-page NAME`（提交 `c273643`）**：镜牢结算后游戏会自动回大厅并再次进场，长窗口会在调用者还没决定前就用旧队开下一局。现在命中该页即 `stopped: stop_page_reached` 并交回控制权（这一步也把「DUNGEON_TEAM 的队槽每次从账本现读」的改动带上，避免跨局用已退役的队）。
- **账本可重播种（提交 `0203482`）**：`seed_run_store(..., overwrite=True)` 只允许覆盖**从未记过任何东西**的账本（有 active run 或任何回执就仍拒绝），`tools/run_ledger.py seed --force` 走这条路。这是为了修「一局在接线之前打完、玩家顺序已经前进，而账本还指着旧队」的局面。
- **Windows 包：五个硬地板的证据可以申报了（提交 `49cfa6d`）**。`tools/build_windows_package.py --verified-dungeon-clear` 才把 `clear_evidence`（默认 `docs/acceptance.md`，带 sha256）写进 `build-info.json`，否则 `pending` 里保留 `full five-floor loop`。三个输入归档（MXU v2.5.1、MaaFramework v5.12.2、MXU 源码）都已在本机并逐一核对哈希，重出一次构建即可（产物落在 `build/windows-package-<uuid>/`，`dist/` 从未产出）。
- 全量测试 **398 passed**；`tools/verify_anchors.py` **40 page(s), 0 broken**。
- **待办**：等这一局（team 5）在大厅交回 → `tools/run_ledger.py seed --slots 5,4,1,6,2,7,3 --rotation 1 --force`（对齐到 team 4）→ 带 `--run-store config/user-run-ledger.json` 跑一整局，验证 `entry_returned` 之后 rotation 自己前进一格。

## Prior continuation: 2026-10-07 03:40 local
- **实机：地图卡死的两个真因都修掉，闭环重新稳定跑通。** `build/window-run111.json`（24 步）与 `build/window-run112.json`（30 步，`steps 32 / clicks 32`）都是「地图→节点面板→出战编队→战斗（Win Rate／START 交替）→奖励卡→层礼物→主题包」再回地图，没有再出现 `no_candidate_node_observed` 或 `page_unreadable_after_waiting`。
- **`MapProgress`（提交 `6f92953`）**：run110 在 floor 3「To be Cleaved」连出 7 次 `map_click_opened_no_panel`，日志里真正点过的 target 只有 `[1010,103]`/`[681,441]`/`[748,416]`/`[1819,709]`，而 `[681,441]` 与 `[748,416]` **交替重复 8 次**、可达的「?」节点 `[303,708]` 一次都没点到。真因是 header 的 floor 读数在 `3 / None / 3` 之间抖动（OCR 丢 token），旧代码 `if floor != map_floor:` 每次抖动都清空「已试过」。新 `src/maalimbus/map_progress.py::MapProgress`：**只有具名且不同的层号才开新一层**，`None` 读数保留层号与已试点；测试 `tests/test_map_progress.py` 三条。
- **header 尾部截断（提交 `6220f97`）**：run111 停在 `page_unreadable_after_waiting` 时，`evidence/runtime/window-20261007-030756/frame-0093..0100.json` 每帧都把标题读成 **`Explorin`**（掉尾字母 g、且没有 floor token），`HEADER_PATTERN`/`HEADER_LABEL_PATTERN` 都要求 `Exploring` ⇒ `map_header()` 返回 None ⇒ 页面判 UNKNOWN。现在两者共用 `HEADER_WORD = r'(?:Explori\w{0,3}|Before\s+Entry)'`；pack 行仍是身份闸门。测试 `tests/test_map_vision.py::test_the_map_survives_a_label_whose_tail_ocr_dropped`（钉 frame-0096）。
- **轮换账本接线（提交 `f70b204`）**：以前窗口永远带 `--team 5` 且不记账，轮换不自增。新增 `src/maalimbus/run_wiring.py`（纯函数，把「观察到的页」映射成**唯一**该记的账本事件：站在 floor n 证明 floor n-1 已清除、`RUN_CLAIM` 是最终胜利（需五层齐）、`RUN_REWARD_CONFIRM` 的 Confirm 是奖励到手、`DUNGEON_TEAM` 的 Confirm 是再入场；绝不上报会被账本拒绝的事件）、`tools/window_step.py --run-store`（用账本的队槽代替 `--team`，每个事件都带**它所来自的帧**做证据；被账本拒绝就记 `run_ledger_refused` 而不打断窗口）、`tools/run_ledger.py`（`status`/`seed`）与 `src/maalimbus/storage.py::seed_run_store`（拒绝覆盖已有账本）。已按用户口径播种 `config/user-run-ledger.json`：`slots=[5,4,1,6,2,7,3] rotation=0 -> team 5`。
- 全量测试 **390 passed**；`tools/verify_anchors.py` **40 page(s), 0 broken**。
- **待办**：用 `--run-store` 跑一整局（从大厅进场）验证轮换在结算后真的前进一格；然后才是 Windows 包（`dist/` 仍未产出）与邮件/体力兑换。

## Prior continuation: 2026-10-07 03:00 local
- **实机里程碑：一局镜牢从开局打到五层通关、领奖、再入场、第二轮已开打。** `build/window-run104.json`（领奖）、`build/window-run105.json`、`build/window-run106.json`（领奖→大厅→Drive→镜牢入口→确认入场→轮换队槽位→等级警告→星辉 Grace→起始礼物→放弃礼物搜索→主题包→地图→节点→出战编队→部署→战斗→回地图，30 步全 passed）。结算页是 "Exploration Complete"（Floor1..Floor5 各 6/6、Total Progress 100%、Starlight 15、Net Amount 7,556）。
- **这一段新命名的页（都带 anchors 页、计划分支与测试）**：`BATTLE_TIP`（点到技能卡弹出的 "Skill Effects" 说明浮层，提交 `b18ce58`）、`BATTLE_VICTORY`（'Victory' + 'EX-CLEAR'，自己不会消失，提交 `208866c`）、`RUN_CLAIM`（结算页四词同帧：Exploration/Complete/Total Progress/Claim，只领奖绝不翻页，提交 `6f8aae9`）、`RUN_REWARD_DIALOG`（'Exploration Reward' 弹窗，提交 `08526bb`）、`RUN_REWARD_CONFIRM`（弹窗 Claim 之后的 "Claim the rewards?" 确认，Cancel 进 `FORBIDDEN_CONTROLS`，提交 `52e5152`）。
- **`map_clicks` 排序修复（提交 `7a17842`）**：run107 在地图 "The Forgotten"（floor 1）连点四个**抬升的徽章框**（`(578,14)`/`(194,334)`/`(232,14)`）而面板一直不开；该层唯一可走的是红色「?」六边形，它的自身图标被读在 `(1087,409)`，手工 1920 空间点 `(1080,428)` **确实打开了节点面板** ⇒ 直接读自帧的 `lit_icon` 现在排在徽章抬升（`node_away_from_player`）之前。测试 `tests/test_map_vision.py::test_the_offered_question_node_outranks_the_lifted_badge_boxes`（钉 `evidence/runtime/window-20261007-023156/frame-0053.png`）。
- **循环守卫教训**：逐页守卫（`guard_page`）在页面每次跳变时清零，所以「`RUN_REWARD_DIALOG ↔ RUN_CLAIM` 来回跳」这种族内回环它看不见——新增 `CLAIM_FAMILY` 与 `--claim-tries`（默认 6）按族计步；`LOOP_GUARD_EXEMPT_REASONS` 只豁免「按用户规则必须连点同一面板」的剧情步。任何豁免都必须配一个步数预算，否则一次无效连点会烧掉整轮（run91 曾空点 40 步）。
- 全量测试 **378 passed**；`tools/verify_anchors.py` **40 page(s), 0 broken**。

## Prior continuation: 2026-10-06 13:20 local
- **管道场景自检（离线，可测）**：新增 `tests/test_pipeline_scenes.py`——冻结管道里 21 个 `limbus_scene` 场景名，断言每个名字都被 agent 侧模块（`agent/recognition.py` ＋ `src/maalimbus/*.py`）提到（防「改名/拼错/凭空发明」这类只在实机半途才炸的错）、冻结列表与管道现状一致、以及**普通 Click/Swipe/Key 节点必须带 `max_hit`**（`Custom`/`DoNothing` 豁免：它们的边界在自己的 Python 回调里，实测有 10 个 `action: Custom` 节点确实按设计不带 `max_hit`）。全量 **302 passed**（原 299）。
- **实机侧**：本轮发过一次**有界**探针（1 步、`--map-tries 2`）确认软锁仍在：MAP 点节点 → `map_click_opened_no_panel` → 驱动如实停机，未继续点击。仍需用户手工结算/结束那一局或重启客户端。

## Prior continuation: 2026-10-06 13:00 local
- **P4 的第一块（离线、可测）：预算闸门——出厂即「什么都不许花」**
  - 新增 `assets/resource/base/budget.json`：`status: "pending"`、`module_budget: 0`、`spent: 0`、`conversion_step: 1`、`allowed_purposes: ["enkephalin_refill","module_conversion"]`，`note` 写明这是用户硬约束（模块预算 0/pending）的出厂态，**只有用户明确给额度才可把 status 改成 active 并提高 module_budget**。
  - 新增 `src/maalimbus/budget.py`：`load_budget(path)`（校验 version/status/module_budget≥0/spent≥0/conversion_step≥1/allowed_purposes 合法性，非法即 `BudgetError`）、`plan_spend(amount, *, budget, spent=None, purpose=...)`、`apply_spend(...)`（额外给出 `spent_next` 供持久化）。拒绝理由按检查顺序：`budget_not_configured`（无表或 `status != active`，**出厂态就是它**）、`budget_amount_must_be_positive`、`purpose_not_allowed`、`budget_zero`、`budget_exhausted`、`request_exceeds_remaining`、`amount_not_multiple_of_step`；全部通过才是 `within_budget` 并给出 `spent_after`。
  - 调用约定（写进模块 docstring）：**先问预算、再发输入**——一次拒绝就是「没有点击」的理由，符合「不买额度不重置」与「有界点击」。
  - 测试 `tests/test_budget.py` 7 条：出厂态/Pending/零预算/无表全部拒绝、六种非法表被拒、金额与 purpose 校验、账本触顶与超限、允许时给出应持久化的账本（拒绝时 `spent_next` 不变）、`conversion_step` 整步门、显式 `spent` 覆盖表值且表本身不被改动（纯函数）。全量 **299 passed**（原 292）；`tools/verify_anchors.py` 仍 **22 page(s), 0 broken**。
  - `docs/script-mode-plan.md` §12 的 P4 条目改为「已实现（离线）＋三条待办」（接实机兑换入口并记录 refusals、邮件每日锚点、Windows 包 OTA）。
- **实机侧**：floor 3 地图软锁**依旧**（本轮未拍帧核对以外未发任何输入）；需要用户手工结算/结束那一局或重启客户端后才能继续 P0 实机验证。

## Prior continuation: 2026-10-06 12:40 local
- **P3 接线：`map_vision.route_decision` 用策略表排序（离线，可测）**
  - `route_decision(header, size, *, current=None, cleared=(), candidates=(), policy=None, kinds=None, context=None)`：仍是「先证后选」——`map_header_not_identified` / `current_position_not_proven` / `no_unvisited_candidate_observed` / `no_unvisited_reachable_node` 四道拒绝不变；**多个未访问候选**时若给了 `policy`（`route_plan.load_policy` 的表）与 `kinds`（节点 id → 本帧读到的种类），改由 `route_plan.plan_route` 排序，返回 `{'next_node', 'reason': 'policy_ranked_candidate', 'plan'}`；种类读不出的候选被跳过，**全体读不出则拒为 `route_kind_unknown`**（仍是拒绝，不是猜）；只有一个候选时不做多余排序，仍返回 `single_unvisited_candidate`。凡不传 `policy` 的调用方（含 `tools/map_live_observe.py:120`）语义逐字不变。
  - 实机冒烟（离线喂 `{'floor':3,'pack':'Repressed Wrath'}` + 三个候选 kinds `shop/abnormality/boss`）→ `next_node='r'`、`reason='policy_ranked_candidate'`、`plan.score=3.0`，`ranked` 依次为 boss 3.0 / abnormality 1.8 / shop 1.2。
  - 测试：`tests/test_map_vision.py` 新增 3 条（策略排序并带出 `ranked`、无人读出种类时拒绝而不是排序、有种类可读时跳过读不出的并把 `regular` 选中、单候选与无 policy 路径逐字不变）。全量 **292 passed**（原 289）；`tools/verify_anchors.py` 仍 **22 page(s), 0 broken**。
  - `docs/script-mode-plan.md` §12 的 P3 待办缩为两条：商店/融合（Wishmaking）计划与预算门限、需要一次实机映射出的真实 floor-graph。
- **实机侧**：floor 3 地图软锁**依旧**（本轮只拍一帧核对：mean 11.59，与软锁期一致），未发任何输入。

## Prior continuation: 2026-10-06 12:20 local
- **P3 的第一块（离线、可测）：路线打分策略表与打分器**
  - 新增 `assets/resource/base/route-policy.json`（version 1）：按八类节点（`boss`/`elite`/`focused`/`abnormality`/`event`/`regular`/`shop`/`empty`，沿用 LALC 的 legend 分类）给权重，另加三个修正项 `avoid_wounded` 2.0、`promote_fusion_shop` 1.6、`push_boss_on_last_floor` 0.8；`note` 明说这是**可编辑的偏好表、不是游戏内部数值**。
  - 新增 `src/maalimbus/route_plan.py`：`load_policy(path)`（校验 version、权重键必须是已知种类、修正项必须是已知名字，非法即 `PolicyError`）、`score_node(kind, *, policy, context)`（返回 `{kind, score, reasons}`，未收录的种类返回 `None`）、`plan_route(candidates, *, policy, context)`（`candidates` 是 `{id, kind, box?}`；**只给种类已知的候选打分**，其余跳过；全部无法打分 → `refused='route_kind_unknown'`，空候选 → `route_candidates_empty`；同分按输入顺序定序，返回 `target/box/kind/score/reasons/ranked/refused`）。
  - **命名澄清（避免踩坑）**：`floor-graph.json` 在 `docs/script-mode-plan.md` §4 里是**运行时每层模型**（节点/连线/行列/包名/层号，由地图感知每层写一次），所以策略表另起名 `route-policy.json`；`route_plan.py` 只负责给那个模型交来的候选打分，不读像素、不发明节点。
  - 测试 `tests/test_route_plan.py` 8 条：shipped 策略覆盖全部八类且不含未知键、非法策略被拒、按分数取最高并带出 `box`、无法打分的候选被跳过且全盲时拒绝、受伤时精英被普通战反超（`wounded_penalty_2.000`）、待融合时商店反超精英（`fusion_shop_bonus_1.600`）、末层推 Boss 且同分按输入顺序、纯函数稳定性（同输入两次调用结果相同）。全量 **289 passed**（原 281）。
  - `docs/script-mode-plan.md` §12 的 P3 条目改为「已实现（离线）＋待办三条」（让 `map_vision.route_decision` 接上每层 floor-graph、商店/融合计划与预算门限、需要一次实机映射验收）。
- **实机侧**：floor 3 地图软锁**依旧**（本轮只拍了一帧核对：mean 11.67，与软锁期一致），未发任何输入；需要用户手工结算/结束那一局或重启客户端后才能继续 P0 的实机验证。

## Prior continuation: 2026-10-06 11:55 local
- **P1 自检与采集闭环补齐（离线，`docs/script-mode-plan.md` §5.2/§5.3 的两条「下一步」）**：
  - `tools/capture_anchors.py`：一条命令采集并登记锚点。`--label/--from/--box/--page`，裁图→缩到 1280 基准→写 `assets/resource/base/image/<组>/<名>.png`→登记
    `{id,kind:'template',template,roi,threshold,box,note:'captured from …'}`（`--kind geometry` 登记 `verified_on{frame,sha256,box,source}`）。
    写完**立刻回放这一帧**：不命中就 exit 1 并删掉半成品；重复 id 要 `--force`；`--dry-run` 只校验不落盘。真实帧实测
    `--label battle.start_label --from evidence/runtime/window-20261006-103550/frame-0044.json --box 1518,738,60,28 --dry-run` → `score=0.9932`、`observed box=[1518,738,60,28]`、journal sha 与 png sha 一致。
  - `tools/verify_anchors.py --frame <png|json>`：只对 template/geometry 控件跑「当前帧自检」，逐条打印 `box / expected / drift / score`，漂移即 exit 1；裸帧没有 OCR 所以 identity 锚点不校验（报告里显式写明），`geometry` 在别的帧 sha 上是 `skip`（未证明）而非失配，`--strict-geometry` 才判失败。
  - 关键坑：`anchors._pixels()` 用 `int()` 截断而不是四舍五入，所以按框算出的 roi 可能比模板**少一个像素**（表现为 `roi smaller than the template`）——采集时把 roi 远端各 pad 1 px 并在条目里另存精确的 `box`，自检的漂移就以 `box` 为准。
  - 测试：新增 `tests/test_capture_anchors.py`（8 条）与 `tests/test_verify_anchors_frame.py`（5 条）；全量 **281 passed**；`tools/verify_anchors.py` 仍是 **22 page(s), 0 broken**。
- 实机仍停在「floor 3 地图不接受节点点击」的状态（上一段记录），本轮**没有再对设备发任何输入**。

## Prior continuation: 2026-10-06 11:30 local
- 实机（MuMu / ADB 127.0.0.1:16416）在 floor 3 地图（`Exploring Floor 3` / `Repressed Wrath`）停住：
  **地图可以拖动、HUD 按钮可以点，但地图节点层不接受任何点击**（点节点后 `page_after` 仍是 MAP，无 NODE_PANEL）。
- 已排除的三种解释：坐标空间（`adb shell wm size` = `Physical size: 720x1280`、density 240 ⇒ 横屏 1280×720，
  而 Maa/证据帧是 1920×1080，正好 1.5×）、输入通道（同一页点右上「?」(1233,207) 能打开 Active Effects 弹窗，
  `--swipe` 能平移地图）、结算窗口太短（`--rounds 4 --interval 5` ≈ 20 s）。
- 实测无效：左发光节点中心与四边、玩家节点自身、大路径箭头、双击、900 ms 长按、Enter 键；
  实测有效：地图平移、`?`/`i` 弹窗、队伍按钮（打开队伍页）、入口页 ▶/◀/圆点、
  **入口页左上返回箭头 `--click-box 112,46,40,40` → `page_after=MAP`**（⇒ 那一局并没有结束，只是 Mirror Dungeon
  菜单页叠在地图之上）。
- 对照 LALC（本机 `D:\Program Files (x86)\lalc` 与 `D:\scripts\lalc`）：同类症状有专门兜底 `mirror_enter_last_week`
  （模板 `previous_session_expired`，文案 "The previous session has expired. Please claim your rewards."）→ 直接报错
  「请手动结算上周的镜牢再启动 | Please finish your Dungeon and restart」；其 `exec_mirror_select_next_node` 也是
  点节点 → 等 connecting 消失 → `node_press("enter")`，失败就回初始页。
- **按硬约束不再触碰该局**（不重启游戏、不点 `Halt Exploration`、不买/不兑换），已请用户处置；
  脚本侧维持 `no_candidate_node_observed` 停机，绝不盲点。
- 新增诊断开关 `tools/window_step.py --swipe x1,y1,x2,y2[,duration_ms]`（一次手势，与 `--click-box` 共用 before/after
  记录，`goal = 0 if (boxes or swipes)`），用于证明「地图能拖」；全量 **269 passed**。
- **联网核查（本轮补做，回答「为什么之前遗漏」）**：
  - 之前只参考了 LALC（PC 端 Python 应用），**漏掉了 Maa 官方的原生 Limbus 项目**：
    [MaaXYZ/MAALimbusCompany](https://github.com/MaaXYZ/MAALimbusCompany)（66★，最后推送 2024-08-11；`assets/interface.json`、
    `assets/resource/base/pipeline/{startup,combat,awards,daily,psychube,wilderness}.json`）——它**没有镜牢**管线（2024 年版本），
    但 `interface.json` 是 ProjectInterface V2 的原生写法，做 Windows 包（MXU/PI）时应作为格式基准。
  - 官方公告（Steam 新闻 API `ISteamNews/GetNewsForApp?appid=1973530`）核查到两条与本情况相关的：
    「Ver. 1.115.0 Known Issues Hotfix & **Save Restoration** Added」（2026-09-24）——Project Moon 为 **Canto X 的软锁**加了
    「设置 → Sisyphe 标签页底部 Restore Save」的兜底，但**只覆盖主线任务软锁，镜牢不在其列**；
    同公告还修了「某些楼层在较窄宽高比下地图被裁切」——与我们「地图能拖、节点不响应」不是同一现象。
    「Known Issues After the Oct. 1st, 2026 Scheduled Update」列出「(The Shadowed) 战斗中进度无法推进」。
  - 结论不变：镜牢卡死属 LALC 也要求人工处置的一类（`mirror_enter_last_week` → “Please finish your Dungeon and restart”），
    脚本侧继续只做「识别 + 停机」，不做任何猜测性补救。

## Prior continuation: 2026-10-06 04:35 local
- 新页面落地：**遭遇奖励卡**（`Select Encounter Reward Card`）。清掉一个节点后游戏交回一张
  「选 1 张」的奖励卡（`Selectable 0/1`），确认前必须先在卡面上点一下。这一页同时带 `X Cancel`，
  所以它必须先于通用 UNKNOWN_DIALOG 被命名，否则整页会被当成「未知弹窗只观察」而卡死——
  实机 `evidence/runtime/window-20261006-034714/frame-0022.json` 就是这样停下来的。
  - `assets/resource/en/locale.json`：`encounter_reward` = `^Select Encounter Reward Card$`、
    `selectable` = `^Selectable(?:\s*\d{1,2}\s*/\s*\d{1,2})?$`。
  - `src/maalimbus/vision.py`：`REWARD_CARD` 分支（标题 + `Selectable` + `Confirm` 三证据）放在
    通用 dialog 否决**之前**。
  - `assets/resource/base/anchors.json`：新页 `reward_card`（identity 三条 + controls 两张卡框、
    `Confirm` [1128,764,168,49]、`X Cancel` [688,768,154,45]）。`tools/verify_anchors.py` → **11 页 0 broken**。
  - `src/maalimbus/window.py`：`REWARD_CARD` 计划读计数——没选满就点第一张卡（`advance=True`，
    只有像素变化能证明选中），选满才点 `Confirm`；`reward_card.cancel_button` 进 `FORBIDDEN_CONTROLS`
    （拒绝已到手的奖励是禁止输入，登记它只为让页面可被识别）。
  - `src/maalimbus/reward_vision.py`（新，纯函数）：`counter_state(record)` 从帧的 OCR token 里读
    `chosen/required`。**关键坑**：未选卡时 OCR 给两个 token（`Selectable` + `0/1`），选中后会并成一个
    `Selectable 1/1`（`evidence/runtime/window-20261006-035257/frame-0002.json`），第一版严格匹配
    因此掉进 UNKNOWN_DIALOG；现在在右上波段内搜索计数，`tests/test_reward_vision.py` 4 个用例钉住两种写法。
  - 循环守卫加豁免 `LOOP_GUARD_EXEMPT = ('TUTORIAL', 'BATTLE_HUD')`：一场战斗本来就会反复
    「Win Rate → START」，否则 3 回合就被误判成循环。
- 实机推进（`build/window-reward2.json`，4 步全 passed）：`REWARD_CARD`（点 `Confirm`）→
  `REWARD_CARD`（再点 `Confirm`，第一次点击落在奖励卡出场动画上被吃掉，第二次生效）→ `MAP`
  → `NODE_PANEL` → `PRE_BATTLE_TEAM`。**全程没有点过 `Cancel`，也没有重复领奖**。
- 全量 **228 passed**。

## Prior continuation: 2026-10-06 04:15 local
- 这一轮全是「窗口自己在实机里被带偏」之后修掉的真实缺陷，每条都有实机帧 + 回归测试：
  - **浮层身份收窄**：`overlay_vision.triangle_box` 现在要求金色连通域「又紧凑又尖」
    （`MIN_FILL=0.28`/`MAX_FILL=0.72` 填充率 + `MIN_LEAN=1.8` 左右四分之一列像素比）。
    实机根因：出战前队伍页右侧的暖色 **Details 按钮**（47×41、填充均匀）被判成教学书的 ▶，
    窗口在 `evidence/runtime/window-20261006-034009/` 里连点 12 次，把「E.G.O Resource Overview」
    详情面板开了又开。`window_step.overlay_hit` 也**不再把三角当身份**，只用「轮播圆点」＋
    「书自己的 ▶ 模板」，三角只用来给浮层计划定位要点的控件。
  - **analyze 事件没有 `ocr`/`size`**：`map_observed`/`battle_observed` 只带语义字段
    （scene/floor/pack/各 box），所以 `overlay_hit` 的圆点判据与 `team_state` 的徽章读取**在实机里一直是死代码**
    （`team` 恒为 `null`）。`window_step.observe` 现在从最新 `frame-*.json` 补齐 `size` 与 `ocr`。
  - **循环守卫**：新增 `--loop-guard`（默认 3）。让 `successor_ok` 容忍 TUTORIAL 治好了「误判即停机」，
    但也藏起了循环——实机 `build/window-run4` 用同一对动作（TUTORIAL 点 ▶ → 队伍页点 To Battle!）
    跑了 12 个来回且每一步都 `passed`。现在同一 `(page, action, node/target)` 计划重复到阈值即停机
    （教学书除外，它本来就该一张张翻）。
  - **`--unknown-rounds` 默认 6 → 12**：胜利横幅本身就把画面占住约 25 秒
    （`evidence/runtime/window-20261006-033014/`），6 轮 × 5 秒不够，窗口会在战斗刚结束时报
    `page_unreadable_after_waiting`。
- 实机进展（`build/window-run5.json`）：`PRE_BATTLE_TEAM`（**12/12 已满**，战绩 `Backup Deployed 5/5`）
  → `To Battle!` → `BATTLE_HUD` → `Win Rate` 自动指派 → `START` 提交回合 → 回合结算（UNKNOWN）
  → 再观测已回到 `BATTLE_HUD`，窗口可以继续推进同一场战斗。
- 全量测试 **222 passed**；`tools/verify_anchors.py` 10 页 0 broken。

## Prior continuation: 2026-10-06 03:45 local
- **实机：窗口第一次自己把一局推进起来了**（`tools/window_step.py`，全部是被证明过的点击，零猜测坐标）：
  MAP → 点「离玩家最近的候选节点」→ **NODE_PANEL**（此前点远处的宝箱节点毫无反应，见下）→ 点 `Enter` → 过场 →
  教学书浮层（连点 ▶）→ 出战前队伍页（12 张卡逐张入队，0/12 的 Battle! 是暗的）→ `To Battle!` → 战斗 HUD
  （`Win Rate` 自动指派 → `START` 提交回合）→ **VICTORY**（`evidence/runtime/window-20261006-033014/`）→ 回到 MAP。
- 这一路上修掉的真实缺陷（每条都有实机帧与回归测试）：
  - `map_vision.map_header`：实机把抬头拆成 `Exploring` ＋ `Floor` 两个 token，风格化层数数字常常没有被 OCR 读到 →
    新增 `HEADER_LABEL_PATTERN`/`HEADER_FLOOR_PATTERN`，**只有 label 也认**（下面仍必须命中主题包行），层数允许 `None`。
  - `overlay_vision`：`triangle_box` 原来返回「带内全部金色像素的包围盒」，于是战斗 HUD 右侧 E.G.O 图标列（x≈.95、y .35–.49）
    被当成教学书的 ▶，窗口把整个战斗页误判成浮层并连点图标列 8 次；改成 `connectedComponentsWithStats` 只取**紧凑连通域**
    （面积 200–4000、宽高比 .5–1.7、边长 ≤9% 帧宽），并新增 `carousel_dots`（书的轮播圆点行）作为主身份。
  - `battle_vision`：第三种 Win Rate/Damage/START 布局（x 比旧的两套右移约 290px）落在波段外 → 波段放宽到 `.95`。
  - `window_step`：MAP 候选改为「按到玩家节点的距离排序」，并加 `--map-tries`：不可达节点会吞掉点击（页面仍是 MAP），
    于是跳过它试下一个，而不是直接停机。
  - 教学书的**出口**：最后一页只剩左侧 ◀（没有前进控件），此前直接停机；现在新增锚点 `tutorial.book_close`
    （书自己的抬头 ⟵，实机点它得到 `PRE_BATTLE_TEAM`，不消耗资源），有 `previous`、无前进控件时改点它。
  - 教学书会在**任意**操作之后压上来（实机 `build/window-run3.json` step1：点 `To Battle!` 后书盖住了战斗页），
    旧逻辑会记 `unexpected_successor` 停机；现在 `successor_ok` 把「后继页面是 TUTORIAL」一律视为可接受，
    由下一步把浮层点掉。浮层自己的计划不受影响（仍要求点完浮层消失）。
- 全量测试 **221 passed**；`tools/verify_anchors.py` 10 页 0 broken。
- 下一步：把这局打到第 5 层并领奖（`pending` 里还缺：结算领奖、层礼赠、商店、事件、下一层、轮换再入场）。

## Prior continuation: 2026-10-06 04:05 local
- 按 Plan v1 先补两件「线上只读数值」的地基，全部离线（无设备、无点击、未改运行行为）：
- ① 社区数据管道：`tools/fetch_identity_catalog.py`（`GitHubState` ETag/限流缓存 + 按 pinned commit 取 raw 与 commit 日期）
  → `src/maalimbus/identity_catalog.py`（纯函数合并）→ `assets/resource/base/identity-catalog.json`：
  **128 人格 / 122 带关键词**，关键词由技能里的 `buffKeyword` 反推（`Burst`=破裂、`Breath`=呼吸法、
  `Bleeding`/`Laceration`=流血、`Vibration*`=震颤、`Sinking`=沉沦、`Charge`=充能）；抽查吻合（剑契组杀手=Poise、
  Seven 南部 6 科=Rupture、多裂纹事务所收尾人=Charge、脑叶 E.G.O 赤瞳=Bleed）。**覆盖率限制**：
  `flaglow/LimbusStaticData` 停在 2025-01-23（LLC 中文包活跃），catalog 只是离线事实快照，**不能**当作
  「玩家现有的全部人格」，线上仍以游戏内 filter 为权威。提交 `74f53fb`。
- ② 锚点注册表 + 自检：`assets/resource/base/anchors.json` + `tools/verify_anchors.py` + `src/maalimbus/anchors.py`
  （8 个单测）。三类锚点 `ocr` / `template`(1280 基准，验证时按帧宽等比放大) / `geometry`
  （`verified_on{frame,sha256,box,source}`，**只在自己那一帧算已证明**，换帧即 `stale`，绝不静默沿用旧坐标）。
  注册表带 `pending` 清单，显式列出尚未证明的页面：人格 filter、结算领奖、层礼赠、商店、事件、下一层、轮换再入场。
  离线回放 5 个已验证页面全绿（模板锚点实测在 1920 帧上 1.5× 命中 `image/battle/win_rate.png`），
  报告写 `build/anchors-report.json`。全量测试 **180 passed**。
- 下一步＝**验证窗口**（用户 m01490 的选择）：把 `pending` 里的页面在一次连续实机里一次看完并钉进注册表，
  之后线上只读「验证过的数值接口」。

## Prior continuation: 2026-10-06 02:17 local
- 用户要求（m01490）：写脚本前先参考 LALC，再参考 Limbus 中文 wiki/攻略摸清机制，然后**先 plan 一个最聪明的脚本模式**；
  「把需要图片验证的部分尽量压缩到一个时间段去做，其他地方在线上保留一个验证后的数值接口就好，而不是走一步看一步」。
  框架 MaaFramework、实现参考 MaaEnd、原型/机制参考 LALC。
- 产出 `docs/script-mode-plan.md`（Plan v1，只读设计，未连设备、未点击、未改运行行为）：四份「数字/契约」文件
  （`anchors.json` / `floor-graph.json` / `inventory.json` / `run-ledger.json`）、三个感知窗口（开轮前标定 / 每层一次整图解析 /
  战斗与结算）、分层锚点 + 锚点注册表 + `verify_anchors.py` 自检 + `capture_anchors.py` 一次点击采集、自动配队四条路径
  （成队码/已存队槽 → 排序法 → 一次扫描 → 人工导入）、镜牢机制基线（5 层、Boss 前必有商店、领奖耗 5 Enkephalin、周加成 3 档、
  星光是 +层数/Hard +4×层数、融合点数与 60/90/99% 命中、关键词内名 `Burst`=破裂）、照抄清单、P0–P4 路线与验收。
- 四个只读调研（子代理）要点：**MaaEnd 不是边狱巴士项目**（是《终末地》，只作 MaaFramework 工程范本：`"task":[]`+`"import"`、
  `Interface/` vs `__` 节点、`SceneManager`+`[JumpBack]`、ExpressionRecognition、ImageCropper「文件名即 ROI」、CI schema 校验、
  MirrorChyan OTA、已弃用后台 Win32 截图）；真正的 MFW 边狱项目 `MaaXYZ/MAALimbusCompany` 66★ **2024-08 已弃坑**，
  是反面教材（只点自带 WinRate/推荐阵容、无地图数据层 → 遇镜牢即崩）；LALC 硬编码 1280×720、缺图即 `raise KeyError`、
  整包覆盖更新、AGPL-3.0；人格数据源 = `LocalizeLimbusCompany`（中文名/关键词/礼物，活跃）＋`flaglow/LimbusStaticData`
  （rank/抗性/被动，2025-01 停更），**id 对齐**；中文 wiki（huijiwiki/fandom）实测 Cloudflare 403，改 `wiki.biligame.com`。
- 待用户拍板项见该文档 §13（许可、游戏内 filter 能否多选、是否自建数据镜像、AALC 框架归属未核实）。

## Prior continuation: 2026-10-06 01:40 local
- First real combat from the stopped231221 session, using the discovery-based binding
  (MuMu 自带 adb、EmulatorExtras 截图、AdbShell|MinitouchAndAdbKey|Maatouch 输入) and one
  bounded click per step: START 点击把战斗从 turn1 推到 turn2，随后回合结算出现胜利演出
  "…have dealt a fatal blow to your enemies"、`Gain Corpus Ingredient`、`Sloth DMG Up +1`、
  `TOTAL 132`（evidence/runtime/battle-step-20261006-013320/frame-0001.png）。全程无按键输入。
- 关键几何：`START` 文字只是横幅，真正的按钮是横幅下方的暖色圆钮——
  `battle_vision.warm_control()` 读该控件，钉住 label(1060,738,66,30) vs control(1038,771,121,133)；
  Win Rate/Damage 按钮会随棋盘横向移动（x1300-1362），自动分配波段加宽到 .58-.74 / .58-.75，
  两种布局都有测试。提交 82863aa、17101be。
- 阻塞并已停下：胜利演出后 HUD 显示 `TURN 3`、有 Win Rate/Damage 但**始终没有 START**；
  连续 8 次 auto_assign 点击无任何状态变化 → 已停止点击，并在 tools/battle_step.py 增加
  `auto_assign_had_no_effect` 标记（pass=False）以免再盲重复。是"该回合要手动点技能/需要别的控件"
  还是"战斗已处于结束态"尚无定论；未再发输入。未声称通关、领奖、轮换或再入场。

## Prior continuation: 2026-10-06 01:20 local
- ADB binding corrected to the documented path. Manual
  `docs/zh_cn/2.4-控制方式说明.md` (and the official Python sample `sample/python/demo1.py`)
  require an ADB controller's screencap/input methods to come from
  `MaaToolkitAdbDeviceFind`, never a hand-picked combination. New
  `src/maalimbus/adb_device.py` (`discover`/`input_policy`/`pin_input`/`build`) and
  `tools/adb_discover.py` implement it; every live tool plus `tools/run_native.py`
  now discovers the device first. Read-only discovery reports MuMu as
  `MuMu安卓设备-1-MuMuPlayer v5+` (127.0.0.1:16416, MuMu's own
  `D:\Program Files\Netease\MuMu\nx_main\adb.exe`, `screencap EmulatorExtras=64`,
  `input AdbShell|MinitouchAndAdbKey|Maatouch` with `extras.mumu.enable=true`), i.e.
  EmulatorExtras screencap is available while EmulatorExtras input is not.
- The previous binding hardcoded platform-tools adb with `Encode` + `Maatouch`,
  which bypassed MuMu's native channel; that is the change the user flagged
  (paraphrased m00950: the clicking interfered with their mouse). No input has been
  sent since; 166 tests pass, including new pure offline contracts for the policy.

## Prior continuation: 2026-10-06 01:05 local
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
## Continuation: October9 Mirror task options

- Installed modified GUI PID22484 now has actual top-level handle10360354 and
  title MaaLimbus v0.1.1 at the exact dist path. The previous consent/no-window
  observation is stale. Kept the same process; no restart/replacement/input.
  Window identity alone does not accept native settings rendering or persistence.
- Mirror task adds initial gift system, gift-search refusal and per-launch step
  bounds, each on independent inert native nodes, validated and merged into
  MirrorLoop parameters. Saved defaults retain launch settings; no new paid
  search or resource authorization.21 focused tests and actual native six-task
  resource/independent three-option parsing passed with zero controller/input.
  Final740Python79.39s/1Windows symlink permission skip passed after updating old
  two-option-only fixtures; build/mirror-task-options-full-tests-final.txt and
  build/mirror-task-options-verification.json retain the results and source hashes.
  These changes are source-only while installed GUI remains d0d5352. Battle,
  theme/gift editors and actual installed interaction/restart remain open.
- Current Team7 INITIAL_GIFTS and scope4734 remain unchanged, with no live runner.
  No repeated star/entry/Confirm or other game input. FGO untouched and deferred.
## Continuation: October12 mirror loop repairs and packaging gate

- Live runs on the real window (evidence/runtime/window-20261012-023229,
  window-20261012-024300, logs build/live-deploy*.log) drove the deployment
  transaction into two stop classes; both are repaired with tests. The
  participant counter was read from a fixed ROI (1700,754,128,58) with
  single-line recognition and returned nothing on three consecutive live frames
  while 'Total Participants 8 / 12' was on screen. The agent now reads
  1680,738,180,92 with detection enabled and pattern \d{1,2}\s*/\s*\d{1,2}; the
  same live loop then read 9/12..12/12 with zero counter rereads.
- Deployment order reuse is implemented from the user report that a party is not
  rebuilt every battle: every deployed card prints its place in the order.
  team_vision gains assignment_box/assignment_numbers/carries_saved_order,
  deployment_transaction.prepare accepts the printed numbers and reports
  inherited_order, and the PRE_BATTLE_TEAM plan submits the saved order without
  Clear Selection when the print already carries it. 107 focused and 980 suite
  tests pass; a live frame whose print matches the saved order has not been
  observed yet, so that rule stays source-verified only.
- Packaging was blocked and is repaired: assets/interface.json grew to 3,727,668
  bytes, past the 2 MiB guard in update_install.metadata, so make_local_app
  failed with StageError Invalid application metadata. storage.py now exposes
  INTERFACE_LIMIT (16 MiB) and read_json takes an explicit limit; metadata and
  the three tools that read interface.json use it. dist/MaaLimbus was rebuilt
  from this tree (source_dirty, commit a6ac321, self_test and agent_self_test
  true, 40 private files preserved) and the frozen product carries maatouch, the
  agent exe and the 3,727,710-byte interface.json.
- The packaged product was then made to run the entry MXU starts:
  tools/verify_packaged_mirror_loop.py launches dist/MaaLimbus/agent/MaaLimbusAgent.exe
  over Maa IPC, binds the installed resources and posts MirrorLoop on a real device
  controller. The frozen agent registers limbus_mirror_loop and ran the loop live
  (evidence/runtime/packaged-mirror-20261012-032032): one team card was clicked and
  the run then stopped on 'Deployment successor participant count not proven'. That
  stop is a product-path defect, not a planner one: the whole run has one
  map_observed and one frame, so the successor read handed the loop the pre-click
  page, and deployment_transaction.observe compared the new count against 2/12.
  MaaObserver.observe now re-runs a node that recorded nothing and stops with
  'the observation node recorded no page for this frame' rather than returning a
  stale event, guarded the same way for the battle node; three cases in
  tests/test_runner.py drive it through an injected node.
- Shop purchase/refresh/skill replacement and applying learned labels to mirror
  decisions remain open. The shop plan still leaves without buying and the shop
  page has no offer anchors; semantic_labels is consumed by the offline
  collection tool only and live frames still report neural_sinners status off.

## Continuation: October12 shop buying and shelf refresh

- The user reported that the loop enters the shop and buys nothing. The shelf is
  now read offline in src/maalimbus/shop_vision.py: offers pairs a price box with
  the name box centred under it, click_box puts the art centre 58 px above the
  price box top, and refreshes returns both Refresh buttons with their costs. On
  the real shelf frame evidence/runtime/window-20261012-024300/frame-0173.json it
  reads currency 1008 and the six live offers (Replace Heathcliff's Skill 77,
  Uncapped Defibrilator 147, Polarization 158, Scalpel 155, Curriculum Vitae 155,
  Prejudice 152) with Refresh 15 and Keyword Refresh 90.
- Buying spends the in-run currency only. The module budget gate in
  src/maalimbus/budget.py covers Modules/Eenkephalin and is untouched, so the old
  note that left the shop as the only budget-safe input no longer applies to
  shelf purchases. Buying is gated by the gift plan instead: wanted_offers filters
  the shelf through gift_plan.wanted, so only names the plan asked for can be
  bought.
- src/maalimbus/window.py plan_step now answers a shop page with, in order, the
  purchase question's own Confirm, a planned offer, a plain shelf refresh bounded
  by settings.shop_refreshes (default 2, --shop-refreshes), and finally Leave.
  runner.shop_state reads the shelf each step, books purchases in shop_bought,
  counts refreshes, and never buys the same name twice in one run.
- The purchase question is its own named page. vision names SHOP_PURCHASE when the
  shop and leave labels are present and a Confirm and a Cancel sit in the dialog
  bands; on that page the only input the plan may send is the Confirm it read from
  the frame, and an unreadable Confirm records instead of clicking again.
- 1013 tests pass with one skip (13 new shop_vision cases, 8 runner cases, 5 plan
  cases, one vision naming case). Two live gaps remain: the purchase dialog's own
  geometry has not been seen (its bands are the superset the leave, gift-warning
  and reset dialogs already sit inside), and the run that was to take the shop
  evidence stopped one page earlier on a floor gift pick, where
  floor_gifts.parse_trial refuses a trial whose text is not fully numeric grammar
  ('floor_gift_enemy_trial_unknown', evidence/runtime/window-20261012-034813
  frame-0079.png). That strictness is deliberate: rank() prices the pick from the
  trial, so an unreadable trial is a stop rather than a guess.

## Continuation: October12 installed task verification repair

- Rechecked the live game without input: Maa foreground LimbusCompany and GIFT_PICK
  0/2 remain, evidence/runtime/sinner-sample-20261012-081957. Current source run
  f855ac82/team7 differs from the installed copy's empty active ledger; those
  files must not be silently overwritten or treated as the same state.
- Retained unpriced trials as explicit excluded offers, without assigning unknown
  penalty values. Three supported offers on actual frame0079 can still rank; the
  unknown Bloody Gadget defense-final-power trial cannot be selected. Duplicate
  or missing evidence still refuses.33 floor cases and88 combined focused cases
  passed; actual selection/receipt remains pending.
- Packaged verifier now defaults to MirrorTask/MainTask, the real PI Start entry,
  with Agent ownership of the canonical controller lease and an explicit optional
  private-state binding. Removed hardcoded team5. Entry wiring, bounded progress
  and dungeon completion are separately reported: a deployment successor failure
  cannot pass merely because mirror_loop_start was recorded. Actual installed
  rerun and GUI Start remain to be verified.
- Actual installed MainTask selected Oracle once, then stopped with its pick
  pending. Native Maa log proves the root cause: Context.check_hit_count skipped
  WindowMapObserve after its first max_hit=1. Nested Context.run_task shares that
  counter, unlike independent CLI tasks. AgentTasker now uses the documented
  clear_hit_count API exclusively for WindowMapObserve/WindowBattleObserve before
  each read, preserving input hit counters/transactions.35 focused tests passed.
  Pending selection must resolve from a fresh counter, never be clicked again.

## Continuation: October12 native successor and shop transactions

- Installed MainTask now exposes later fresh observation rather than reusing the
  old screenshot. The current Oracle selection is visible at1/2; pending retained,
  no repeated input. Its selected +1 badge full-screen confidence.779889 failed
  the original.85 gate. Two independent native narrow crops read +1 at.997535 and
  .999325, masked badge negative reads none; floor-trial-level-native-verification
  binds PNG92bbc6... and records zero device input.31 relevant cases passed.
- Loop callback now returns its actual bounded verdict; errors preserve attempted
  input counts and steps and print reason plus evidence path. Logs explicitly
  distinguish unverified dungeon completion.
- New shop transactions persist scope/visit/PNG+JSON-bound purchase/confirm/refresh
  intents. Generic Confirm cannot authorize payment. Exact coin delta and complete
  successor shelf are required before booked purchase. Pending/restart/UNKNOWN
  cannot reset refresh budget.50 shop integration cases passed; actual question,
  currency/receipt and later visits remain to be tested.

- Pending floor pick recovery now validates its original full offer/counter and
  JSON/PNG bindings against a fresh1-step counter successor, without another
  input. Changed scope/original or unknown counts keep pending.91 focused tests
  passed across runner/floor/native badge/transaction cases.
- Shop regular Refresh native dual-crop diagnostic reads15 at.999732/.999956
  versus old icon-prefixed015 at.844343; original confidence gates stay unchanged.
  Runtime now drops low-confidence shop costs and uses fresh native caption-bound
  narrow reads. Runtime self-label proposals are connected to real card-page
  journal frames with scope/PNG/JSON bindings, always unreviewed/not training truth.
- DeepSeek completed its permitted add-only policy files and documented empty
  learned evidence as zero adjustment. Its159 tests are offline policy evidence,
  not actual neural inference or Mirror completion. Training agent is preparing
  a12-class130-card real research dataset; no model/promotion claim yet.

## Continuation: October12 GUI Start, neural research and shop handoff

- GUI Start really dispatched installed MirrorTask/MainTask. The first actual
  GUI run pi-20261012-111430 hit a missing re import in map header recovery;
  the fault is repaired in bc913b5 and the complete Agent observer was replayed
  natively on its actual frames, with no device input. Callback errors now retain
  the message and stack, and stop summaries remain literal GUI text.
- The resumed actual GUI/Agent13240/40172 is pi-20261012-112240, active at the
  handoff. It is still MAPfloor2, not a full run completion. It must not race a
  second controller or be replaced by a freeze while active. Root source now
  shortens unchanged-map settling and prioritizes the actual54px question glyph
  before neutral path cubes/reward badges; real-frame+masked replay passes but
  the live node successor is still required.
- A real130-crop/12-class ONNX research model is installed through the local
  shadow policy. Native retained inference found missing/misclassified boxes;
  quality/production/input authorization remain false. No live PRE inference
  or completed neural-assisted dungeon is claimed. Review bundles, predictions,
  raw frames and hashes collect in build/learning-review. Global CUDA is restored;
  training work uses the isolated neural-learning-venv.
- DSH added independent native shop policy/refresh/reserve controls; Root wired
  them into MainTask/Runner and the durable transaction. Coin reserve is checked
  again before either purchase/refresh intent. Empirical refresh learning uses
  complete native shelf/coin-delta receipts; it never treats buying as a combat
  strength label. Unknown strength has explicit rule fallback. Named shop GET
  acknowledgment, actual purchases/skills/refresh and pre-boss shop remain live
  acceptance work. New source is not installed in the running GUI.
- Final225 relevant focused tests passed37.24s. Earlier whole suite1345passed,
  1skip/5fail was not green: four outdated option fixtures were fixed, the actual
  canonical-controller test collided with the live lease and awaits idle replay.
- User explicitly delegated continuation until Codex returns and requested DSH's
  task board. Exact plan/process/evidence/remaining work is in
  docs/DEEPSEEK_CONTINUATION.md. Keep GUI Start/full-floor/receipt/HOME evidence
  separate from unit/resource/package checks. No new payout/module permission,
  FGO input, limit check or public Release occurred.

## Continuation: October12 shop notice acknowledgment and the live run's natural end

- The GUI run pi-20261012-112240 ended on its own at 11:58:14 local:
  `mirror_loop_stopped reason=unexpected_successor steps=17 clicks_sent=17
  passed=false`. Every one of the 17 clicks was a MAP node attempt and every
  observation kept `route.reason=current_position_not_proven` with
  `verified_clear=false`, so floor2 never advanced; each failed click started a
  fresh retry budget (attempts 1-7, remaining 17..12, one per ~2.4 min) instead of
  exhausting a shared one. That livelock is the map-identity blocker, still Root's
  open item; the run stopped rather than sending an unproved input.
- DSH implemented the missing one-shot native `E.G.O Gift GET!` acknowledgment
  offline. `shop_skill_vision.frame_overlay/read_overlay` now recognise the notice
  over a shelf (measured on the retained frame
  evidence/runtime/window-20261006-042640/frame-0066.json: title `E.G.O Gift GET!`
  box [828,250,258,41], single `Confirm` box [922,774,136,45]) and return
  available/complete/target separately; an unread notice yields no target, and a
  locale pattern may widen the match but must still normalise to the proved title.
  `ShopTransaction.reserve_overlay_acknowledgement` records the intent at stage
  `overlay_intent` before any input, binds it to the notice frame's own PNG hash,
  refuses a frame that repeats the retained shelf or question, and is single-use per
  intent so a restart can never click twice. The notice is an input anchor, never a
  receipt: only `reconcile_purchase` on the returning shelf with the exact coin
  delta and the removed offer records a purchase.
- Evidence: tests/test_shop_receipt_acknowledgement.py 15 focused tests plus
  tests/test_shop_skill_vision.py 32, together `47 passed`; the shop group
  (receipt-acknowledgement, transaction, skill vision, settings) `134 passed`.
  build/deepseek-shop-skill-handoff.json records the notice reading, the
  acknowledgment contract and `notice_acknowledgement.wired_in_runner=false`.
- Not done here: the runner still does not call the acknowledgment, so a real
  purchase in the live loop keeps stopping safely with
  `shop_receipt_successor_not_proven` until Root wires the GIFT_GET branch. Nothing
  was installed into dist, no controller was started, no input was sent, no private
  budget/ledger/config was written, and no commit was made.

## Continuation: October12 installed GUI Start enters the node panel, and the shelf floor

- The repaired source was installed through `tools/make_local_app.py` (backup
  `dist/MaaLimbus.backup-8ae0cd0ac09d4ee3bb7e7380651e7ba6`) and a real GUI Start
  at 12:39:06 local produced `pi-20261012-123906`. It **entered the node panel**
  (scene `NODE_PANEL`, title `Emotional Indolence`, enter box `[1672,784,118,57]`),
  which the previous install never reached: `pi-20261012-112240` held only MAP and
  UNKNOWN over 948 events and zero panels. Two live MAP clicks
  (`[1067,736,40,40]`, `[1450,110,40,40]`) genuinely changed the page, and the run
  walked MAP → event choice → a four-state skill check → node panel → `GIFT_GET`
  → shop in 32 steps / 31 clicks before stopping on its own.
- The `E.G.O Gift GET!` notice was cleared on the real device at 16:40:24 UTC
  (`the_gift_get_notice_is_cleared_with_its_own_confirm`, target
  `[922,774,136,45]`, the measured `GIFT_GET_CONFIRM_BOX`). That proves the notice
  path in the loop; the purchase-bound `reserve_overlay_acknowledgement` stays
  unexercised because no purchase occurred to bind it to. The first shop refresh
  reconciled normally (`shop_receipt_verified kind=refresh`, cost 15). The run
  stopped on its **second** refresh with `Fresh refresh currency delta and complete
  changed shelf not proven`.
- Root cause was the shelf reader, not the rule: `_shelf` filtered OCR tokens at
  `score >= .9`, and a card's `@77` price token scores .835 while a sibling read
  `①211` at .874, so one unchanged six-slot shelf read as four offers before the
  refresh and five after. The coin delta itself was exact (1647 → 1617 for a cost
  of 30). Fixed one-sidedly in `src/maalimbus/shop_vision.py`: `PRICE_GLYPH_PATTERN`
  + `price_value()` accept a leading coin mark, `shelf_tokens()` keeps any token at
  `score >= .8` that parses as a price while names still need `.9`, and the three
  shelf call sites (`shop_vision` callers, `shop_transaction._shelf`,
  `runner.py` `shop_offers`) now pass through it. The refresh-cost reader was left
  at `.9` deliberately: both live costs read clean ('30' .997989, '45' .999201).
- Evidence: `tests/test_shop_vision.py` gained the live six-offer pair and
  `tests/test_shop_transaction.py` gained
  `test_the_live_refresh_pair_reserves_and_reconciles`, both guarded by
  `pytest.skip` when the gitignored `evidence/runtime/` pair is absent. Whole suite
  `1416 passed, 1 skipped` in 76.11 s; `tests/test_runner.py`'s shop expectation was
  widened from two names to the full six the live shelf really shows.


## Continuation: October12 live battle spine and the renamed duplicate gift

- The shelf-floor repair was installed (backup
  `dist/MaaLimbus.backup-42c89ed8c3424c70b21a7f2dc80c0b68`, built from `22ceaa6`)
  and a real GUI Start at 13:55:57 local produced `pi-20261012-135557`. The run
  finally left the map: shop pending reconciled, shop left, MAP → `NODE_PANEL` →
  `PRE_BATTLE_TEAM` → `DEPLOYMENT` → **`BATTLE_HUD` (15 observations) → battle won**
  → `BATTLE_RESULT` → `GIFT_GET`. This continuation proves the repaired installed
  entry reached a live battle; earlier repository runs already had battle and
  Hard-five-floor evidence. Saved order was submitted without Clear Selection.
- It then stopped at 18:02:19 UTC on `steps=32 clicks_sent=31` with
  `Fresh refresh currency delta and complete changed shelf not proven` **gone**, and
  a new reason: `floor_gift_receipt_successor_not_proven` in
  `src/maalimbus/floor_gift_transaction.py` `observe_receipt`.
- Root cause is a real game behaviour, not a reader fault. The pick screen offered
  four cards and one of them ("Portable Battery Socket") carried the `Owned` band.
  The run picked that duplicate as its second pick, and the game answered the two
  picks with two notices: `Prejudice`, then a **different gift printed under its own
  name, `Faint Vestige`**. The transaction required the successor notice to name a
  *remaining selected* gift, so the substituted name read as an unattributable
  receipt and the run stopped rather than guess.
- The fix keeps the frame and drops the refusal. `observe_receipt` now accepts a
  `GIFT_GET` successor that prints a name which is neither the notice just booked
  nor a remaining pick, records it as a labelled substitution
  (`d['substitutions']`, with `expected`, `printed`, `expected_owned` and the proof
  frame), carries `granted` into the new pending, and lets `receipt_intent` bind the
  printed name back to the next unclaimed pick. `runner.py` journals
  `floor_gift_receipt_substituted` with `input_sent=false`, so the mismatch lands in
  `events.jsonl` as evidence the learning step can test instead of vanishing.
  `intent(..., owned=...)` now records which picks were known duplicates.
- An outstanding receipt whose confirm already landed is now recovered instead of
  stopping: `retained_notice_name()` re-reads the booked notice's own frame with a
  PNG/`image_sha256` check and `runner._resolve_floor_receipt` books it from that
  retained frame plus the fresh successor, journaling `floor_gift_receipt_recovered`.
  No input is re-sent. Repeated identical notices and stray notices after every pick
  is receipted are still refused.
- Evidence: `evidence/runtime/pi-20261012-135557/frame-0084.*` + `frame-0085.*`
  retained (gitignored) and
  `build/deepseek-continuation-20261012/_probe_floor_receipt_recovery.py` replays the
  real store copy end to end without touching it. `tests/test_floor_gifts.py` gained
  the labelled-substitution, repeated-notice, stray-notice, retained-name and
  changed-image tests. Whole suite `1423 passed, 1 skipped` in 85.83 s.

## Continuation: October 12 actual Purchase modal

- `dist/MaaLimbus/evidence/runtime/pi-20261012-170045` stopped after 58
  inputs on frame 0239: the Purchase modal was classified as SHOP because the
  earlier detector expected Confirm. The runner then checked a post-purchase
  coin delta before Purchase had been sent. The existing card intent remains
  pending; it is not a failed paid purchase or an unknown gift effect.
- Added the actual native `Purchase E.G.O Gifts` / `Purchase` / `X Cancel`
  layout. The full selected name plus two independently read balance crops
  bind the pending offer: Devil's Share, 2707 -> 2563, price 144. Descriptive
  effect text is not a purchase prerequisite. GIFT_GET is a valid confirmation
  successor; only the later shelf reconciliation books the purchased gift.
- `build/shop-purchase-dialog-native-replay/verification.json` uses the real
  Agent observer and retained PNG, with changed price/title and masked balance
  negatives. An isolated copy reserves one confirmation and rejects a duplicate;
  the authoritative transaction hash remains unchanged, with zero device input.
  Related purchase/shelf/transaction/floor-receipt tests: 83 passed in 7.96 s.
- Actual fresh Purchase -> GET -> shelf receipt and GUI Start continuation remain
  required. Offline replay is not a completed purchase or whole-run acceptance.

- Installed `be0c3f4` with 2212 private-file hashes preserved, then used the
  actual GUI Start. `pi-20261012-173651` sent Purchase once and GET Confirm once,
  returning to SHOP at 2563 coins. It stopped at a second reader defect: purchased
  cards stay on the shelf and move columns, with Purchased above their art.
  The old transaction instead required the offer to disappear.
- Native narrow OCR now reads that badge twice above each full name/price pair.
  Only the exact reserved gift's unique high-confidence badge, exact coin delta,
  unchanged other items and retained confirmation chain can book it. The marked
  card remains in the complete shelf for refresh auditing but is never a new buy.
  `build/actual-purchased-shelf-replay/verification.json` replays the native Agent
  against the actual frame, books only an isolated transaction copy, rejects a
  masked badge, and leaves real pending bytes unchanged. 120 focused tests pass.
  The real transaction still needs fresh GUI continuation to finish bookkeeping;
  no Purchase or GET may be replayed.

## Continuation: October 12 purchase receipt and learning inputs

- `pi-20261012-174217`, started with the real installed GUI button, reconciled
  Devil's Share without another Purchase or GET. It verified both bounded
  refreshes (15 then 30), exited to MAP floor 3 / Sinking Pang, and fought the
  boss through BATTLE_RESULT into the floor reward. Read-only chain audit:
  `build/actual-shop-purchase-real-verification.json` (one paid Purchase, one GET,
  2707 -> 2563, exact item Purchased badge and all proof hashes).
- It then stopped before gift input on frame 0084: `Acqulre E.G.O Glft` was not
  a plate, so four cards became three and adjacent trials were mixed. The exact
  complete-caption i/l alias restores four independent title/trial columns.
  Actual retained-frame and missing-caption negatives pass; unknown Final Power
  remains unpriced and uses the existing bounded exploration queue.
- Added explicit economy preferences before keyword filtering, with Prestige
  Card weight 100. These are manual engineering priorities, with saved-team block
  and existing spend caps still controlling actions; not a trained value estimate.
  `docs/economy-gift-review.md` is DSH's source-backed catalogue reviewed by Codex.
  No unrelated forum use can disprove the player's black-card nickname.
- `shop_outcomes` now queues actual purchased action/context and subsequent same-
  scope outcome evidence beside PNG/JSON/review/trace. It never equates buying
  with benefit, labels an unbought item as a negative, or invents unknown effects.
  One actual receipt sample currently has a pending value outcome; the purchase
  value neural model is still untrained. DSH has only the isolated feature/MLP
  training-tool task; runtime policy and promotion remain Codex-owned.
- Focused final: 80 passed; full source regression: 1466 passed, 1 Windows
  symlink-permission skip in 93.84 s. Live whole-run continuation, economy buy,
  and trained value policy application are still required; source tests do not
  establish any of them. No final payout or new module consumption claimed.

- Installed `f2466d5` with 2396 private hashes preserved. GUI `175907` picked
  Rebate Token and the already-owned Oracle once each, confirmed Select once,
  acknowledged Rebate Token and the printed replacement Faint Vestige once,
  and reached SELECT FLOOR 4. The substitution journal records expected_owned
  true; no guessed Oracle effect is attributed to Faint Vestige.
- The floor-4 drag then stopped on a changed-pixel THEME_PACKS fade. The patient
  theme path already had a read budget, but the generic same-page pixel-change
  break cut that budget short. It now excludes theme drags: only exact native MAP
  floor/name clears the existing pending, and no drag is repeated.
- Actual `174217` prebattle frames 0012/0013 executed native NN shadow inference
  with 11 candidate boxes each, not production input. DSH's independent identity
  helper returned no online report because it compared decoded pixel bytes with
  the journal's encoded PNG hash. The corrected PNG hash replays the actual
  teacher as 12 measured cards / 3 resolved / 9 unresolved, detector_read false.
  Changed PNG bytes still refuse. 39 focused runner/theme/hash tests passed in
  26.08 s; whole-source test evidence above predates these two corrections.


2026-10-12 shop value and unavailable deployment continuation: see
`docs/shop-value-learning.md`. Actual readiness: 1 pending purchase sample,
0 reviewed episodes; no value model or production neural shopping. Native
retained HP-zero/capacity/card proof passes in
`build/deployment-unavailable-native-verification.json`; current encounter
order filtering preserves the permanent roster order and pending no-op evidence.
Source fixes also independently read TURN 7 and locate the shifted lit START
dial. Full current-run completion still requires installed GUI continuation.

Idle source verification after these changes: 1528 passed, 1 skipped
(Windows symlink privilege), 98.33 s; build/shop-value-deployment-full-tests.txt.
This is a source test result, not complete game or production-value acceptance.

## Continuation: October 12 the shop's Heal Sinner revive

- The operator's rule and route: a Sinner in the first seven slots of the saved order who
  cannot be deployed has to come back, `Heal Sinner 100` opens three options and the third
  one is the revive, and the Sinner itself is then the one to click. It became three pages,
  each named from two independent tokens: `HEAL_SINNERS` (`assets/resource/en/locale.json:67`,
  `vision.py:266-269`; the title plus the three ordinal rows whose third prints its own badge),
  `REVIVE_PICK` (`:68`, `vision.py:286-288`) and `REVIVE_DONE` (`:69`, `vision.py:283-285`).
  The first option's ordinal is read live as `I.` rather than `1.`, so
  `shop_revive.ORDINAL` matches a loose glyph run and the rows are taken in reading order.
- The modal's inputs are words, not positions: the option rows are display-only in every
  state. Measured live in `window-20261012-214600`, clicking the revive row, its 100 badge
  and its inner label did nothing, while a second click on the picked portrait took the pick
  back (highlight 227 px -> 0). The real input is the modal's own bottom-right control, whose
  word carries the state: `Return` [1610,941,172,55] in the three-way step, `Select`
  [1614,937,166,61] in the pick step, `Leave` [1622,943,150,53] after a revive
  (`shop_revive.modal_bottom_control`, `CONFIRM_X=(1560,1860)` x `CONFIRM_Y=(900,1010)`,
  exactly one match at `FLOOR=.9`).
- Which Sinner is dead is never read from the picture. It is the deployment page's own proof:
  `unavailable_sinners` = the store's `unavailable` plus its rejected inputs' proof cards,
  minus the cards the booked `revives` name, intersected with `saved_order[:KEY_POSITIONS]`
  (7). The picker's bar is measured geometry (`BAR_FIRST_CENTER=112`, `BAR_PITCH=115`, the
  box 90 x 120 at y 880), so `slot_box(card)` aims without searching portraits.
- A revive is booked only from the shop's own counter delta, because its price cannot be read
  off the shelf before it is spent: planning stores `state['revive_receipt']`, and the next
  SHOP frame books it through `deployment_transaction.book_revive` only when
  `coins_before - currency == cost`; any other delta notes
  `shop_revive_receipt_not_proven` and books nothing. Live proof, one window apart:
  `window-20261012-214803/frame-0001.json` reads `Hong Lu, revived, returns to battle.` over
  2993, exactly 3093 - 100.
- Written up in `docs/shop-revive.md`, cross-linked from `docs/shop-settings.md`. Suite:
  1595 passed, 1 skipped (Windows symlink permission);
  `tests/test_runner.py tests/test_window.py tests/test_shop_settings.py` 181 passed.
  `dist/MaaLimbus` rebuilt and installed from this source (`tools/make_local_app.py`,
  `self_test` and `agent_self_test` true, 2824 private files preserved, backup
  `dist/MaaLimbus.backup-833ef7c747b245c38c279855909937ef`).
- Still required at that point: one live window driving the whole route from the planner in a
  single run (the live clicks above were sent one at a time with `tools/window_step.py`), and the
  carry-cap spend of `docs/shop-settings.md` in a live shop. The continuation below answers the
  cap spend and the planner's own legs; what is still open is named at its end.

### Live continuation: the planner drove the modal, the cap and the exit

- `build/deepseek-revive-live-14.json` (`window-20261012-221139`, `--steps 60`) started on the
  revive notice the previous run left behind and drove it from the planner in one window:
  step 0 `REVIVE_DONE -> SHOP` `click` `the_revive_is_paid_for_and_the_modal_leaves_back_to_the_shop`,
  step 1 `SHOP -> SHOP_PURCHASE` `spending_the_coins_this_visit_would_carry_out_on_the_shelf`
  (the carry-cap rule buying live for the first time), step 2 `SHOP_PURCHASE -> GIFT_GET`
  `confirming_the_purchase_the_shop_asked_about`, step 3 `GIFT_GET -> SHOP`
  `the_gift_get_notice_is_cleared_with_its_own_confirm`. Step 4 stopped the run:
  `Independent complete successor shelf not proven`.
- That stop was a real defect in the receipt, not in the revive. `shop_transaction.py:419`
  matched the bought card by its exact title, and the shop's own typeface spells the same card
  two ways: the visit reserved "Today's Expression" 189, the counter went 2993 -> 2804, and the
  successor printed that same slot under its own Purchased badge as "Today's **Expresslon**".
  No bought card was recognised, so the fallback compared every remaining slot and refused a
  purchase the counter had already charged. `_same_title`/`_fold` (`shop_transaction.py:33-53`)
  now fold the typeface's confusable class (`i`/`l`/`1`/`!`/`|`, `o`/`0`, apostrophes) before
  matching a re-read shelf row to the intent, and the fix is used for the badge's own card, the
  unspent-intent guard and the strict whole-shelf comparison. It is not a fuzzy title match:
  `matching_purchase_question` still demands the complete name.
- `build/deepseek-revive-live-15.json` (`window-20261012-221631`, `--steps 70`) then did the
  whole shop visit on the fixed source: the walk-in reconcile booked the stuck
  "Today's Expression" (`own_purchased_badge`, successor `frame-0001`), the cap bought
  "Blood, Sweat, and Tears" 200 (`frame-0007`) and "Millarca" 204 (`frame-0013`), two refresh
  receipts were booked, the visit closed (`closed: True`, `pending: None`) and the run left the
  shop at 2400 through `SHOP_LEAVE` — then kept driving the dungeon (battles, `EVENT_CHECK`,
  `REWARD_CARD`, `NODE_PANEL`, `PRE_BATTLE_TEAM`, `GIFT_PICK`) to the step budget. The cap could
  not reach its own ceiling on that shelf (every affordable offer was already bought and the only
  unbought one was the service "Replace Don Qubote's Sil"), which the decision now says in its own
  reason instead of borrowing the gift plan's (`SHOP_REASON_CAP_UNMET` in
  `tests/test_runner.py:794`), and the exit stayed budget-safe. `config/user-run-ledger.json`
  now holds the active run on floors `[1,2,3,4]` (team 7, rotation 5), so floor 5 is the next
  live milestone; the earlier receipt `8de51ee326254dada65ae776aa1c1e11` (team 4, floors
  `[1,2,3,4,5]`, victory and reward) is still the only floor 5 outcome on evidence.
- Tests: `tests/test_shop_transaction.py` 45 passed, including the live three-frame replay
  (`frame-0002` reservation, `frame-0004` question, `frame-0008` successor) and a negative that
  proves the fold never adopts a card with a different glyph; `tests/test_runner.py` 46 passed.
- Still required after this continuation: a single planner run that starts at `HEAL_SINNERS` and
  carries the revive itself (`HEAL_SINNERS -> REVIVE_PICK -> REVIVE_DONE -> SHOP`) — only its
  separate legs are live-proven so far — and a floor 5 outcome on evidence.
- `dist/MaaLimbus` was rebuilt from this source after the fold fix (`tools/make_local_app.py`,
  `self_test` and `agent_self_test` true, 2824 private files, backup
  `dist/MaaLimbus.backup-0553a889cb14422f8fed9197f057a77b`), and the frozen product was then
  pointed at the live window to continue the run toward floor 5
  (`tools/verify_packaged_mirror_loop.py --app dist/MaaLimbus --steps 300 --seconds 3600`,
  report `build/deepseek-floor5-packaged.json`). Suite at this point: 1598 passed, 1 skipped.

## Continuation: October 12, the wiki is brought back onto today's code

- The wiki (`docs/wiki/`, `README.md` + `zh_cn/` + `en_us/`, 11 chapters per language) had been
  frozen at 20:40-21:51 the same day, i.e. **before** the shop revive work: a grep for
  `shop_revive`, `Heal Sinner`, `revive`, `REVIVE_`, `CARRY_CAP` and `modal_bottom_control` over
  every wiki file returned zero hits. It now documents the work: `shop_revive.py` joined the module
  table (`docs/wiki/*/2.2-modules.md`, 92 -> 93 modules), chapter 5's store table carries
  `saved_order`/`unavailable`/`revives` and the shop store's `bought`/`refresh_receipts`/`closed`,
  the in-floor state graph gained the revive route (`SHOP -> HEAL_SINNERS -> REVIVE_PICK ->
  REVIVE_DONE -> SHOP`) plus the shop's own purchase/refresh/leave edges, chapter 4 gained the
  shop-visit section, chapter 7 gained the battle-HUD gap, and chapter 2.3 gained decisions D13
  (a dialog's answer is the state word it prints, not its explanatory row) and D14 (the confusable
  fold, explicitly not fuzzy matching).
- Two new build-side guards exist for the *anchor* half of the wiki, which
  `tools/check_wiki.py` never checked (it validates structure, not `path:line`):
  `build/deepseek-continuation-20261012/resolve-wiki-citations.py` resolves every
  `src/maalimbus/<module>.py:line` citation to the line it lands on and flags inverted ranges,
  out-of-file lines, blanks and comment-only spans, and
  `build/deepseek-continuation-20261012/fix-wiki-citations.py` holds the audited repair table
  (both languages, longest citation first, idempotent). After the repairs: 1112 citations
  resolved, 12 remaining flags that are all deliberate citations of a design-comment banner, and
  `tools/check_wiki.py` still `ok — 0 problem(s)` with `tests/test_wiki.py` 30 passed.
- One real code defect came out of the audit: the `HEAL_SINNERS` plan's third row opens a picker
  the classifier names `REVIVE_PICK`, but the plan's `expect` tuple omitted that page, so the hop
  was an `unexpected_successor` retry. `src/maalimbus/window.py:1000` now reads
  `expect=('REVIVE_PICK', 'HEAL_SINNERS', 'SHOP', 'PRE_BATTLE_TEAM', 'UNKNOWN')`, asserted by
  `tests/test_window.py::test_the_shops_own_option_list_is_answered_with_its_third_row_only`;
  `tests/test_window.py tests/test_runner.py tests/test_vision.py` = 169 passed.
- A read-only audit subagent hand-verified every `window.py`/`vision.py`/`runner.py`/
  `shop_transaction.py` citation in the wiki and found ~60 stale ones, all now repaired (~130
  replacements across both languages). One row is knowingly left alone: `7-quality.md:19` quotes
  `docs/acceptance.md`'s own record (`runner.py:1784`, `runner.py:2131`), which the audit marked
  UNVERIFIABLE — it is a quotation of another document, so it is not re-anchored by guesswork.

### Continuation: October 12 late, the diagrams catch up and one durability defect closes

- The **diagrams** were the last stale layer. `§5.1.2`'s in-floor state graph already carried the
  revive route, but nothing else did, so `docs/wiki/*/4-business-flows.md` gained a shop-visit
  flowchart under `§4.3.1` (the ordered inputs, each hop gated by its own page's words, ending in
  the `coins_before - current == cost` receipt gate and `book_revive`), `docs/wiki/*/2-architecture.md`
  figure 2-2 gained a `shop_revive.py` node in the page-reading layer with `RUNNER --> SHOPREV -->
  SHOPV` edges grounded in `src/maalimbus/runner.py:1862` and `src/maalimbus/shop_revive.py:20`,
  and the chapter-5 ER diagram now lists the keys the revive path actually writes
  (`saved_order`/`unavailable`/`revives` on `user-deployment-transaction`, `unspent_intents` on the
  shop store). The module count was stale in eight more places (chapter 1's two diagram labels,
  chapter 2's four mentions, chapter 6's source-tree diagram, chapter 2.2's cluster sum): all now
  93, and chapter 2's Chinese vision-cluster row was 25 where the English row and chapter 2.2 both
  said 29 — both are now 30. Verified with `tools/check_wiki.py` (`ok — 0 problem(s)`,
  flowchart 28 -> 30), `tests/test_wiki.py` 30 passed, and the offline render check
  (`tools/make_wiki_mermaid_check.py` + a local HTTP server read through the browser):
  **48/48 blocks parsed, all blocks parsed**.
- One durability defect closed while touching that contract. `DeploymentTransaction.prepare`
  rewrites the store from a fresh dict whenever the page has been submitted again — which is how a
  selection is cleared — and that rewrite silently dropped `revives`, the receipt the shop's own
  currency counter paid for. The next shop visit of the same run then read the dead slot again and
  walked back into a picker it had already paid for (the picker refuses, so the run stops rather
  than double-charges). `src/maalimbus/deployment_transaction.py:23-30` now carries same-scope
  revive receipts through that rewrite and starts a different scope empty, pinned by two tests in
  `tests/test_deployment_transaction.py`. Live note: `config/user-deployment-transaction.json`
  currently holds no `revives` row (its last write predates the manual booking, and the game shows
  no dead slot — `unavailable: []`), so nothing was re-booked into the operator's store by hand.
- Suites at this point: `python -m pytest -q` = **1600 passed, 1 skipped**; the wiki citation
  resolver reports **1144 citations, 12 flags**, and every one of the twelve is a deliberate
  citation of a design-comment banner rather than drift.




## Continuation: October 13 entry reconciliation, list browsing and wiki semantics

- Real installed `pi-20261013-000909` stopped after two inputs on DUNGEON_TEAM:
  a shop-local variable shadowed the imported run-wiring reconcile. Renamed to
  shop_reconcile; the actual failed frame passes isolated zero-input regression.
- Offscreen numbered team targets now get bounded sidebar-only swipes and current
  OCR row targeting, with independent selected-header verification (1-40).
  Custom team names require a verified slot mapping; no ordinal/name guess.
- Current source: 1608 tests passed, 1 Windows symlink privilege skip, 115.31 s.
  This is not GUI/game completion. New product installation remains a separate gate.
- Paired wiki component/deployment diagrams now show actual boundaries and
  interfaces. Business activities and logical data cardinalities are separate;
  intent-before-input and shop refresh transitions corrected. Actual browser
  Mermaid parser accepted 52/52 blocks before the final field-name correction;
  structural checker reports zero problems after the correction.
- Current public-text scan: 854 files, zero remaining local-home-path/literal UID
  findings. Document local-user paths redacted; public-source export refuses
  detected private text before ZIP creation and excludes local policies/logs.
  Screenshots, datasets and existing Git history have not all been privacy-reviewed.

## Continuation: October13 local wiki diagrams and manual rotation policy

- User chose success-only automatic rotation plus an explicit manual skip, and confirms
  the previous gameplay clear. Preserve that report separately from missing independent
  payout/return bookkeeping; do not mutate the active scope or pretend it failed.
- Added twenty paired feature-local diagrams, stable coverage links and an index guard.
  Browser parses 92/92; actual preview exposes every chapter, readable scroll and fit.
- Idle-only skip source panel/launcher/RunStore request journaling is implemented with
  controller exclusion, stale-cursor refusal and idempotent request IDs; no receipt,
  budget or completed counter changes. TypeScript passed; native Rust build, installation
  and actual GUI action remain open. Do not replace the running paused GUI for docs.
- Retained-frame Runner tests prove fixed/rotation targets1/2 override stale team7;
  sidebar tests cover return from lower rows and independent header before Confirm.
  Actual product offscreen Swipe acceptance still needs a resumed authorized test.
- Python full snapshot1623 passed/1 permission skip; later wiki/skip focused40 passed.
  Latest source/wiki changes are not installed. Remaining game pipeline, learning
  production quality and public updater obligations stay open.

## Continuation: October13 actual GUI single/rotation startup refusal

- Actual GUI runs022858/023045/023230/023233 rejected in GlobalSettingsAction with
  Finish the active run before changing its rotation, before any gameplay input.
  The GUI correctly sent rotation[1,2,3,4,5] and later single[2]; the old Team7
  ledger blocked application before the runner could reconcile the ended run.
- MainTask now observes independently before changing settings when a run is saved.
  Exact Before Entry plus Enter, PNG/JSON hash and dimensions, or a new picker,
  can retire the stale scope without inventing payout/clear. Pending entry/payout
  and actual ongoing gameplay are preserved. Native fresh screenshot + isolated
  copies prove both single2 and rotation1..5, original private hashes unchanged.
- Expected settings refusals now persist agent-result/run.log and show the reason;
  they do not latch callback_failure. Preparation and loop share one evidence folder
  and journal; resumed journals continue indexes instead of overwriting bound frames.
- Full snapshot1636 passed/1 Windows permission skip157.29s; latest focused74 passed
  2.26s includes journal durability/clear preservation. Native probe remains zero-input.
  Freeze/install and actual GUI entry continuation are the next required gates.


## October14 recovery, restored controls and continuation

- The actual pi-20261014-053727 failure selected card4 but did not read75 at the
  original only_rec crop: native confidence .767653 under .85. Two anchored
  detected-digit crops now agree without reducing the threshold or deleting a
  contrary full-frame read. Native actual105/95/75 plus masked digit/label cases
  and isolated pending4 recovery pass, original private transaction unchanged.
- Added bounded observation-only retries and a retained-before-frame/current
  exact-delta recovery before new star inputs. Decision console and run.log show
  actual rule components/final scores, saved weights, shop priority and shadow
  boundaries. This does not claim a trained value policy controls purchases.
- Fresh pinned custom MXU build restores GitHub update button, reference portrait
  order editor and base star-card selection. Native SHA aa28bc31…9615c2, full
  corresponding source. Installed Agent self-test passed,2970 private hashes kept;
  build/grace-ui-installed-verification.json. GUI persistence is not yet accepted.
- Actual installed MirrorTask probe found HOME rather than the historical STAR
  page; it reached DRIVE, then exposed missing tasker wiring for native NODE plans.
  Source fixes MaaDevice to carry the same AgentTasker callback proxy used by the
  observer;72 focused tests including retained DRIVE navigation pass. This latest
  adapter fix is source-only after the installed freeze. No star recovery or
  further star purchase happened live. Existing pending card4 remains protected.
- Full pre-correction snapshot1651passed/1skip/2failed exposed payout using all
  profiles rather than the actual queue and a historical-fixture queue mismatch.
  Both corrected; focused reward/grace/log/UI84 and adapter/Runner72 passed.
  Latest whole-suite rerun and actual full pipeline remain required.
- DSH handoff follows docs/plan-20261014-recovery-diagnostics.md and wiki-first
  feature-local diagrams. Resource CPU/RAM/GPU/VRAM UI remains planned, not done.

## DSH handoff execution: star settlement, packaged entry, live pipeline

- Gate build/dsh-20261014-ready.json given with Codex commit 252c0d2; the running
  client PID6764 was closed with CloseMainWindow and no MaaLimbus process remained.
  Rebuilt and safely reinstalled with the node-adapter fix: build-info source
  252c0d2a9b38, built 2026-10-14T10:20:08Z, mxu_sha256 aa28bc31…9615c2, self-test
  passed, 2970 private files byte-identical to the backup and to the install copy.
- Card1 was settled in both halves from retained evidence with zero device input.
  The ended scope bc1fec62c8984a8f9d78ed6c26b0f4b8 was retired through native OCR of
  the fresh MIRROR_ENTRY frame: disposition ended_without_new_outcome_claim,
  completed_runs still 2, receipts still 2, grace transaction untouched
  (build/mirror-idle-entry-native-verification.json, ledger sha 7b085d5f…). The sent
  card4 selection was then booked from the retained before/after frames (95->75):
  selected[2,4], spent30, pending null, store bef3f24b…->89ea65c6…
  (build/grace-balance-recovery-native-verification.json). Both tools gained an
  explicit --apply that refuses a clone, a changed pending and an unretired scope;
  their default path stays isolated-copy only.
- Card2's packaged entry now walks MIRROR_ENTRY -> ENTRY_CONFIRM -> DUNGEON_TEAM ->
  STAR_GRACES through the installed MainTask with no tasker error, so the source-only
  adapter fix is proven in the install (build/grace-stop-page-star-graces.json). The
  live run then read every grace balance at the anchored crops 105->95->75->45->5,
  bought the planned[2,4,5,7] with one input each, confirmed the selection and entered
  the dungeon; its evidence is evidence/runtime/packaged-mirror-20261014-063205.
- Card3's run-count semantics were verified in source instead of asserted:
  completed_runs advances only on entry_returned after five floors, a victory and a
  claimed reward (storage.py259-289, tests/test_run_store.py53-61); abandoning or
  pointing never touches it; MirrorRunBounds is read only as a step bound
  (mirror_task_options.py8) and all three locale labels say it is not a dungeon count;
  the module gate still ships pending/0. A visible verified-run counter in the MXU
  panel is not built yet.
- Card4's resource diagnostics landed deviceless: src/maalimbus/resource_diagnostics.py
  (stdlib ctypes/subprocess only) plus tools/resource_diagnostics.py and 14 hermetic
  tests implement the plan document's snapshot contract verbatim - unknown is null with
  a machine-readable reason, never 0, and the GPU read is one bounded nvidia-smi call.
  A live snapshot resolved the running Agent (pid 67064, 4.17% of one core, 87MiB RSS),
  kept the whole-box 402.05%/16-core figure explicitly separate from the app's load, and
  reported process_gpu as unsupported because this host has no per-process GPU provider.
  Report build/resource-diagnostics-report.md; the opt-in panel is still to build.
- The packaged acceptance run evidence/runtime/packaged-mirror-20261014-063205 is the
  first live chain past the entry page on the fixed install: STAR_GRACES ->
  STAR_CONFIRM -> INITIAL_GIFTS -> GIFT_SEARCH -> THEME_PACKS -> MAP -> NODE_PANEL ->
  PRE_BATTLE_TEAM -> BATTLE_HUD. Reaching battles exercises exactly the native node-plan
  path whose missing tasker stopped the previous product run, and the run spent its
  configured grace plan (account star 525->25, scope allowance 105->5) without buying a
  card twice: the cancelled preparation had moved only its own allowance 95->75 and
  never charged the account.

## DSH continuation: the printed deployment order is read from several framings (2026-10-14)

- The packaged acceptance run stopped at step 39 on `deployment_order_digits_incomplete_after_retries` after
  entering the dungeon, clearing the first node and winning a battle
  (`evidence/runtime/packaged-mirror-20261014-063205`, report `build/packaged-pipeline-run-1.json`): the two
  nested crops lost card 11's printed `4` (`frame-0103.json`), so the page was refused as an unreadable order
  instead of a proven different one.
- `src/maalimbus/deployment_numbers_native.py` now reads each card's band through three framings and adopts a
  number only when two of them agree; a card no two framings agree on keeps `None`. Proven deviceless on both
  retained pages (`tools/verify_deployment_numbers_native.py`: `frame-0027` needs the narrow framing,
  `frame-0103` needs the margin; both now read all twelve printed numbers), pinned by
  `tests/test_deployment_numbers.py`, full suite `1675 passed, 1 skipped`, commit `e7aaafc`.
- Rebuilt and safely installed the packaged app on top of that source
  (`dist/MaaLimbus.backup-ea051b4de6454b459fe2f2157bfea998`, 2970 private files preserved, self-test passed,
  `build-info.json` source_commit `e7aaafcd27e00c3b02640c312679af2bab64f8f8`) and re-ran the packaged
  acceptance (`build/packaged-pipeline-run-2.json`, evidence `evidence/runtime/packaged-mirror-20261014-065112`):
  the run drove `PRE_BATTLE_TEAM -> DEPLOYMENT -> BATTLE_HUD`, i.e. the deployment page that stopped run 1 is
  now read and answered.
- Still open from this era: the live GUI click Start (the packaged CLI probe is explicitly not a substitute), an
  explicit saved run count with a visible verified-run counter, the resource-diagnostics panel, and the
  lesson-review/apply path.

## DSH continuation: the saved run count and the panel that lost its pack line (2026-10-14)

- The saved run count is now the operator's own field, not a step budget wrongly reused: `mirror_loop` gained
  the `mirror_run_count` option (`assets/interface.json:126`, node `MirrorRunCount` at
  `assets/resource/base/pipeline/mirror.json:5579`), `src/maalimbus/mirror_task_options.py:33` reads it beside
  the step bound, and `src/maalimbus/runner.py:191` clamps it. The counter itself is separate from the step
  budget: `_verified_runs` (`runner.py:1387`) advances only where the ledger books a returned entry
  (`runner.py:2807` stops the loop when `_run_count_reached()`), and both the run summary
  (`summary()['verified_runs']`, `runner.py:3196`) and the module-level `_completed_runs` (`runner.py:3203`,
  printed by `src/maalimbus/event_log.py:149` as the `ledger: run …` line) report it. 20 new assertions in
  `tests/test_runner.py` plus the updated `tests/test_mirror_task_options.py`; full suite `1689 passed,
  1 skipped`.
- The second packaged acceptance run (`evidence/runtime/packaged-mirror-20261014-065112`) proved the deployment
  repair and then stalled at 74 steps on `page_unreadable_after_waiting` while the frames show the node panel:
  `frame-0250` carries the `Emotional Craving` title, the `Enter` control and no resource-pack line, because the
  pack had just been taken. `src/maalimbus/map_vision.py` now identifies that page by its own identity —
  `floor_label()` reads the `Exploring Floor N` header, `node_panel()` accepts a panel whose pack line is
  absent (pinned by `tests/test_map_vision.py::test_a_panel_whose_pack_line_was_dropped_is_still_a_panel`),
  commit `d574a26`; the run-count work is commit `8ca1ac1`.
- The app was then rebuilt with the agent re-frozen (`tools/make_local_app.py --mxu-exe
  build/mxu-interactive-artifact/mxu.exe --mxu-proof build/mxu-interactive-artifact/build-proof.json`, backup
  `dist/MaaLimbus.backup-bd579a330ea541d0a58db4ccdd5d3d08`, 2970 private files preserved, agent self-test
  passed, `build-info.json` source_commit `8ca1ac1b0d41ee17f51687acbf92e8f06ede4350`) and a **real GUI Start**
  was performed: `dist/MaaLimbus/MaaLimbus.exe` (process 34940) was launched and its own Start button pressed
  with real pointer input at 07:22 local. The run `dist/MaaLimbus/evidence/runtime/pi-20261014-072228` opened on
  scene `NODE_PANEL` -- the exact page the packaged CLI run could not read before `d574a26` -- and then
  dispatched `CUTSCENE -> EVENT_CHOICE -> EVENT_RESULT -> GIFT_GET -> PRE_BATTLE_TEAM -> BATTLE_HUD -> MAP ->
  NODE_PANEL -> GIFT_GET` and ran on to 254 frames / 71 inputs: `window_intent` covered `BATTLE_HUD` 20 (win-rate
  assignment and start button), `MAP` 8 node clicks, `SHOP` 7 including 4 `SHOP_PURCHASE`, `GIFT_GET` 6,
  `NODE_PANEL` 5 -- all five through `panel_enter_is_the_only_forward_input`, which is `d574a26` exercised live --
  `GIFT_PICK` 4, `REWARD_CARD` 2 and the four event-check pages. It then stopped honestly at 07:40:34 on
  `floor_gift_commit_receipt_not_proven` (`src/maalimbus/runner.py:2696`): the floor-gift transaction held
  `selected ['Prejudice','Uncapped Defibrilator']` -- the two cards the run's own clicks ticked on the pick page
  (`frame-0252`, button `Select 2/2`) -- while the notice it had to commit (`frame-0254`, retained as
  `evidence/runtime/gui-20261014-072228/frame-0254.json`) prints `Dark Vestige` on its own name plate, a name from
  neither the pick page's four offers nor the selection, so no selected name matched the receipt and nothing was
  written to the run ledger. Its Confirm is the only forward input on that page, so refusing the press stopped a
  one-click chain that was already working.
- That disagreement is now a bounded, tested rule instead of a stop: the notice page and its own name plate prove
  the press, and the receipt keeps both names -- the pick it answers and what the device printed.
  `FloorGiftTransaction.notice_matches_a_pick` and `receipt_intent(..., on_notice_page=True)` in
  `src/maalimbus/floor_gift_transaction.py`, the notice gate plus the labelled note
  `floor_gift_notice_outside_selection` in `src/maalimbus/runner.py`, pinned by
  `tests/test_gift_receipt_settling.py`: the retained live notice drives the whole runner step, and a name the
  selection cannot account for is still refused on any page that is not a notice page, because the middle band
  (`initial_gifts.receipt_name`) is a loose read that an encounter reward page also prints into.
- The live run before this one (`dist/MaaLimbus/evidence/runtime/pi-20261014-053727`, 5 inputs) had stopped on
  `Grace purchase successor balance not proven`, and its own frames say why: the STAR_GRACES reader is right and
  the OCR missed one glyph -- `frame-0010`/`frame-0011` read the counter at `[1515,45,54,40]` ('95'), while
  `frame-0012` emitted no counter token at all (only 'Available' `[1392,49,84,30]` and the yellow `375`), so the
  successor balance could not be proven from a single frame. That run was executed by an older install
  (`fd78ca8`); the bounded re-read (`grace_successor_balance_read_retry`, added in `252c0d2` with the zero-input
  `GraceTransaction.recover`) is in the source since, so the fix is installed but not yet exercised live.
- The learning path was audited offline (card ⑤): the shipped sinner model
  `assets/resource/base/model/detect/sinners.onnx` (10,634,896 bytes, sha256
  `859b8546292fc32007a22ac1723dded382bbb77a25d34246369d78200ebc1a59`) runs in production only as a shadow --
  `src/maalimbus/neural_shadow.py:130` refuses any mode but `shadow`, `agent/recognition.py:366-374` journals it
  and degrades to `status='unavailable', input_authorized=False` on any error, and its only consumer is
  label-proposal persistence (`agent/recognition.py:378-380`). Its model card records
  `fit_validation_uses_training_images: true` and the native evaluation's samples are `split: "train"`, so its
  metrics do not generalise. The shop-value shadow cannot reorder purchases -- `src/maalimbus/shop_value_shadow.py`
  returns `list(offers)` unchanged on every branch (lines 11, 53, 56) and no `assets/resource/base/model/shop-value`
  exists, so the trace reads `purchase_value_model_missing_rule_fallback`; in the real packaged run
  (`evidence/runtime/packaged-mirror-20261014-065112`) all five `shop_decision_ranking` events carry
  `learning: None` and the two purchases were chosen by `the_gift_plan_asked_for_this_offer_and_the_shop_covers_it`.
- Still open: the five-floor completion and the saved-run count's live stop; the resource-diagnostics panel (④);
  and the named-anchor re-resolution of wiki citations into `runner.py` (⑥).
- The learning loop was measured rather than only read (card ⑤): `python tools/train_shop_value.py` reports
  `training_ready: false` and `production_enabled: false` because all 3 retained samples under
  `build/learning-review/shop-purchases` are `review_not_approved` (`exclusion_reasons: {review_not_approved: 3}`)
  and 0 reviewed episodes is under `MIN_REVIEWED_EPISODES = 10` (`src/maalimbus/shop_value_training.py:48`), so
  `rank_preview` (`src/maalimbus/shop_value_shadow.py:7`) has no model to load, returns the input order unchanged
  (lines 11, 53, 56) and the trace reads `purchase_value_model_missing_rule_fallback`. The gate is deliberate:
  export refuses below 10 reviewed (`shop_value_training.py:764-765`) and below 10 ledger-verified episodes
  (`:779-780`), and the readiness report's own next actions are to approve a review with a 0..1 benefit per sample,
  attach a ledger-bound `outcome.json`, keep the evidence bytes beside each sample, and collect 10 independent
  scopes. What orders a real purchase today is the shop priority (`src/maalimbus/shop_priority.py`, a known unique
  gift plus an integer 0..100, loaded at `src/maalimbus/runner.py:1824`) and the gift plan: in the packaged run's
  five `shop_decision_ranking` events the two purchases were chosen by
  `the_gift_plan_asked_for_this_offer_and_the_shop_covers_it` with `learning: None`. So the lesson-apply path is a
  human review gate plus 10 independent scopes, not missing code.
- That gate is now operable rather than theoretical: `tools/review_shop_purchase.py` (pinned by
  `tests/test_shop_review_tool.py`, 7 passed) lists every retained sample with its review status, outcome flags
  and reason; records an approved/rejected decision with a note and a 0..1 label; and refuses `--eligible` unless
  `verify_episode_evidence` re-reads the bytes and the run ledger first. Against the three real samples it refuses
  with `delayed_outcome_scope_not_in_run_ledger`: all three carry scope `f855ac82c2b1429a…`, which the ledger no
  longer holds (the retired scope), so no label can make them trainable -- and since they share that one scope they
  could never supply the 10 independent episodes the export requires.
- Card ⑥'s source-anchor review now has a measurement instead of an impression:
  `tools/verify_wiki_citations.py` (pinned by `tests/test_wiki_citations.py`, 10 passed) classifies the 1,280
  `path.py:LINE` citations in `docs/wiki` as 383 with no symbol named beside them, 397 inside table rows that name
  several at once, 300 whose path does not resolve as written, 12 whose named word the cited file never mentions (or
  is only the module's own name), and 188 that do name a symbol -- of those, 167 land within 16 lines and 21 have
  drifted after its `--apply` re-pointed the 27 that were unambiguous (a single definition-like line, or a single
  occurrence) onto their real line in both language mirrors. What is left is ambiguous by construction: a symbol with
  several homes, such as `STAR_GRACES` (9 occurrences) or `open_game` (3). One repaired example:
  `docs/wiki/en_us/3-runtime.md:456` cited `src/maalimbus/runner.py:2824` for `claim_family_made_no_progress` while
  the reason is now set at `:2954`. `tools/check_wiki.py` (ok, 0 problems across 26 files) and the citation
  resolver cannot see this class, because a citation that lands on another real code line is structurally valid.
  `python tools/wiki_route.py --build` regenerated the index (`--check`: valid, 15 routes, `snapshot_stale: false`)
  and moved the run-count row to `src/maalimbus/runner.py:174` `Settings`; `docs/wiki/agent-index.md`,
  `agent-index.json` and `routes.json` are still untracked in the working tree, so the drift list is recorded here
  as the next bounded pass rather than silently rewritten.
- The live retest then carried the chain past that stop and booked the receipt: the run's `floor_gift_ranking` at
  12:05 selected `Today's Expression` (`selection_source: single_free_select_button`, proof `frame-0057.json`), the
  `Select` intent (`select_takes_the_picked_floor_gifts`, point `[1686,873]`) was answered by the notice, and
  `config/user-floor-gift-transaction.json` now holds `pending: null`, `commit_sent: true` and
  `receipts[0] = {title: Today's Expression, receipt: frame-0059.json, successor: frame-0060.json}`. The window runs
  on `difficulty: hard` (`difficulty_gate`, required `hard`), and the ledger's active scope
  `3122877b7bb64409b6ad9fe68522de7b` carries `floors [1, 2]` (`floor_clear-1` from the packaged run,
  `floor_clear-2` from this run's `frame-0014.json`) against `completed_runs: 2` overall. It launched with
  `run_count: 0`, so card ③'s stop is not armed in this window and the live bound is `steps 400` / `budget 5400s`.
  Still owed: the full five-floor clear with payout and entry return, and a window that is actually armed with a
  saved run count.
- A third live stop exposed the same reader-versus-transaction gap on the shop shelf: at 12:14 this run stopped with
  `Shop successor shows an offer the shelf never held` (`mirror_loop_stopped`, 68 steps / 67 clicks, `passed: false`)
  while settling the `Rusted Cutting Knife` purchase it had just made for 244 of 1530 coins.
  `config/user-shop-3122877b…json` kept `pending.stage overlay_intent`, and the returning frames 0201/0202 show the
  very same six slots with the bought card under its own `Purchased` badge -- but the visit's own reservation frames
  0195/0196 had read the 160-coin slot as "Thomy Path" while the returning shelf read "Thorny Path", its catalogue
  name (`assets/resource/base/gift-catalog.json` `gifts[280]`), so the strict title comparison called a card the
  shelf had held all along an offer it never held. `src/maalimbus/shop_transaction.py` now folds the condensed `rn`
  ligature into `m` beside the typeface's other confusable glyphs (pinned by
  `tests/test_shop_transaction.py::test_a_condensed_ligature_reads_as_the_same_slot` and the negative
  `test_the_ligature_fold_is_not_a_licence_to_shorten_a_title`), and replaying the stopped store against
  `frame-0202.json` settles it: `reconcile_purchase` returns True, `bought[-1]` is `Rusted Cutting Knife`, `pending`
  is cleared. The installed app still has to carry this fold before a five-floor clear can be attempted again.
- The same reader gap then showed itself once more, one blank wide, and this time on the shelf the run had just
  written itself: the app relaunched on the folded build stopped after 3 inputs (`pi-20261014-082326`, 41 events)
  on the identical `Shop successor shows an offer the shelf never held`. Its own reservation frame-0002 read the
  144-coin slot as `Crownof Roses`, its returning frame-0008 printed the catalogue spacing `Crown of Roses`, and the
  two keys differed by a single space. `src/maalimbus/shop_transaction.py::_fold` now drops the blanks beside the
  confusable class and the `rn` ligature (it still cannot shorten a title, because the letters and digits have to
  agree one for one). Pinned by
  `tests/test_shop_transaction.py::test_a_space_the_reader_dropped_still_names_the_same_slot` and
  `::test_the_space_fold_is_not_a_licence_to_shorten_a_title`; replaying the stopped store against frame-0002 and
  frame-0008 now lists no offending offer at all. 55 tests pass in `tests/test_shop_transaction.py` +
  `tests/test_prune_shop_state.py`.
- Under that lay a state bug that could have ended the live acceptance for good: the next launch raised before its
  first step. `mirror_loop_error` recorded `ValueError: Configuration/state exceeds 2 MiB` straight out of
  `maalimbus/shop_transaction.py:172` -> `storage.py:43` (`pi-20261014-082856`, 0 steps), because
  `config/user-shop-3122877b….json` had grown to 2,464,332 bytes. The cause was the decision context: it recorded
  `owned_bought` as the *whole* purchase records, and every record carries its own decision context, so each purchase
  embedded the previous ones. `src/maalimbus/runner.py` now records their names, `shop_transaction._context` enforces
  that shape at the store boundary (names are also what `shop_value_training._text_list` accepts), and
  `tools/prune_shop_state.py` rewrites the files an earlier version left behind -- it reported
  2,464,332 -> 46,950 bytes for the live scope and 375,287 -> 36,674 for the other, touching only that one field, and
  is pinned by `tests/test_prune_shop_state.py` (dry-run, idempotence, an unknown shape it refuses). The pruned store
  reads under the ordinary 2 MiB guard again, with all seven bought cards and the pending `Tangled Bundle` intent
  intact.
- A sixth real GUI Start (`pi-20261014-193945`, 19:39 local, the app's own Start button pressed with real pointer
  input) stopped after one input on a *refresh* successor it could not prove: the shelf held nothing the plan
  wanted, so the run paid the 15-coin refresh (currency 1127, box `[1478,168,86,28]`) and the next frame read two
  of the six slots with the still pre-refresh counter. `src/maalimbus/runner.py` now waits instead of stopping --
  up to three unproven successor frames per visit, each noted as `shop_refresh_settling`, the intent left unclaimed,
  the fourth still stopping the window -- pinned by
  `tests/test_runner.py::test_a_refresh_successor_read_mid_change_waits_before_it_stops`. The live proof is the next
  launch on that shop.
- 2026-10-14 19:51 local, the next launch (`dist/MaaLimbus/evidence/runtime/pi-20261014-195102`): the wait did fire
  live -- three unproven successor frames in a row, each noted `shop_refresh_settling` (`attempt` 1, 2, 3,
  `reason: the_refresh_successor_frame_is_mid_change`) with no input sent and no ledger write, and the fourth frame
  stopped the window with `Fresh refresh currency delta and complete changed shelf not proven`. Reading that run's
  `frame-0005.png` explains why no frame could ever settle: the game is in its scheduled maintenance window and the
  client shows `Server is under Scheduled Maintenance. You will be able to login after 12:00(KST)`. The shelf behind
  the notice is greyed out with only two slots legible (`of Roses` 144, `Thorny Path` 160) and the currency still
  reads 1127, so the 15-coin refresh was never delivered. The stop is therefore honest in both directions: nothing
  was booked, and nothing claims the refresh happened. The pending refresh intent stays unclaimed in
  `config/user-shop-3122877b7bb64409b6ad9fe68522de7b.json`; because the cost was never charged, the next live run
  after maintenance will simply attempt it again. Hard five-floor live proof remains blocked until the server is
  back.

## DSH continuation: the redesigned Mirror Dungeon, entry to the reward page (2026-10-15)

The 2026-10 redesign moved the entrance, the floor-gift pages and the purchase dialog, so this session walked
one live stop at a time, fixed the reader that was actually wrong, and re-froze the app between runs:

- Entry: `pi-20261015-071912` and the later GUI Starts raised inside the observation node on the participant
  counter (`PRE_BATTLE_TEAM`). `agent/recognition.py` now observes the entry tolerantly while the saved ledger
  still holds an active run and records `mirror_entry_observation_failed` instead of raising; the re-frozen
  build then entered the loop (17:31 run: `mirror_loop_start`, 75+ frames of real battle).
- Star/grace pages: `star_vision`/`grace_vision` re-anchored on the redesigned layout (commit `45adac7`),
  retaining the visual-threshold star card check and the numbers the dialog prints.
- Reward page, two false stops, neither of them the game changing:
  - `three_free_gift_trial_or_cost_present` on `dist/MaaLimbus/evidence/runtime/pi-20261015-172214`: the veto
    treated `Defense Level Down until` `[844,534,244,25]` -- one card's own effect sentence -- as a trial, while
    the page's buttons are `Refuse Gift` and `Select`. The veto now fires on wording that carries a price: a
    shop/trial noun (`Modules`/`Purchase`/`Shop`/`Lunacy`/`Mounting`/`Trials`) or a trial/price word followed by
    a number. `tests/test_three_free_gifts.py` pins both directions and `tests/test_free_gift_descriptions.py`
    keeps the measured price lines vetoing.
  - `floor_gift_identity_unknown` on `dist/MaaLimbus/evidence/runtime/pi-20261015-180214` (345 frames, the run
    the user started): the catalogue `assets/resource/base/gift-catalog.json` spelled the entry
    `Arrested Hymm` while the client prints `Arrested Hymn` (20 of 20 occurrences in `build/learning-review`),
    and one letter in 12 scores 0.9167 against the 0.93 gate in `src/maalimbus/gift_vision.py::text_identity`.
    The entry is corrected (icon `path`/`sha256` untouched) and `text_identity` accepts a single name of length
    >= 8 one edit away; `tests/test_gift_vision.py` pins the slip and the short-name refusal.
- Purchase dialog: the redesigned confirmation prints `1102` and `895` as one token `1102895`
  (`[1234,232,126,36]`), so `purchase_balances` read no affordance and
  `the_shop_asked_about_a_purchase_and_its_confirm_was_not_read` stopped the 251-frame run. The badge is now
  split on the paid delta and checked against the recorded price, with the whole dialog re-read from the
  frame that stopped the run before the fix landed.
- Still open from the user's own brief (m01434): an explicit completed-run count instead of the step window as
  the goal (the window is already raised to >= 4000 when a count is named), and the gift search opened up so it
  learns what to buy; the step ceiling stays as a safety net, and coins keep their carry cap and reserve.


## DSH continuation: one general answer to "the page did not move" (2026-10-15)

The redesigned client keeps producing pages the old tree never saw, and each one used to end the run with its own
reason string. Two general mechanisms now cover the whole family, both in `src/maalimbus/runner.py`:

- `RECOVERY_LADDER` (`src/maalimbus/runner.py:301`) is an ordered list of page-independent gestures: the map
  pinch-out whose two finger tracks were proven live by `tools/map_zoom.py` (`tools/map_zoom.py:52-70`), a
  swipe-back, and a plain tap. `_recover` (`src/maalimbus/runner.py:3321`) tries them in turn, records
  `recovery_attempt` with the gesture and the page, and only after the ladder is exhausted ends the run with the
  original reason plus the gestures it tried. `recovery_tries` (`src/maalimbus/runner.py:167`) bounds the ladder
  and can be set to 0 to switch it off; the legacy runner tests pin exactly that so they stay deterministic.
- `stall_watchdog` (`src/maalimbus/runner.py:342`) watches the heartbeat the runner already writes and, when no
  page changed for its limit, ends the run with a distinct reason instead of leaving the app hung; it runs as the
  daemon thread `maalimbus-stall` (`src/maalimbus/runner.py:3375`).

Live evidence for both: `dist/MaaLimbus/evidence/runtime/pi-20261015-193010` stopped with
`unexpected_successor` on the map after 24 clicks, where the correct move was a zoom-out, and `maafw.log` shows
the 19:16:07 recognition call burning 0 s of CPU for 12 idle minutes: the hung case the watchdog now names.

A third live run (`pi-20261015-200848`) showed the ladder arriving too late on the map: it clicked five candidate
nodes in ninety seconds while `Exploring Floor 3` never changed, and the run looked wedged until the user stopped
it. On the map the pinch is therefore spent on the *first* stalled click (`_map_zoom_once`,
`src/maalimbus/runner.py:3304`), booked as the ladder's rung 0 so the ladder cannot spend it twice, and only the
next stalled click falls back to another candidate.

Docs: chapter 9 section 9.3.8 in both languages (`docs/wiki/zh_cn/9-execution-plan.md`,
`docs/wiki/en_us/9-execution-plan.md`), the `recovery` route in `docs/wiki/routes.json`, and the rebuilt
`docs/wiki/agent-index.md` / `docs/wiki/agent-index.json`. `tools/check_wiki.py` reports 0 problems.

Still open from the user's brief (m01434, m07672): count completed Mirror Dungeons instead of the step window,
and open the gift search so the planner learns what to buy; the wiki is to be used and updated, not only code.

## DSH continuation: a modal that cannot be read no longer ends the run (2026-10-15)

User wording (m08238): be structured and frameworked, and the direct question "surely every gift that is not in
the catalogue will not stop the run?". The two new stops are the same thing: the page already offered a safe exit
or a safe default, and the criterion treated it as nothing to continue with.

- The purchase dialog (`the_shop_asked_about_a_purchase_and_its_confirm_was_not_read`, live run
  `dist/MaaLimbus/evidence/runtime/pi-20261015-202635`): the criterion chain `matching_purchase_question`
  (`src/maalimbus/shop_vision.py:354`) demanded the name, `before - after == price` and `balances[0] == coins` all
  strictly equal, while in that same run the shop read `1808` and the dialog badge read `1809`. The new
  `purchase_dialog_answer` (`src/maalimbus/shop_vision.py:408`) answers `('purchase', box)` only for a name that is
  adjacent (`close_to(..., 1)`) and a badge that spends exactly the reserved price, and `('cancel', box)` for every
  other reading, with `COIN_DRIFT = 2`; `src/maalimbus/window.py:610` clicks that Cancel and re-reads the shelf on
  the next frame, and the old refusal survives only for a dialog whose Cancel cannot be read either.
- Gifts outside the catalogue: `floor_gifts.observe` (`src/maalimbus/floor_gifts.py`) used to raise
  `floor_gift_identity_unknown` whenever `text_identity` returned `None`, so any gift missing from
  `assets/resource/base/gift-catalog.json` ended the run. `identity_of` / `keywords_of` now fall back to the title
  the page itself printed (empty keyword set), so the offer still ranks and still reaches the receipts and learning
  records it under the name it saw.

Docs: chapter 9 section 9.3.9 in both languages, the README row, and the corrected 9.3.7 acceptance line.
`tools/check_wiki.py` reports 0 problems; `tools/verify_wiki_routes.py --check` passes.

## DSH continuation: a scene read is not an authorization (2026-10-15)

The run after that freeze (`dist/MaaLimbus/evidence/runtime/pi-20261015-212438`, started 21:24:38) stopped after
two seconds with `mirror_loop_failed; Full matching purchase title/price/question not proven`
(`src/maalimbus/shop_transaction.py:384`). A 159-coin reservation left by an earlier run met a dialog whose own
badge asked 390; the button the scene read was planned anyway, the transaction layer rightly refused to authorize
it, and the refusal ended the whole run. 9.3.9 fixed "cannot be read"; 9.3.10 fixes the other half.

- `shop_state` (`src/maalimbus/runner.py:1111`) no longer hands a `confirm` over on the `SHOP_PURCHASE` page: the
  dialog's `Purchase` is a scene anchor only (`readable` writes the trace reason). The page's only authorization is
  computed by the `SHOP_PURCHASE` branch of `_observe` (`runner.py:2074`) from the reserved intent's name, price
  and coin count, falling back to `shop['cancel']` when the account does not match; with no reservation at all the
  dialog's own `Cancel` is the only input offered (`a_purchase_question_this_run_never_reserved`).
- `ShopTransaction.retire_pending` (`src/maalimbus/shop_transaction.py:390`) clears the reservation before that
  Cancel lands and records why in `visits[...]['retired']`; without it every later purchase would be refused as
  'already reserved' and the run would sit on the same dialog.
- A wrapped gift name is proof by its words, not by the order its lines arrived in. The 21:34:16 run
  (`dist/MaaLimbus/evidence/runtime/pi-20261015-213416`, 5 inputs) looped SHOP <-> SHOP_PURCHASE on one card and
  stopped with `mirror_loop_failed; the observation node recorded no page for this frame`: the dialog's name band
  had been read as the boxes `Mirror, Calm`, `Clear`, `Water` for the gift `Clear Mirror, Calm Water`, so the name
  check never held, every frame answered the dialog with its own Cancel, and the shelf chose the same offer again.
  `names_match` (`src/maalimbus/shop_vision.py`) compares the band as a word multiset instead - the order of the
  lines is not part of the proof, the client font's single-glyph slips still are - and the same live frame with the
  390-coin reservation answers `purchase` on its first frame.
- Tests: `tests/test_shop_vision.py::test_the_purchase_pages_own_button_is_never_an_authorization`,
  `tests/test_shop_transaction.py::test_a_reservation_the_modal_never_asked_about_is_retired`, the new
  contract pinned in `tests/test_runner.py::test_the_purchase_question_offers_only_the_confirm_it_printed`, and
  `tests/test_shop_vision.py::test_a_wrapped_gift_name_is_read_in_whatever_order_its_lines_came`.
  Full suite 1754 passed, 1 skipped; the two shop files 86 passed, runner+window 132 passed.

Docs: chapter 9 section 9.3.10 in both languages and the README row.

On the next Start (`dist/MaaLimbus/evidence/runtime/pi-20261015-214921`, 21:49:21, inputs=1) the *transaction* layer
was the one still asking for the retired question sentence (`ShopTransaction.reserve_confirm` ->
`matching_purchase_question`), so the modal the plan had just authorized could not be paid for and the run ended on
`mirror_loop_failed; Full matching purchase title/price/question not proven`. `reserve_confirm` now asks
`purchase_dialog_answer` first (gift band by its words, badge spending exactly the reserved price, coin counter on
the reserved intent) and keeps the older wording only as a fallback for the pre-redesign client.

## DSH continuation: the receipt is the currency delta, and the value model is labelled by the run itself (2026-10-15/16)

The user's report (m08801) was that a purchase *succeeded* and the run then died immediately, and that the neural
network must actually be implemented ("你没有这个东西，我们搞一些硬边界都没有用"). Two changes answer it.

First, the receipt. `ShopTransaction.reconcile_purchase` used to require the successor shelf to still show the
bought card (`bought` matched through `_same_title`); on `pi-20261015-215812` the shelf re-printed the truncated
title `Clear Mirror, Calm Wate`, the fold could not adopt it, and the run ended on
`mirror_loop_failed; Independent complete successor shelf not proven` even though the currency delta proved the
purchase exactly (1809 -> 1419 = the reserved 390). The exact delta is now the receipt: `shelf_evidence` is
`own_purchased_badge`, `removed_offer` or `exact_currency_delta`, and a shelf that cannot corroborate the delta is
recorded as `successor_note` instead of ending the run. Folded-glyph adoption is still refused.

Second, the network. Nothing ever labelled the recorded purchases and the runtime model root did not exist, so
`rank_preview` always took `purchase_value_model_missing_rule_fallback`. Now:

- `shop_value_training.label_from_outcomes()` derives the label from the run's own later observations (floor 0.2,
  victory 1.0, reward/early return 0.1) with a digest over the bound bits only;
- `review_sample()` approves a folder only when a ledger-bound later observation exists, and the loader re-derives
  the label and excludes `objective_label_mismatch`;
- the trainer gates participation on its own whole-run holdout (`split_by_scope`, >= 4 pairs and accuracy >= 0.6 ->
  `ranked`, otherwise `shadow`), and a ranked model only reorders inside the set the plan already approved;
- `tools/shop_value_review.py --install` copies the candidate into `assets/resource/base/model/shop-value`.

Measured 2026-10-15: 10 folders, 7 labelled from observation, 3 pending (no later observation), 1 verified run /
6 rows, 0-pair holdout -> participation **shadow**; the candidate scores offers (Awe 0.5488, Clear Mirror, Calm
Water 0.5397, Tangled Bundle 0.5316) and does not reorder. Steering begins when a second verified run makes a
hold-out comparison possible.

Tests: `tests/test_shop_value_review.py` (6 new), `tests/test_shop_transaction.py` updated; shop/vision/value/
learning/window/runner 232 passed. Docs: chapter 9 section 9.3.11 in both languages plus the README row.

## DSH continuation: the page-identity side counts differing glyphs instead of listing them (2026-10-16)

The next Start after the refreeze (`dist/MaaLimbus/evidence/runtime/pi-20261016-011659`, 01:16:59, inputs=0) stopped on
`Shop successor shows an offer the shelf never held`. It was reconciling the reservation `pi-20261015-214921` had left
behind (Clear Mirror, Calm Water 390, 1809 -> 1419 `own_purchased_badge`) and the only stray row was the same page's own
`Voodoo Doll` 149, which this frame's reader had named `Vaodoo Doll`: the typeface draws `a` and `o` one bowl apart,
`_fold` folds `o` but not `a`, and the check at `src/maalimbus/shop_transaction.py:553` therefore called the successor a
different page and ended the run before its first input. (The log line "旧局仍在进行，跳过开新局的设置应用" is the
expected stale-session behaviour, not part of this stop.)

`_one_glyph_apart` (`src/maalimbus/shop_transaction.py:73`) and `held_offer` (`:541`) now answer the page-identity
question by counting differing positions -- equal length, exactly one folded position differs, and the price agrees --
instead of enumerating glyph pairs one at a time, which is what let this class of stop recur (i/l/1, o/0, rn/m, spacing,
now a/o). It is deliberately not a title match: the bought card is still matched by `_same_title`, the receipt still
needs its own `Purchased` badge plus the exact coin delta, a title cannot shorten, and a different price is not the same
row.

Tests: `tests/test_shop_transaction.py::test_a_neighbouring_slot_read_with_one_glyph_of_noise_is_still_the_same_page`,
`::test_one_glyph_of_noise_is_not_a_licence_to_shorten_or_repricing`, and the live replay
`::test_the_live_resumed_purchase_across_runs_is_receipted` (the three real frames of the round trip, skipped when the
retained evidence is absent). Wiki: decision D14 gained the continuation in both languages, and its item 8 now says
which side no longer enumerates.

## DSH continuation: the ledger's archived runs still label a purchase, and one label value halves the gate (2026-10-16)

The value model was installed and could never rank anything, and the reason was not the corpus size.
`_scope_evidence` (`src/maalimbus/shop_value_training.py:389`) looked for a scope's evidence binding only in the
ledger's `active` and `receipts` lists, while `run_wiring.expire()` files an expired or superseded run under
`abandoned` -- where `f855ac82c2b1429aae9c747a122213b8` sat with its own four `floor_clear` events, the very
observations that label that visit's purchase. Reading two of the three lists meant a purchase could be labelled only
while its own scope was still active, so the corpus could never hold two scopes and the held-out comparison could
never exist. `_ledger_runs()` (`:374`) now reads all three, still refusing a scope the ledger files twice as
`run_ledger_scope_ambiguous`; the live corpus goes from 1 run / 6 rows / 0 held-out pairs to 2 runs / 7 rows / 6
held-out rows.

The second half is not a bug. `label_from_outcomes` takes the run's own maximum later return, so every row of one run
carries essentially the same number -- how far that run eventually got. The live corpus reports `label_values`
`[0.6]`, one distinct value, and `len(targets) > 1` correctly keeps the candidate a shadow rather than promoting a
ranker whose only lesson is a constant. `train_and_export` now writes `label_values` and a reason that says which gate
held (`..._blocked_because_every_row_in_the_corpus_carries_the_same_outcome_value_0.6`) into the report and the
modelcard. The confound this exposes is recorded too: a label that measures the run can teach which gifts appeared in
strong teams rather than which gifts are worth buying, so `ranked` needs a within-team control before it is handed
over.

Tests: `tests/test_shop_value_training.py::test_a_scope_the_ledger_filed_as_abandoned_still_carries_its_label`,
`::test_a_scope_the_ledger_files_twice_is_still_ambiguous`, `::test_one_outcome_value_in_the_whole_corpus_cannot_teach_a_ranking`,
`::test_two_outcome_values_are_reported_however_the_fit_turns_out`. Wiki: the 9.3.11 continuation in both languages
now records both halves and names the confound.

## DSH continuation: the map offers its steps by colour, not by one floor's badge bitmap (2026-10-21)

The next Start (`dist/MaaLimbus/evidence/runtime/pi-20261021-185251`, 18:52:51) walked floor 1 `Dregs of the Manor`
for eight minutes and stopped at 19:00:56 on `no_candidate_node_observed`, 51 steps and 48 inputs in. The journal is
unambiguous about the cause: `window_map_retry` reached `remaining: 0` on a target of `[1521,307,190,190]`, and the
four candidates the page ever offered were the player's own icon, a path chevron and two lattice guesses inside the
empty black panel beside the map. Every one of them was a click on nothing.

`frame-0119.png` shows what the reader missed. The floor marks the nodes it offers with five gold rings, 24 px across,
BGR (21,140,223), drawn on each node's top edge: (863,404), (1055,403), (1247,403), (1247,564), (1055,723), over the
nodes at (863,448), (1055,447), (1247,447), (1247,608) and (1055,767). `node_badge_template()`'s stored bitmap matched
none of them on this floor, so the badge channel contributed nothing and the lattice guess was left carrying the page.

`gold_marks` (`src/maalimbus/map_vision.py:880`) reads the ring off its colour instead -- hue 10-40, saturation >= 120,
brightness >= 140, a blob 14-46 px -- and `gold_badge_drop` (`:916`) lifts each mark onto the node it is drawn over
(+44 px, measured on that frame). The candidates come out as `gold_badge_node` (`:1097-1100`), ranked behind the walked
path, the lit ring and the lit icon, and ahead of the neutral outline, the badge lift and the lattice. The reading is
gated on `node_markers` having found nothing at all: on a gold-painted floor (`window-20261006-212950/frame-0058.png`)
gold is everywhere, and without the gate a lit ring read as a badge would dedupe the shop node away.

Tests: `tests/test_map_vision.py::test_the_offer_mark_is_read_by_its_gold_not_by_one_stored_bitmap`,
`::test_the_live_floor_one_offers_the_five_gold_badged_nodes` (the retained frame replayed, all five node coordinates
compared). Wiki: decision D15 in both languages. **No live run has exercised this yet** -- the frame replay is the only
evidence, because a Start can only come from the user.

## DSH continuation: the gold reader becomes a labeler, so its false positives matter (2026-10-22)

Same 389 retained map frames replayed: 3831 marks, about half of which cannot be a node the floor
offers. Two structural causes were fixed in `src/maalimbus/map_vision.py` -- `GOLD_MARK_MERGE = 25`
folds a ring the badge icon split in two (`[1448,342]` / `[1449,345]`), and the exclusion band now
ends at `.80` instead of `.84` because the party strip starts at about `.78` and its twelve gold
avatar frames were read as badges. The replay now yields 3014 boxes, 5 per frame modal, 18 max; the
live frame still reads its five nodes and `tests/test_map_vision.py` is 50 passed.

`tools/export_map_dataset.py` turns that reader into a dataset labeler: per-run splits, unmarked map
frames kept as negatives, manifest under `build/map-dataset/samples.jsonl`. It labels only -- the
`NeuralNetworkDetect` candidate still has to beat the rule on held-out runs before it is enabled.
The discriminator still missing is structural: a node (dark hexagon) must exist directly below the
ring, or the mark is dropped. Wiki: D15 continuation in both languages.

## DSH continuation: a live run refutes the ring gate, so the offered marks outrank the guesses (2026-10-22)

`evidence/runtime/packaged-mirror-20261021-200907` is the first run driven by this session
rather than by a human pressing Start: `tools/verify_packaged_mirror_loop.py --authorize`,
the installed `MirrorTask`, the frozen agent, the real controller. It stopped after 14 steps
with `unexpected_successor` once the recovery ladder was spent. Its last frame had three
gold rings at (1247,220), (1439,220) and (1055,380), and the reader handed out none of
them, because the ring branch was gated on the badge scan finding nothing -- while the scan
still guessed, so nine retries went to the info/guide/party/help column at (1791,324) and
(1801,254).

Commit `021a247` removes the gate, computes the nodes the badge/ornament readings will name
before adding the rings (a ring within 90 px of a named node is skipped), and forbids a
guess -- never a proven reading -- from proposing the right-hand button column at all.
`tests/test_map_vision.py` 50, `test_runner.py` + `test_window.py` 132,
`test_recovery_ladder.py` + `test_stall_watch.py` 10 passed. The app is frozen at that
commit (`build/agent-refreeze-20261022002423`) and the next live run is under way.

## DSH continuation: the map refused the click, so retrying was bookkeeping (2026-10-22)

`evidence/runtime/packaged-mirror-20261021-202503` ran with the corrected ring ordering and
stopped after 10 steps (`no_candidate_node_observed`). The rings were at (1247,220),
(1439,220), (1055,380) and the reader emitted `gold_badge_node` at (1247,264), (1439,264),
(1055,424) -- the right points. Every intent was followed by `window_map_retry` on the same
target, then the ladder, then the stop.

Measured outside the agent with `adb shell input tap` on the same map: ringed nodes,
chevron-marked nodes and both `?` nodes all changed ~2 500 px (particle noise), while the
gear at (1229,42) changed 228 435. Input works; this map page accepts no node step. A map the
game will not step on is not a map with no nodes, and retrying a target that provably did
nothing is the ladder keeping books instead of diagnosing. The rule recorded in D15: a page
whose inputs are provably inert must be handed over rather than retried.

## DSH continuation: the floor was paused, not dead -- and the game reports its own progress (2026-10-22)

The run that produced `evidence/runtime/packaged-mirror-20261021-202503` looked like a floor
that refused every click: seven inputs on ringed, chevron-marked and `?` nodes, every frame
pixel-identical. Opening the game's own pause menu on that same screen disproved the reading:
**Dungeon Progress: Floor 1 (HARD) 4/5**. The party had already stepped four times this floor;
the clicks were landing, the map simply had no next step to give, and the identical frames
were the map at rest rather than a map that ignored input. The dungeon was also *paused*,
which is why a fresh driver run had nothing to advance either.

Two things out of this that outlive the coordinates:

1. **The pause menu is a ground-truth progress oracle.** `Dungeon Progress` names the floor,
   its difficulty and `N/5`, and the panel stays readable while pausing. The library has no
   reader for it yet, and it is the only in-game statement of how far a run actually got --
   worth reading before a run (does the floor still have steps?) and after one (did it move?).
2. **`no_candidate_node_observed` is still the wrong name for "the floor has nothing left to
   give".** `map_stop_reason` (commit `a95b1e4`) already separates "no candidate in this
   frame" from "candidates were clicked and nothing moved"; a third case is now known -- the
   floor is at its last step and the only marker left is not a step at all.

## DSH continuation: the floor was not refusing clicks -- the run had already lost (2026-10-22)

Chasing the "map that accepts no node" ended when I used the game's own pause panel to leave:
`Forfeit` -> `Quit exploring the dungeon?` -> **Defeat**, then `Exploration Complete`:
`Floor 1 [HARD] 4/6`, `Last Reached: Mirror of Sisyphus / Floor 1 [HARD]`,
`Total Progress 13%`, then `Exploration Reward` with `Weekly Bonuses 3/3` (all three spent),
`Starlight 20`.

So the frames the loop kept re-reading were a *stale map*: the party had lost the fight and
the client was sitting on the map underneath the result flow, which is why seven clicks, a
double tap, a long press, a chevron tap and a drag all moved under 4 000 pixels while the gear
button moved 228 435. The reader was never the problem on that screen; the *page identity* was.

What this leaves behind, in order of how much it would have saved:

1. **A defeat that renders as a map must be recognised as a defeat.** `vision.classify` has a
   `defeat` locale key, but nothing on those frames matched it -- the banner is not drawn on
   the map underneath. The run's honest state was "lost the fight", and the loop could not say so.
2. **The exploration summary is the run's receipt.** `Exploration Complete` names the floors,
   the last one reached (`4/6`), the dungeon (`Mirror of Sisyphus`) and `Total Progress 13%`,
   all on one screen -- a far better end-of-run record than the frame it stopped on.
3. **The three weekly bonuses are a budget the run must read, not assume.** This summary says
   `3/3`; the user's goal is three Hard clears, and what those clears are worth depends on
   whether those slots were already spent.

## DSH continuation: the end-of-run summary is a page, and a lost run never claims (2026-10-21)

The 2026-10-21 self-driven run (`evidence/runtime/packaged-mirror-20261021-202503`) stopped on
`no_candidate_node_observed` with every map click inert. The map was not stuck: the battle had ended in
`DEFEAT`, and the client kept drawing the map behind the result screen, so the loop read a page that
ignored input. Only the client's own pause panel (`Dungeon Progress`, `Floor 1 (HARD) 4/5`) and then the
`Exploration Complete` summary (`Floor 1 [HARD] 4/6`, `Total Progress 13%`) said what had really happened.

`src/maalimbus/dungeon_progress.py:exploration_summary` now reads that receipt -- floor, `steps/of`,
`Last Reached`, `Total Progress` -- and the title is read as the two lines the client draws, not as one
merged token. `src/maalimbus/vision.py` names the page `EXPLORATION_COMPLETE` and
`src/maalimbus/window.py` refuses it with `the_dungeon_run_ended_at_its_summary`.

The user's correction drives the ordering: a summary that reports less than 100% is a run that was LOST,
and its `Claim Rewards` is never touched. That gate sits after the reward-modal branches -- those modals
are drawn over the summary and must keep their own names -- and before the pause-panel branch, which the
summary would otherwise match because its left column also prints `Dungeon Progress`.

Tests: `tests/test_dungeon_progress.py::test_the_end_of_run_summary_states_where_the_run_really_got`,
`::test_the_summary_is_not_read_as_the_pause_panel_under_it`,
`::test_a_lost_run_never_reaches_its_claim_buttons`,
`::test_a_cleared_run_still_claims_its_rewards`. That file now uses the shipped locale for page identity
instead of a hand-rolled stub, which is what made the classifier's later branches reachable.


## DSH continuation: once the task ends, the window posts no more input (2026-10-21)

The self-driven run `evidence/runtime/packaged-mirror-20261021-211030` got through DRIVE (after
`f398b1f` renamed the node to the `MirrorDrive` the pipeline actually declares) and then died on the
entrance click with `OSError: exception: access violation reading 0xFFFFFFFFFFFFFFFF` at
`runner.py`'s `click` -> `maa/controller.py`'s `post_click`. `debug/debug/maafw.log` shows the order
in that same second: `WindowMapObserve` `PipelineTask node done [completed=false]` ->
`OnEventNotify msg=Node.PipelineNode.Failed` -> `node not completed, handle error` ->
`_CustomActionResponse ret=false`. Maa was tearing the task down; the loop was still posting into it.

`MaaDevice.end_session(reason)` (`src/maalimbus/runner.py:387`) now records on the device that it may
never post input again, and `_refuse_if_ended` (`:415`) makes `click` / `swipe` / `key` refuse by name
before anything goes out. `Runner._end_session` (`:1500`) sets `state['session_ended']`, writes
`mirror_session_ended`, and arms the device; the `run()` loop stops instead of calling `step()` and
records `mirror_loop_stopped / reason=the_pipeline_node_failed_before_the_next_input`; a `RuntimeError`
or `OSError` out of `step()` takes the same path through `the_task_raised_before_the_next_input`.

An earlier attempt this round scaled click coordinates to the device and refused out-of-range points;
it was reverted because `test_maa_device_maps_the_loop_onto_the_controller_it_was_given` proved the
controller is already told `target_long_side 1920`, so Maa maps coordinates itself and a second scale
would double-apply.

Tests: `tests/test_runner.py::test_the_device_refuses_input_once_the_session_ended` (52 passed in that
file). Wiki: decision D16 in both languages. Honest limit: a native access violation cannot be caught
in Python, so this layer guarantees that once we know the session is dead nothing more is sent, and
that a failure always leaves a readable stop reason. A full Hard five-floor clear is still unproven.


## DSH continuation: the gold ring has to sit on the map's lattice (2026-10-21)

`gold_marks` answers "which nodes does the game offer" by the gold ring the client draws above
each one. Three statistical guards were measured first and all three were refuted on 1000 rings of
`build/map-dataset` frames: mean brightness (node 51 vs empty 19), dark-pixel share (node 0.35 vs
empty 0.80) and texture deviation (node p10 11.8 vs empty max 101.6) overlap, because empty map space
is uniformly black while a node is a dark body with a lit rim; no single threshold separates them.

The principled guard is the one the floor itself provides: nodes sit on a lattice (192 px across,
160 px down, 192x160 diagonal at 1920 wide), so `lattice_consistent` (`src/maalimbus/map_vision.py:922`)
keeps only rings that stand at one of those spacings (9% tolerance) from another ring in the same
frame. A lone ring is kept, a frame whose rings share no spacing is kept whole, and an empty result
falls back to the input -- dropping every candidate is the failure this reader exists to prevent.

Tests: `tests/test_map_vision.py::test_a_gold_ring_off_the_lattice_is_not_a_node_the_map_offers`,
`::test_a_lone_mark_is_kept_because_one_ring_cannot_be_judged` (52 passed in that file). The dataset
re-exports through `tools/export_map_dataset.py` as 389 frames / 2830 boxes / 7 negatives / 12 runs,
holding out the whole of `pi-20261021-185251`. Wiki: D15 continuation 3 in both languages.


## DSH continuation: the map frames now also exist in the YOLO11 layout (2026-10-21)

`tools/export_map_yolo.py` reshapes `build/map-dataset/samples.jsonl` into the tree the official
recipe reads: `images/<split>/`, `labels/<split>/<stem>.txt` in YOLO's normalised `class cx cy w h`,
`data.yaml`, `manifest.json`. The split is copied verbatim -- it was cut per run, never per frame, and
reshaping must not leak one floor across the boundary -- and a frame with no box keeps an empty label
file so the negatives stay negatives.

Output: 389 frames / 2830 boxes / 7 negatives, train 333, test 56. The tool reads the written labels
back and refuses if their count differs from the dataset, so a normalisation slip cannot reach training.

One honest limitation, recorded in the manifest rather than papered over: the dataset has only two
splits, so `val` points at the held-out run and that run serves as validation and test both. A third
run is needed before the comparison against the rule can claim independent validation.

Training itself is still blocked here: `ultralytics` (and torch with it) is not installed.


## DSH continuation: the held-out labels were on the player's own token (2026-10-21)

Drawing the held-out labels of `pi-20261021-185251/frame-0039` back onto its frame showed both boxes
sitting on the player's own token -- the gold flame and the gold lantern answer the same hue as the
ring -- while the nodes that carried rings were not labelled at all. The false positive came from two
things: the lattice tolerance was computed from the frame width (`width*0.09/2` = 86 px) instead of
from the step it judges, so a 68 px gap passed as a 160 px row; and the "keep everything when no pair
fits" fallback let a frame whose only gold is the player marker through.

`lattice_consistent` now uses a per-step tolerance (`max(8, want*tolerance)`) and, when the kept set
is empty, treats a nearest-neighbour gap under 90 px as one object read twice and returns nothing.

Consequence, stated plainly: the dataset re-exports as 389 frames / **727 boxes / 189 negatives**,
down from 2830 boxes / 7 negatives -- so roughly three quarters of the previous boxes were never
nodes. Tests: `tests/test_map_vision.py::test_the_players_own_gold_token_is_not_a_pair_of_nodes`
(54 passed). Wiki: D15 continuation 4 in both languages.

Open, and the next thing to fix: frames such as `pi-20261021-185251/frame-0067` still show gold rings
yet now read as empty, so the tightening overshot -- the reader has to tell "the ring sits outside the
candidate band" apart from "this floor uses a different lattice family" instead of returning nothing.


## DSH continuation: lattice spacing is a multiple, and a tight cluster is one object (2026-10-21)

Continuation 4 tightened the lattice and overshot: frames like `pi-20261021-185251/frame-0067`
still show gold rings yet read empty. The raw marks there were (1470,360), (702,365), (669,403),
(738,403), (1086,679) -- three on the player's own token, two real rings, and those two sit
(384,319) apart, exactly twice 192x160, because the node between them is not offered this floor.

`lattice_consistent` now decides in a fixed order: drop every mark within `TIGHT_MARK` (150 px) of
another, since that is one object read twice and the player marker is gold; then a survivor counts at
1-3 whole lattice steps from another survivor, multiples allowed per axis; then, if no pair fits,
hand on everything that survived instead of deleting the candidates. The `(96,80)` diagonal was
removed -- it was a guess that was never measured, and keeping it would make a genuine node look like
a tight cluster.

Evidence: `frame-0067` -> two real rings, `frame-0039` -> one real ring, `frame-0119` -> the same five
measured rings. Dataset: 389 frames / **802 boxes / 126 negatives** (from 727/189), and
`tests/test_map_vision.py` 54 passed in that file. Wiki: D15 continuation 5 in both languages.


## DSH continuation: a ring is only a ring when a dark node sits under it (2026-10-21)

QC over `build/qc-sheet.png` found false positives on warm floors: floor 3 paints the board in
orange-gold wash, and `pi-20261015-191205/frame-0030` carried a box on a direction arrow. A hollow-ring
test was measured first and refuted (a real ring's core is the gold sun glyph, coverage 0.88-0.96, the
same as the false positive), so it was deleted.

`_node_below` is the structural test that replaced it: the 40x40 patch `gold_badge_drop()` under the
ring must average <=70 brightness. Real rings measure 12-42; arrow and wash are rejected. Dataset
802 -> **742 boxes / 130 negatives**; `tests/test_map_vision.py` 54 passed.


## DSH continuation: the detector agrees with the rule, so the labels are the ceiling (2026-10-21)

Comparison on the same frames, detector at its third epoch (`build/map-model/run/weights/best.pt`,
yolo11n, imgsz 960) against `maalmibus.map_vision.gold_marks` -- the artefact is
`build/compare-rule-model.png`:

- `pi-20261021-185251/frame-0119` (dark floor): rule 5, model 5, and every model box sits on a rule
  mark. Identical answer.
- `pi-20261015-191205/frame-0030` (warm floor 3): rule 1 -- on the grey **chevron arrow**, not on a
  ringed node -- and the model 0. Neither reads the floor, and the rule is simply wrong here.

So the detector does not beat the rule; it reproduces it. That is what the provenance predicts: the
labels *are* the rule's output, so a student can only be as good as its teacher, and the warm-floor
false positive is now baked into the labels as a negative. Enabling the network today would add a
torch/ultralytics dependency for identical output -- there is no case for it yet.

The ceiling is the labeler, not the model. Beating the rule needs labels from a source the rule is
not: hand-corrected frames, or the node-hexagon structure read directly instead of the ring
brightness. Correction of `maalmibus` typo aside, nothing was enabled in the runtime, and the loop
still reads the rule.


## DSH continuation: the ring-to-node offset is assumed, not measured (2026-10-21)

Two more discriminators were measured and refuted before touching code again:

- *Angular rim coverage* (how much of a 12-sector ring at r=28..42 around the node centre is lit):
  real nodes in `pi-20261021-185251/frame-0119` score 0.17-0.42, and the warm-floor false positive in
  `pi-20261015-191205/frame-0030` scores **0.50** -- higher than every real node. No separation: on a
  warm floor the whole board is lit, so a rim is not locally distinguishable by brightness.
- *Temporal persistence*: the warm-floor mark (890,587) is identical in frames 0020-0025, so it is a
  static object and not the animating chevron. Persistence cannot separate it either.

What the numbers do point at is the constant itself: `gold_badge_drop` returns one global 44 px for
every floor, and the box it produces in that frame (890,631) does not sit on the node the ring at
(890,587) belongs to. The offset is therefore an assumption, not a measurement, and on floor 3's
layout it is likely wrong -- which mislabels nodes rather than merely missing them.

Next: derive the offset per frame from the lattice (the node is the darkest lattice point below the
ring) instead of trusting a constant, then re-export and re-check the warm floor.


## DSH continuation: the offset cannot be derived from darkness either (2026-10-21)

The planned fix was to derive the ring-to-node offset per frame instead of trusting
`gold_badge_drop`'s constant 44. The darkness profile below a ring refutes it: on the dark floor
(`pi-20261021-185251/frame-0119`) the 28x28 mean brightness keeps falling all the way to the scan
limit (84+ px), because the empty board is dark too, so "darkest point below the ring" drifts to the
bottom of the range instead of stopping at the node; on the warm floor
(`pi-20261015-191205/frame-0030`) the darkest point is at 84 as well, at V 31. The node is not the
darkest thing under the ring, so this derivation is unusable.

Counting what has now been measured and refuted for the labeler: ring brightness, ring size, hole at
the ring centre, angular rim coverage, temporal persistence, and darkness below. Every one of them
separates nothing on a warm floor, because a warm floor makes the whole board gold and lit.

That is the real result of this arc, and it should stop the loop of trying cheaper heuristics: the
labeler cannot be rescued by one more threshold. The label ceiling has to be raised by data a rule
did not produce -- a hand-corrected set of frames labelled with the game's own node taxonomy (the
wiki is the best source for those type names), then train on that and compare on a held-out run.

Everything shipped this session stands: `0671a02` (lattice multiples + tight clusters), `403d443`
(dark node under the ring), `f642979` (the detector only reproduces its teacher), `55fef9c` (offset
is an assumption), and the dataset at 742 boxes / 130 negatives over 389 frames with
`pi-20261021-185251` held out.


## DSH continuation: the label ceiling is raised by eye, not by another threshold (2026-10-21)

`tools/map_label_review.py` is the door the next round of labels goes through. It draws the rule's
boxes in red, the reviewer's in green, writes the picture to `build/map-dataset/hand-reviewed.png`, and
appends each reviewed frame to `build/map-dataset/hand-reviewed.jsonl` with `label_source='by_eye'` and
a `node_type` from the game's own taxonomy (`battle`, `event`, `shop`, `reward`, `rest`, `unknown`).
Reviewed frames are meant to win over the rule whenever the two disagree -- that is the only way the
teacher becomes better than the rule.

First reviewed frame: `pi-20261021-185251/frame-0119`, five boxes, all five confirmed by eye against
`build/map-candidates-0119.png` and the earlier zooms; types left `unknown` because the node glyphs
were not read closely enough to claim a type. The types are what the wiki pages are for, and the tool
rejects any name outside the taxonomy rather than inventing one.

Second reviewed frame, and the first one where the reviewer beats the rule outright:
`pi-20261015-191205/frame-0030` (floor 3, warm board). By eye against `build/grid-0030.png` the floor
offers three nodes -- a gift/reward node at ~(300,393) with the gold "180" badge, the player's own node
at ~(630,393) ("150"), and a battle node at ~(965,663) ("85") -- plus an unoffered "?" node and an
unoffered dark hexagon. The rule found **none** of them: its single mark at (890,587) is empty board.
The review records the two nodes that are targets (reward at 240,333 and battle at 905,603) and leaves
the player's own node out, because clicking where the party already stands is not a target.

That is the shape the hand set has to have: the rule errs on warm floors by finding nothing where there
are real nodes, so the corrections are additions, and they are exactly the frames a student trained on
rule labels could never learn from.

The exporter now prefers a reviewed frame over the rule (`tools/export_map_dataset.py`): it reads
`build/map-dataset/hand-reviewed.jsonl` and, for a matching `run/frame`, uses the reviewer's boxes with
`label_source='by_eye'`. The first wiring keyed on `run/frame.png` against a `run/frame` stem and printed
"reviewed 0 frames", which is why the summary line prints that count -- a silent mismatch is exactly the
failure mode that would have left the hand set unused. Dataset now 743 boxes / 130 negatives / 389
frames with 2 reviewed, and `tests/test_map_vision.py` 54 passed.


## DSH continuation: where the map-label work stands at the end of the 40-round goal (2026-10-21)

**Goal status: not achieved.** No Hard five-floor clear has been run end to end, and the detector is
deliberately not enabled. The 40 automatic rounds ended here; a human decides whether to continue.

**What landed (all committed):**
- `0671a02` lattice spacing may be a whole multiple (1-3 steps), tight clusters are one object read
  twice; `403d443` a ring needs a dark node under it, which removed 60 warm-floor boxes;
  `f642979` the detector only reproduces its teacher; `55fef9c` the ring-to-node offset is a constant
  assumption; `a39cac9` the offset cannot be derived from darkness; `cf1c51a` the hand-review door;
  `1275a33` first warm-floor correction; `13b927d` reviewed frames win over the rule in the exporter;
  `1a26899` the hand set lives in the repository, not in `build/`.
- Dataset: **389 frames / 744 boxes / 129 negatives**, held-out run `pi-20261021-185251`.
- Hand-reviewed: **3 frames** in `assets/resource/base/map-labels/hand-reviewed.jsonl`
  (`run/frame`, boxes, `node_types` from `battle|event|shop|reward|rest|unknown`).

**Refuted by measurement, do not retry:** ring brightness, ring size, hole at the ring centre, angular
rim coverage, temporal persistence, darkest-point-below-the-ring. Every one fails on a warm floor,
because a warm floor makes the whole board gold and lit.

**Next, in order:**
1. Grow the hand set with `tools/map_label_review.py --frame <run>/<frame>.png --boxes ... --types ...`,
   prioritising warm floors and frames the rule reads as empty; it is the only label source better than
   the rule.
2. `python tools/export_map_dataset.py && python tools/export_map_yolo.py && python tools/train_map_model.py`
   -- the enable criterion is beating the rule on the frames the rule gets wrong, not agreeing with it.
3. Live runs (`tools/verify_packaged_mirror_loop.py --authorize`) need server maintenance to end and the
   Limbus client front-most in MuMu; MuMu currently fronts another game.

## DSH iteration: one end, one reason; and a revived grace scope keeps its purchases (2026-10-22)

`维护结束了，你继续吧` 之后的两次真机运行各暴露一半问题，都已修在源头，并各带一条可复跑的判据。

第一半是**一次会话被记成两次结束**。`packaged-mirror-20261021-204444` 的停止理由是
`the_task_raised_before_the_next_input`，但那次任务真正失败是因为预算到点：循环在 `except` 里
`_end_session(...)` 之后 `continue`，下一圈看到 `session_ended` 又写一条 `mirror_loop_stopped`，
于是理由由症状覆盖了原因。`src/maalimbus/runner.py` 的循环收口现在在 `except` 里自己判定：
已过调用方截止时间记 `loop_deadline_exceeded`，否则记任务本身，然后 `break`。判据
`tests/test_agent_loop.py::test_a_run_out_of_budget_stops_bounded` 现在要求恰好一条停止事件。

第二半是**复活的会话被当成余额被篡改**。同一个 run 的第二层被
`Grace balance changed outside verified purchases` 挡住：作用域保存的余额是会话第一次读到的数，
崩掉之后货币会因领奖与维护而变化，而复活会话复用了同一个 `run_id`。放宽 `validate()` 先被两个老测试
当场否掉（同一作用域花过钱后漂移必须仍报错），于是改在入口：`GraceTransaction.reset_baseline(reason)`
只把 `available` 置空并记 `baseline_resets`，`selected`/`spent`/`pending` 保留，有 `pending` 时不动；
`runner.py` 入口按作用域分流（不同 → `begin()`，相同 → `reset_baseline`）。

测试：`tests/test_agent_loop.py` 16 passed、`tests/test_grace_transaction.py` 11 passed、
全量 `1792 passed in 156.27s`。提交 `f99fa8b`、`edc005c`。Wiki：决策 `D17`（中英各一节）。

## DSH iteration: the battle HUD names itself in the classifier (2026-10-22)

第 2 层的一次真机战斗帧（`evidence/runtime/packaged-mirror-20261022-010654/frame-0154.json`）里
`WAVE 1/1`、`TURN 4`、`Win/Rate/Damage` 全都干净可读，`maalimbus.battle_vision.battle_hud()` 也认得出，
但 `maalimbus.vision.classify()` 返回 `UNKNOWN`，整回合被当成读不出的页面，只能靠手势梯子绕过。

原因不是识别能力不足，而是**页面名的判定散落在两处**：`agent/recognition.py` 有一个 `battle_hud` 分支，
`vision.classify()` 没有。现在把战斗 HUD 的自我标识放进 `classify()` 本身（`src/maalimbus/vision.py`，
在最后返回 `UNKNOWN` 之前），页面命名回到单一入口。

判据：`tests/test_vision.py::test_a_battle_frame_is_named_by_its_own_battle_hud`（直接吃这一帧的 OCR，
断言 `BATTLE_HUD`；证据不在时跳过）。全量 `1791 passed`，两条失败是控制器租约测试（真机在跑时本该失败）。

同轮还有一处防线：读不出的页面不再直接停窗，先花一次 `_recover` 手势（`runner.py` 的
`page_unreadable_after_waiting` 分支），实机日志已出现 `window_recovery page=MAP gesture=pinch_out`。

## DSH iteration: the shop receipt survives a re-rolled shelf (2026-10-22)

`packaged-mirror-20261022-012400` stopped at its twelfth event on `Shop successor shows an offer the shelf
never held`. The purchase was correct; the shelf had re-rolled between the run that left the reservation and
the run that resolved it, so an offer this session never saw appeared on the successor frame.

`reconcile_purchase` (`src/maalimbus/shop_transaction.py:554`) now records that as `successor_note`
(`the_successor_shelf_holds_offers_this_session_never_saw`) instead of raising. What still refuses is the
bought card itself: `_same_title`, the reserved price, and its own `Purchased` badge.

Tests: the two neighbour tests became receipts, the duplicate badge-path test was rewritten to the same
rule, and `tests/test_a_shortened_bought_title_is_still_refused` was dropped because the documented rule
(the exact delta is the receipt) had already overtaken its premise. Full suite `1792 passed`.

## DSH iteration: an unnamed event is declined by its own control, not by its name (2026-10-22)

`evidence/runtime/packaged-mirror-20261022-013228` is the best live run so far: floor 2, 22 clicks, battles
fought by the loop itself, and it passed the shop page the previous run died on. It then stopped at event
frame-0092 with `Accept/Refuse garden event identity is not independently proven` -- `Choices` over
`Put on the shoes.` / `Refuse.`.

`refusal_choice` (`src/maalimbus/event_vision.py`) now answers any page that prints exactly one declining
control out of exactly two rows, and `runner.py` records `event_identity_not_known` instead of stopping.
Tests: the two new cases in `tests/test_garden_event.py`. Full suite `1794 passed`.

## DSH iteration: the battle guard may not call an unread round a stalled one (2026-10-22)

`evidence/runtime/packaged-mirror-20261022-014748` stopped a healthy floor-2 fight with
`battle_progress_stalled` after 19 inputs. This theme's battle HUD OCR returns `WAVE`/`TURN` and no values,
so the signature was `(None, None)` every round and looked static.

`battle_progress` (`src/maalimbus/runner.py`) now counts only readable signatures as stalls, tracks unread
rounds as `battle_blind`, and hands a long blind stretch to the recovery ladder rather than ending the run.
Tests: the two new cases in `tests/test_runner.py`. Full suite `1796 passed`.

## DSH iteration: the turn dial is found by the caption, not by being lit (2026-10-22)

`packaged-mirror-20261022-015843` 停在 `battle_progress_stalled`，但这次守卫判对了：签名读得到
`(wave=None, turn='6')`，四轮不动，因为**回合根本没交出去**——四次输入全是 `win_rate_auto_assign`，
一次提交都没有。离线问读者要计划，`begin_turn_plan` 给的是 `turn_start_not_present`。

原因在这一层的盘面：提交用的齿轮盘被自身轮毂剖成 `(1326,771,113,58)` 与 `(1341,799,88,79)` 两段，
都过不了圆盘面积门槛。我先试过把掩膜闭运算成整圆——那一帧确实读出来了，但同一判据把已知的暗色变体
（`window-20261007-184958/frame-1401`）也当成控件，两边亮度还几乎一致（中心 132.0 vs 134.7），
于是整段回退。

随后用点击实验定位：未分配时点齿轮盘只有动画，`Win Rate` 之后再点就把回合交了出去（TURN 6 → 攻击序列）。
这既证明盘就是提交控件，也说明"点亮/不点亮"不是判据。最终改法是 `dial_beside_caption()`：锚定`Win Rate`
说明，取其左侧、纵向跨度内的最大暖色块。全量 `1796 passed`，决策 D20 中英各一节。

## DSH iteration: the battle intents alternate instead of repeating (2026-10-22)

`packaged-mirror-20261022-022144` 到了 floor 3（此前最好 floor 2），13 次提交成功，但最后一场战斗卡住：
`TURN` 一直是 1，循环反复对齿轮盘 `[1340,800,86,79]` 发提交。原因是新回合开始时技能未分配，而盘只在分配后
才提交——所以每次都是空击，直到停滞守卫收局。

`window.py` 原来的顺序是"有盘就点盘"，没有记忆。现在 `plan_step` 接受 `battle_previous`，`runner` 用
`state['battle_previous']` 记住本回合上一次发的是提交还是分配：提交回来还是同一回合就改发 `Win Rate`，
分配之后再发提交；离开战斗页清空。判据见
`tests/test_battle_touch.py::test_a_turn_that_did_not_move_is_answered_with_the_auto_assignment_first`。

全量 `1797 passed`。决策 D21 中英各一节。

## DSH: operator constraints on what "clearing the Mirror Dungeon" means (2026-10-22)

用户 (m03811, verbatim): "我突然发现你用的是一队，而且是不是一个流血饰品都没有拿。。。你先专注nl，但是nl和成功通关一次一定要看这个，其实能够不靠你自己走到第5层最后一关就算通关了，因为视频不拿选结尾包乱选怎么都打不过镜牢的（"

三条约束记在这里，后续每一局都要对：

- **验收口径**：能靠脚本自己走到**第 5 层最后一关**即算通关；不要求打完关底。理由是结尾包（ending pack）与构筑选择决定成败，
  不按构筑打，关底怎么都过不去。
- **队伍**：目前真机跑的是**1 队**，目标是 2 队（用户长期要求"用 2 队打三次 Hard"）。
- **构筑/礼物**：目前**没有拿任何流血（bleed）类饰品**。礼物选择必须朝流血构筑走，而不是只按"当前最便宜的可得礼物"买。
  这条对 `src/maalimbus/floor_gifts.py` 与商店的价值模型都成立：价值模型要能表达"这件礼物属于本局正在走的构筑"，
  而不是只表达"这一格相对同排其它格更好"。

优先级：用户明确要求**先专注 NL**（地图检测模型的训练与规则对比），再回到真机通关。

## DSH: the detector is judged at conf 0.5, and by disagreement frames (2026-10-22)

`tools/compare_map_detector.py` now reads frames from `build/map-dataset/samples.jsonl` (the earlier version
walked `evidence/runtime` only and silently compared nothing), defaults to `--conf 0.5`, and renders the
worst disagreement frames with the rule in red and the detector in green.

Why 0.5: on the 2-epoch checkpoint the counts are 0.25 -> 1722 boxes / 646 matched / 47 agreeing frames,
0.5 -> 509 / 499 / 203, 0.7 -> 275 / 272 / 139. The 1722 is duplicate predictions on the same ring, not
wrong places: at 0.5 98% of the detector's boxes land on a rule box. Comparing below 0.5 measures the
duplication, not the reading.

The criterion stays behavioural: frames where the two disagree get adjudicated by eye and bucketed into
"model right / rule wrong" and "rule right / model wrong". One such frame is already decided
(`pi-20261012-180805/frame-0189`, floor 4): the rule boxed two modifier icons that carry no ring, the
detector boxed the single truly ringed node -- model right. That is one frame, not a verdict; the ratio
over all disagreement frames is what decides whether the detector may replace the rule.
## DSH continuation: what "通关" means, and the build it requires (2026-10-22)

用户给了验收口径与两条构筑约束，写进这里以免只活在对话里：

- **验收**：脚本自己走到第 5 层最后一关即算通关，不要求击杀最终 Boss 之后的所有流程。
- **队伍**：后续实机跑必须用**2 队**（当前跑的是 1 队）。
- **构筑**：礼物选择要朝**流血（bleed）**方向走；乱选结尾包、不拿齐构筑是打不过镜牢的。

这三点属于"跑得完"的前提，不是识别问题：识别只决定看不看得见，构筑决定打得过打不过。
后续在 `GIFT_PICK` 的取礼策略里加入按关键词的构筑偏好（流血优先），并在入口设置里固定选 2 队；
两处都要先用证据确认页面上能证明"这是流血类礼物"，再谈偏好，否则就是凭名字猜。

## DSH iteration: a label is written where the input goes out (2026-10-22)

Before the detector can be judged, the corpus has to be able to produce labels. Checking the
comparison from every angle showed no existing corpus can settle it: the 818-frame click corpus is
the set the 1280 detector trained on (train-set accuracy, 20.8% vs 11.9%); the exported held-out
split scores 100% for both rule and model because its labels *are* the rule's output; and the only
unseen run with clicks (`pi-20261021-185251`) is the run where the rule could not see the rings at
all (15 clicks, `gold_marks` finding one ring on `frame-0040`), so it scores 0/15 for both.

The blocker was a placement bug. `state['map_pending']` was recorded on the retry branch that runs
after a click failed, so a run whose clicks all worked wrote no `map_click_result` at all — 202
events, zero labels. `src/maalimbus/runner.py` now records the pending target immediately before
`self.device.click(*point)`, beside `window_intent`, so every map click is judged on the next
observation and a whole run can be held out.

Tests: full suite `1800 passed in 154.02s`. Wiki: decision D22 in both languages.


## D23 进战斗前那一页由它自己印的计数决定（2026-10-22）

地图上点敌节点后会先进一页人员选择：`Total Participants n / 12`，`n < 12` 时 `To Battle!` 是灰的。之前的循环走入这一页后不做任何事，于是 HUD 停在 `WAVE 0/10`、`TURN 1`，看起来像"战斗停滞"，实际是"队伍没选满"。

`src/maalimbus/party_vision.py` 只按这一页自己印的东西判断：`is_page()` 认 `Total Participants` 标签，`participants()` 收 `0/12` 与分开的 `0`、`12` 两种排版（读不出返回 None，不猜），`cards()` 给 6×2 十二个卡位，`to_battle()` 给走人按钮。

判据：`n < 12` 点卡，`n == 12` 只按 `To Battle!`。满员时卡面已从 `SELECTED` 变成 `BACKUP`，再点会把已上场的身份换下去——"满员不点卡"是正确性而不是优化。`runner.py` 在页面分派之前调用它，所以分类器还没命名的帧也会被回答。

## DSH iteration: a loop that is alive and no longer decides anything (2026-10-22)

`packaged-mirror-20261022-033911` was the first self-driven run that actually fought: it took the
board from `WAVE 2/10 TURN 3` to `WAVE 8/10 TURN 5`. Then its last event (`window_unknown_wait round
3`) was written at 07:41:23 and nothing followed for twenty minutes — with frames still arriving, so
`stall_watchdog` had nothing to fire on and `agent-stall.json` was never written.

`MirrorRunner` gained a second watch over progress instead of frames: `PROGRESS_SECONDS` (900s) over
`artifacts['event_heartbeat']`, which `note()` stamps. On trigger it writes `agent-no-progress.json`
(reason, `last_event`, `step`, `page`, `event_age_seconds`) and ends the process, so the driver can
record a failure that names a page.

Tests: `tests/test_stall_watch.py` 5 passed; full suite `1811 passed in 146.27s`. Wiki: D24 in both
languages.

## DSH iteration: an animation is waited out, an unreadable page still stops (2026-10-22)

`evidence/runtime/packaged-mirror-20261022-043142` (AdbShell input, 167 events) fought a
whole battle and then stopped as `page_unreadable_after_waiting`. The frames show the stop
was mis-booked: `frame-0069` is a skill's impact animation -- eight fragmentary OCR reads,
no control of any kind, and a different picture one frame later. The loop counted every
`UNKNOWN` frame into `unknown_seen`, so the animation spent the unreadable-page budget.

`looks_like_transition` (`src/maalimbus/runner.py`) now asks two things: no control word in
the frame's reads, and a frame that moved since the last unknown one. Both make a
transition -- waited out under its own bound (`window_transition_wait`), never charged to
`unknown_seen`. The same unnameable frame twice is still a page, and still stops the run.

Tests: `tests/test_runner.py::test_an_animation_that_moves_does_not_spend_the_unknown_budget`
plus the existing `::test_a_run_waits_out_an_unreadable_page_and_then_stops`, 58 passed.
Wiki: decision `D26` in both languages.

## DSH iteration: a battle submit the board ignored is now a fact, not a success (2026-10-22)

`advance` 默认 `False`，战斗提交意图又不传它，于是"点击被吞"的判定条件永远凑不齐；`expect` 里同时含 `BATTLE_HUD`/`BATTLE_PLANNING`/`UNKNOWN`，让"忽略"与"接受"在页面层面同形。实测 19 次 `battle_observed` 只推进到 turn 5、每回合约 43 秒，而全程没有任何 verdict 事件——这不是点击没送到，是"送到了却被忽略"压根没被观测。

现在以 HUD 的 `turn` 为唯一判据：同回合同一提交超 25 秒 -> `battle_submit_not_accepted`（带 `attempts`）；满 3 次 -> `battle_submit_ignored_repeatedly` 并清 `turn_wait_until`，把页面交还进度看门狗，让这一局以记录下来的原因进入恢复，而不是在同一回合上空转。判据为 `submit_was_ignored()`，6 条断言钉住语义；`tests/test_runner.py` 60 passed，全量 1815 passed。提交 `afc3551`、`6c90b07`、`8441649`；决策 `D27`（中英）。

## DSH iteration: a dot in the header deleted the map page (2026-10-22)

`evidence/runtime/packaged-mirror-20261022-045608` filled 32 of 36 `map_observed` events with `scene: UNKNOWN` and produced **zero** `map_click_result`. The frames were plainly the map; the header OCR on `frame-0006` read `Exploring·Floor` (U+00B7) instead of `Exploring Floor 3`, which `HEADER_LABEL_PATTERN` did not match, so `map_header` returned `None` and the agent left the page as `UNKNOWN`.

`normalise_header_text()` in `src/maalimbus/map_vision.py` folds the separator glyphs to a space before matching; `_folded_header` carries that text into `floor_label`. Folded, `frame-0006` yields `floor=None, pack='Sinking Pang'` — identity restored, no invented floor number. Tests: `tests/test_map_vision.py` gained the text case and a live-evidence case that skips without the frame. `56 passed`; full suite `1816 passed` (the one failure was the controller-lease test, correctly blocked by a running self-run holding the lease). Commit `42928ed`; decision `D28` in both languages.

## DSH iteration: the map's walkable edge is the bright one, and our node set is empty (2026-10-22)

Three adb taps on the four badged neighbours of `evidence/runtime/packaged-mirror-20261022-051350` were all inert, and the floor screenshot (`build/t94-now.png`) shows why: the party's node is the one with the orange hexagon outline, the walkable edges leaving it are bright cyan, and every node the loop offered hangs on a grey edge. The badge is reward information, not reachability.

`path_end`, `advance_candidates` and the `cyan_node` candidate kind already encode the cyan-edge rule, but each needs `node_markers`, which template-matches the crescent badge and returns 0 on this palette; feeding `path_end` the party located by `player_by_ring` still returns `None`. So the defect is a missing node set and a cyan-edge read that does not hold here -- not the ordering, the radius or the click point, all of which were tried and measured this round. Decision `D29` in both languages.

## DSH iteration: the walkable cyan edge is dark, and a straight sample cannot tell edges apart (2026-10-22)

Measured on `build/t94-now.png`: the cyan edges are `H≈95-98, S≈220-250, V≈13-55`, so a `V>=120` cyan mask matches zero pixels — one direct reason `path_end` returned `None` there. A +-5 px sample along the line from the party to each node scores 0.81-1.0 for all five nodes, because the background lattice is cyan too, so the discriminator must sample **that edge** narrowly and compare it against the floor's grey edges instead of the whole line. Appended to `D29`.

## DSH iteration: a floor is wider than the viewport (2026-10-22)

`Sinking Pang` 第 3 层停在 5/7 上反复失败：候选点击全 `rejected`，点自己也毫无反应，但暂停菜单一点就开（29 万像素变化）——输入通道正常，页面也不忙。

在实机上从队伍位置向外拖 400 ms：画面整体右移、右侧**冒出一批此前任何一帧都没有的节点**，队伍/层数/货币都不变（`build/t100-swipe-700.png` 对照 `build/t100-s0.png`，29 272 像素变化）。镜牢一层比一屏宽，而读取器只看当前视口，于是"没有可走节点"在视野不全时就是假的。

`RECOVERY_LADDER` 只覆盖纵向拖动，横向的"看不全"因此被读成"这页没路"。补上 `pan_left` / `pan_right`（`RECOVERY_PAN = (620, 540, 1300, 540)`，400 ms），排在纵向两档之后、`wait` 之前；四档都只移动视野、不按控件，因此对未知布局的页面仍安全。

测试：`tests/test_recovery_ladder.py` 现在要求四档各生效一次（纵向两档 + 横向两档），梯子用尽后仍然结束。全量 `1821 passed in 185.85s`。Wiki：决策 `D30`（中英各一节）。

边界：平移只让读取器**有机会**看全整层，不保证那一步可点；第 3 层那两步是否另有原因仍未证实。

## D32 implementation: the team the task setting names, and every system it is built around (2026-10-22)

决策记的是"礼物目标属于队伍，而不属于常量"，落地时有两处必须比决策写得更细。

**队伍来自任务设置，不是账本。** 第一版从 `user-run-ledger.json` 的 `active.team` 取槽位，那是**上一局留下的记录**。
玩家在 GUI 里点任务开始时，游戏按任务设置自己切队（`mirror_team_mode = single`、`mirror_single_team = 2`），
所以 `configured_slot()` 优先读这两项，只有 `rotation` 模式才回退到账本。runner 因此不需要持有队伍——它只需要知道
"任务设置说这局是几号位"。

**充震队不能被压成一个词。** 第一版取 `sorted(队伍体系)[0]`，等于又在"充"和"震"之间替玩家做了一次选择，跟写死
`bleed` 是同一类错误。现在 `systems()` 返回全部体系（`('charge','tremor')`），`gift_plan.wanted()` 接受以 `+` 连接
或直接传入的集合：先到先得、去重、全无序时回退 `default`。`from_active_team()` 保留单值语义，只给仍只吃单个关键词的
调用方用。

测试：`tests/test_team_gift_keyword.py` 8 条（含"任务设置优先于账本""rotation 仍跟账本""集合不丢体系"）、
`tests/test_gift_plan.py` 新增 3 条（多体系合并、跨体系重复只出现一次、未知体系回退默认），全量 `1832 passed`。

## DSH continuation: the graces page's control band clipped the button it pointed at (2026-10-22)

`packaged-mirror-20261022-072802` walked the whole entry chain (HOME -> DRIVE -> MIRROR_ENTRY ->
ENTRY_CONFIRM -> LEVEL_WARNING -> DUNGEON_TEAM -> STAR_GRACES) and then ended with
`unknown_or_bounded_transition_exhausted`. The graces page was recognised, a plan was produced and the
click was sent -- `window_intent page=STAR_GRACES target=[1740,986,102,42]` -- but the page never
changed.

The target came from `src/maalimbus/star_vision.py`'s `CONTROLS`, whose x band started at 0.88 while the
client draws that control column at x 0.79..0.91 (`evidence/runtime/packaged-mirror-20261022-072802/
frame-0020.png`). The band clipped the button's left half, so the reader returned a fragment -- it had
"found" the phrase and still pointed at empty board. That is the silent failure mode this project keeps
meeting: a constant measured on one client revision, which stops matching without raising.

The bands now cover the drawn column (`aa6edfd`, tests `-k "graces or star"` 77 passed, refrozen). The
next live run went further than any before: `packaged-mirror-20261022-073122` passed STAR_GRACES ->
STAR_CONFIRM -> PRE_BATTLE_TEAM (12 identity picks) -> MAP, and produced the first accepted map click of
the session (`accepted: the_click_opened_the_next_page`).

Two sampling mistakes belong in the record because they cost rounds. Reading an event journal while the
run is still growing produced two false "it hung" conclusions: once from confusing UTC event stamps with
elapsed local time, once from treating a 15-event snapshot as terminal while the process went on to 87
events. "Stalled" now requires all three: two samples at least `stall_seconds` apart with an unchanged
event count, a wall-clock gap over the limit, and no stall record.

## DSH continuation: a verdict now names its frame, and the party is read from its own torch (2026-10-22)

两条改动，各自带可验的判据。

**判定可回看**：`map_click_result` 的 `frame` 曾是恒 `None` 的死代码——
`getattr(self,'frames',None)` 取的是 journal 的属性，`Runner` 上没有。现在点击派发时把当前帧名
存进 `state['map_click_frame']`（`src/maalimbus/runner.py` 两个派发点），三条判定
（rejected / accepted / 无变化）统一 `state.pop('map_click_frame', None)` 取用；另外补了
"页面既未变化也未移动时仍记一条 `the_map_stayed_with_the_party_in_place`"，
避免意图被静默丢弃。真机验收：`evidence/runtime/packaged-mirror-20261022-075450` 388 事件、
13 条判定，**13/13 带帧名**，0 条 `None`，0 条静默丢弃。

**队伍位置**：`player_marker` 在直播帧上返回 `None`（`frame-0034`：队伍在 `(830,450)`，而
它只找到 6 枚徽章），于是循环无法只点相邻节点。新增 `map_vision.party_point(image)`，
用队伍自己的火把（两枚上下相邻的暖色高亮斑，`frame-0034` 上为 `(832,418)` area 56 与
`(826,461)` area 23）定位。验收：该局 14 个地图帧 **14/14** 读出，且相邻帧位移
`(829,440)→(826,561)` 与一格步幅一致。

同一轮里被自己数据否掉的三个假设也记在这里，免得下一轮重走：徽章点并不在节点上方空白
（`build/gt-node.png` 显示 `(1020,327)` 落在 `?` 六边格内，而"下移 106"落在格子下方空地）；
`GOLD_MARK_DROP` 改成 106 会让两条既有测试失败（两个页面的偏移不同，全局常量在结构上就是错的）；
用面积阈值取橙色边得到的是徽章图标（48×56），不是连线。检测器在 `frame-0034` 上输出的
四个中心 `(450,333) (833,333) (641,655) (449,653)` 与 `gold_marks` 重合——标签来自规则，
所以换模型不会改变几何，这一项要改的是**标注对象**，不是识别器。

仍未解决：10 分钟 13 次点击 0 次被接受，队伍停在第 1 层；点击点确实落在节点内、该节点也
确实连着亮边，所以下一个嫌疑是点击投递而不是识别。



## DSH continuation: map clicks are rejected only while the exploration is not resumed (2026-10-22)

这一条是**对照实验**得出的，不是推断。同一台设备、同一批候选、同一页面：

| 探索视图状态 | 点击结果 |
|---|---|
| 未恢复（`mirror_entry_preparation: a_run_is_still_in_progress`） | 9 次点击全部无反应（帧差 300–2000 px，仅动画） |
| 已恢复（入口 → Enter → `Dungeon Progress` → Resume） | 第一次点击即弹出节点面板 `Thick Rumbling Hum`（帧差 **107 860**），按 Enter 正常进入商店 |

因此在恢复后手动走了一步：`Floor 1 [HARD] 4/6` → 商店（`Super Shop 3%`，540 硬币，
Replace Ryōshū's Skill 77 / Green Spirit 146 / Barbed Lasso 187 / Deceptive Accord 148 / Phebotomy Pack 142）。

**结论（推翻此前三条记录）**：
- 「候选几何必然错约 170 px」不成立——同一批候选在恢复后命中；
- 「点击投递失败」不成立——恢复后同一次点击立即生效；
- 「地图不可交互」只在**未恢复**状态下成立，这是状态问题而非识别问题。

**连带解释**：那一局此前记录的 4/6 推进，是在视图可交互时走出来的；进程被杀后客户端退回未恢复态，
而循环仍按「读到 MAP 页就可以点」继续点击，于是产生了整段 `rejected`。

**上游修法（未实施）**：`a_run_is_still_in_progress` 现在只跳过设置应用
（`agent/recognition.py:1745-1748`），并没有要求先恢复探索。正确做法是把它当作先决条件：
在地图点击前确认探索已恢复（入口按下 Enter，出现 `Dungeon Progress` 时按 Resume），
而不是把「页面读作 MAP」等同于「可以点击」。

方法教训：判断「卡住/无响应」必须与状态对照（是否恢复、是否在结算），
单看帧差或点击次数会把状态问题误判成识别缺陷——本轮为此先后推翻了自己三条结论。


## DSH continuation: a refused map resumes before it clicks again (2026-10-22)

`80780b4` 把「连续三次被拒」从**命名**变成**动作**：runner 在 streak ≥ 3 时向 `plan_controls` 注入
`map.progress_button`，`window.plan_map` 据此返回恢复计划，不再点候选节点。

测试：`tests/test_window.py::test_a_map_that_refuses_every_click_offers_its_own_resume_control`
钉住两条——无该控件时仍走 `MAP_FORWARD_REASON`，有该控件时改为恢复计划且 target 就是该控件。
全量 `1839 passed`。

诚实标注：`MAP_PROGRESS_CONTROL` 由单帧目测得出，仅一个分辨率验证过；`Resume` 本身仍由后续帧处理，
本改动只负责把「再点一个节点」换成「打开进度控件」。


## DSH continuation: the resume chain now completes (2026-10-22)

`8e09153` 把恢复链补全。真机 `packaged-mirror-20261022-084358` 证明：streak 命名 → 恢复计划 →
点进度控件 → `DUNGEON_PROGRESS` 全部按预期发生，只剩最后一环 `continue_button_not_anchored`。
根因是分支早就有、锚点没人绑。runner 现在从本帧 OCR 绑定 `continue` 行，`Forfeit` 不绑。

测试：`tests/test_window.py::test_the_progress_panel_resumes_and_never_offers_another_control`。
全量 `1840 passed`。


## DSH continuation: candidates are filtered by adjacency (2026-10-22)

`9cd9de9` 加 `map_vision.adjacent_to`（距离带 150–430 px），并在 `runner.candidates_of` 里应用。
此前候选只排序不筛选，循环点的都是两格外的节点，所以 `rejected` 全部属实、队伍不动。
测试：`tests/test_map_vision.py` 新增三条用例；全量 `1842 passed`。


## DSH continuation: no party reading, no click (2026-10-22)

`53cb40e` 把 `party_point` 的带宽从 0.79 改到 0.95（东侧队伍在 x≈1628，旧带外），`1d0c921` 让
`candidates_of` 在读不到队伍时返回空候选。此前两者叠加使相邻约束从未生效，一局烧掉 6 次点击。
测试：`tests/test_runner.py` 契约测试改为"无队伍则无候选"。


## DSH continuation: a suspended exploration is re-entered from the entry (2026-10-23)

`packaged-mirror-20261023-050219` attached to a run already in progress
(`mirror_entry_preparation: a_run_is_still_in_progress`), and its first six node clicks were refused. The pause
panel's Continue was offered as the recovery and only closed the panel: `party_point` reads `(1628,562)` across
`frame-0006`..`frame-0041` (three clicks, frame diffs 611..6020), while the panel's own OCR prints
`Progress / Forfeit / Continue / Window / Config` and no `Resume` at all. The resume that works lives on the
entry's progress dialog (`Resume / Halt Exploration / Cancel`).

`src/maalimbus/runner.py` now also binds `dungeon_progress.resume_button` (OCR `resume`) and
`dungeon_progress.window_button` (OCR ending `window`), and raises `dungeon_progress.resume_via_entry` once
`map_refused_streak >= 3`. `src/maalimbus/window.py`'s `DUNGEON_PROGRESS` branch uses that flag to prefer Resume,
then the window control, and only falls back to Continue when the flag is absent -- so a normally paused run is
still left with a single click.

Tests: `tests/test_window.py::test_a_suspended_exploration_is_reentered_through_the_entry_not_continued`
(85 passed in that file). Commits `83ee06b`, `050d7e0`. Live counterpart of the claim is still owed.

## DSH continuation: one class for "the control is not in the frame" (2026-10-23)

架构审计的三个病因里，第一个被测量钉死了：窗口层 77 条拒绝理由中有 **52 条**是同一个机制（缺控件）被逐页命名，
外加两条用别的拼写说同一件事。这把"缺一个按钮"变成了 52 个各自为政的结局，任何调用方都无法对整类作出反应。

`src/maalimbus/anchor.py` 收口这一类：`anchor_of()` 解出缺失控件，`classify_refusal()` 给出
`stop_kind`（`anchor_missing` / `page_unreadable` / `held`）与 `anchor`、`anchor_page`；
`window._refuse()` 是唯一出口且理由原文不变，所以账本与既有断言不受影响。守卫测试扫描 `window.py` 里
每个 `_refuse(...)` 字面量，新增未声明的非锚定类拒绝即失败（提交 `6feb00e`，D34）。

分类之后是行为：`anchor.reread_allowed()` 把"能不能再看一眼"写成一条规则——没有发出输入、不是策略性拒绝、
不是 observe-only、且未用尽 `page_tries` 时，锚定缺失花一次有界重读而不是结束本局（`5682381`）。
`window_page_retry` 现在带 `anchor` 字段。

证据：`tests/test_anchor.py` 17 passed（正例/反例/别名/守卫/边界），与 `test_window.py`、`test_runner.py`
合跑 164 passed in 40.02s。未验证：这一类在真机上的实际停窗率变化——本轮没有任何实机输入，未启动游戏、
未消费资源、未领取奖励。

## DSH iteration: a refusal's kind now decides which rungs may be spent (2026-10-23)

第三批结构偿还。`src/maalimbus/pages.py` 里 `REFUSALS` 把 77 条拒绝理由收成六类，六类各对应一个
动作（`bind_control` / `pan_view` / `escalate_ladder` / `reread_text` / `recompute_state` / `stop`），
`recovery_for()` 把类别翻成动作，`ladder_for(action, ladder)` 再把动作翻成**可花的手势子集**。

这条链的验收写作两句话：**动作只能缩窄手势集，不能发明手势**；**未知动作回落到实测过的六级梯子**，
而不是凭“看起来更安全”临时编一个。实测依据是恢复梯子换代时反复出现过的那类事故——在确认框上拖拽
会把一次可恢复的停顿变成走错页，而平移、缩放至今没有破坏过任何一局。

同时修掉了一个测试假坏：`tests/test_recovery_ladder.py` 用的「地图后跟意外后继」夹具从未进入
恢复路径，所以它用 `swipes == 1` 报出的是“什么都没发生”，不是“梯子错了”。现在夹具走真实的
拒绝通道，断言恢复为 `pinches == 1 && swipes == 4`。

测试：`tests/test_refuse_vocabulary.py` 5 passed（含类别↔动作一一对应、动作只缩窄两例），
`tests/test_recovery_ladder.py` 7 passed，全量 `1903 passed`。

## DSH continuation: 相邻性判定不再是常量，而是本帧格距（2026-10-23）

`fa899fa` 把地图候选的相邻判定从"常量半径"改成"本帧自身格距"。判据不是推理，是已落盘事件复算出来的：
`map_click_result.target` 的中心与同帧 `party_point` 的距离——一步是 219–245 px，两步是 386–396 px，而
**所有 `accepted` 的唯一坐标恒为 (1844,60)，那是右上齿轮，不是节点**，所以 `accepted` 计数此前是被污染的。

同一偏移 (381,106) 在 219 px 格距的图上是一步、在 396 px 格距的图上是两步；`far=430` 与 `STEP_CENTRES`
都会在一半地图上判错，且 `map_vision.py` 里历史上已存在两份同名 `adjacent_to`（后一份遮蔽前一份），
这就是同类 bug 以两种形态复发的原因。

实现：`pitch_of(party, boxes)` 分轴估计格距（≥2 个框共识才算数，否则返回 `None`），`adjacent_to` 以
`{(across,down),(across,0),(0,down)}` 的 `tolerance` 邻域判定；`None` 是"本帧不可证明"，退回旧带并记录，
不猜。锁定行为的断言是"同一输入在不同格距下结论相反"（`tests/test_map_vision.py`）。

遗留：`recovery_advanced` 仍为 6/17，须在受控实机跑里复测；本轮 0 次实机输入、0 消费。

