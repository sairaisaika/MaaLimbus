---
type: Project
title: MaaLimbus
tags: [project, maaframework, windows-native, limbus-company, mirror-dungeon]
---
# MaaLimbus

MaaFramework Win32 controller + ProjectInterface V2 + MXU + Python Agent.
Goal: Hard Mirror Dungeon floors 1–5, verified rewards, saved-team rotation and repeat;
then budgeted Enkephalin conversion/refill, mail and daily missions. English/Japanese.

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
