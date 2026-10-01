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
