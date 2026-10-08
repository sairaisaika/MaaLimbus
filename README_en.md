<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# MaaLimbus

<img src="assets/misc/Don-Quixote.png" width="160" alt="MaaLimbus Don Quixote" />

A native Windows Limbus Company automation learning project powered by MaaFramework.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows_x64-blueviolet)
![MaaFramework](https://img.shields.io/badge/MaaFramework-5.12.2-blue)
![Pipeline](https://img.shields.io/badge/Pipeline-ProjectInterface_V2-876f69)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](LICENSE)
![Status](https://img.shields.io/badge/status-in_development-orange)

[English](README_en.md) | [简体中文](README.md)

</div>

## Introduction

MaaLimbus uses the MaaFramework Win32 controller, Pipeline and Python Agent with English and Japanese resources. A native MXU development app is installed. Actual MuMu ADB evidence proves one English Hard five-floor run, paid rewards, saved-team rotation and reentry; Windows game input and Japanese live operation remain open.

The priority is **five Hard Mirror Dungeon floors → verified rewards → saved-team rotation → repeat**. This chain has real MuMu evidence. Unknown pages still retain evidence and stop; arbitrary teams, game updates and prolonged unattended farming remain unverified.

Recognition uses local text, stable icons and positions rather than variable dungeon covers. Clicks stay inside target boxes and delays vary within finite bounds; transitions require recognized postconditions.

## Get started

> [!IMPORTANT]
> Development source and a local development package are available; a fully live-verified release is not. Startup, task success and offline tests do not establish dungeon completion.

On Windows with Python 3.11+ and MaaFramework 5.12.2 native libraries:

```powershell
git clone https://github.com/sairaisaika/MaaLimbus.git
cd MaaLimbus
python -m pip install -e '.[dev]'
python -m pytest -q
```

Read the [design](docs/design.md) and [acceptance evidence](docs/acceptance.md).

| Feature | Verified scope | Remaining work |
| --- | --- | --- |
| Native control | MuMu Maa simulated touch, bounded random delay and shared controller gate | Windows live game input, Japanese E2E |
| Tasks and builds | Six MXU entries, global builds and Mirror single/rotation modes | Complete saved-editor restart and GUI Start dispatch |
| Hard Mirror | Real five floors, named gift receipts, paid payout, Team2 to Team7 reentry | Shops/fusion, arbitrary layouts and prolonged unattended runs |
| Battle and packs | Native WinRate/START touch, independent Hard/title gates and bounded drag | Full clash/strategy policies and Japanese |
| Experience / thread | Independent entries referencing saved builds | Stage, spending and battle flows; currently capture and stop |
| Conversion / daily rewards | Entries and budget foundations | Actual actions and receipts; currently capture and stop |
| GitHub updates | Desktop startup check, persistent limits, validation, configuration-preserving install/rollback | New public version download and visible version restart |
| Learning | Reviewed hashes and episode-separated data preparation | Only two samples; model training and enablement not completed |

A bounded development session requests standard Windows UAC consent:

```powershell
./tools/start_native.ps1 -Binary <Maa-library-directory> -Locale en -Seconds 180
```

The launcher cannot approve consent. Cancellation starts no controller. Game/controller privileges must match. Sessions last at most one hour; the current Pipeline stops with evidence at unimplemented pages. Launch records are in `build/native-launch*.json`, logs in `build/native-live.*.log`, and evidence in `evidence/runtime/`. Redact account details before sharing.

## Statements and licenses

### Open-source license

MaaLimbus-owned code currently declares [AGPL-3.0-or-later](LICENSE). This was a project choice, not a MaaFramework requirement and not its license.

MaaFramework uses [LGPL-3.0](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/LICENSE.md). Its [LGPL text](THIRD_PARTY_NOTICES/MaaFramework-LGPL-3.0.md) and incorporated [GPL text](THIRD_PARTY_NOTICES/GPL-3.0.txt) are retained. Lix-sourced gift icons/catalog/reference material retain their AGPL-3.0 designation. The root license does not relicense third-party material.

See the [source/license inventory](THIRD_PARTY_NOTICES/README.md) and [reference comparison](docs/readme-license-reference.md). Replacing the root license cannot turn existing Lix material into LGPL material.

### Distribution

Dependencies retain their own licenses. Future packages need license texts, source revisions, build instructions and applicable corresponding source; no such package has been released. Game artwork belongs to its rights holders. Lix provenance does not establish permission to relicense that artwork; distribution rights remain to be checked. Private frames, configuration and runtime evidence are excluded from releases.

### Use

This learning project is provided as stated in its license, without promised runtime results. Check the target software's terms and authorizations. It does not inject into the game, read game memory or bypass privilege/security controls.

## Development

The project consumes official Python objects and Jobs. Maa owns screenshots/input/Pipeline scheduling; the Agent supplies recognition/decisions, while pure Python policies run offline.

- [Quick start](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/en_us/1.1-QuickStarted.md)
- [Binding/interface design](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/4.2-标准化接口设计.md)
- [Framework build guide](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/4.1-构建指南.md): for compiling Maa itself. This application consumes public native libraries.

Actual Maa replay checks create no game controller:

```powershell
python tools/verify_native_replay.py --binary <Maa-library-directory> --references <reference-directory>
python tools/verify_team_replay.py --binary <Maa-library-directory> --frame <team-library-frame>
python tools/verify_gift_replay.py --binary <Maa-library-directory>
python tools/verify_theme_replay.py --binary <Maa-library-directory>
python tools/verify_deployment_replay.py --binary <Maa-library-directory>
```

Resource parsing does not prove Japanese live-flow coverage. Derived cover/title changes are marked separately.

See [Windows packaging](docs/windows-package.md) for building and replaying the packaged Agent over Maa IPC. The builder creates a fresh local directory; it does not launch the desktop client, request UAC, replace an installation or publish a Release.

## Acknowledgements

- [MaaFramework](https://github.com/MaaXYZ/MaaFramework): controllers, recognition, Pipeline and Python interfaces.
- [MXU](https://github.com/MistEO/MXU): unmodified ProjectInterface desktop client in the development package; UI acceptance pending.
- [LixAssistantLimbusCompany](https://github.com/HSLix/LixAssistantLimbusCompany): workflow/team/gift references and attributed assets; its controller is not embedded.
- [MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets) and [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR): OCR resources and notices.

## Communication

Report issues via [Issues](https://github.com/sairaisaika/MaaLimbus/issues), including game language, the stopped page and redacted terminal logs. Actual acceptance evidence determines feature status.
