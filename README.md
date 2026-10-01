# MaaLimbus

MaaFramework automation for the native Windows edition of Limbus Company.
English and Japanese resource packs, ProjectInterface V2 and a Python Agent.

**Under development. Hard Mirror Dungeon five-floor clears are not yet verified.**
The priority is five floors → verified rewards → rotate saved teams → repeat.

Implemented foundations:

- Native Win32 capture, process identity and privilege checks before input.
- Stable local menu labels and normalized positions, independent of dungeon covers.
- Maa-owned clicks/swipes, bounded retries and randomized delays within finite ranges.
- Saved-team library selection with a fresh title/row postcondition. This is distinct
  from dungeon deployment; edited team names are matched literally.
- Atomic private team profiles, deployment order validation, durable run evidence
  and rotation only after all five floors, victory, reward receipt and entry return.
- Team-aware floor-gift OCR/icon candidates with retained ranking evidence,
  separate enemy-buff ranking and opt-in resource budgets. Actual acquisition
  confirmation and next-floor integration remain pending.
- GitHub Release metadata checks with ETag caching and persisted rate-limit deadlines.

See [design](docs/design.md) and [acceptance evidence](docs/acceptance.md) for the
remaining dungeon, deployment, battle, rewards, desktop packaging and updater work.

## Local development

Python 3.11+; public MaaFramework 5.12.2 binaries and the documented OCR assets.

```powershell
python -m pip install -e '.[dev]'
python -m pytest -q
python tools/check_update.py
```

The prepared ProjectInterface is `assets/interface.json`. `tools/run_native.py`
uses one locked controller and a session of at most one hour. It refuses lower-privilege
input to an elevated game. Maa and Steam/game must have matching privileges;
the application does not elevate itself or restart Steam without user action.

Saved-frame checks use the actual Maa parser, OCR and production Pipeline:

```powershell
python tools/verify_native_replay.py --binary <Maa-library-directory> --references <reference-directory>
python tools/verify_team_replay.py --binary <Maa-library-directory> --frame <team-library-frame>
python tools/verify_gift_replay.py --binary <Maa-library-directory>
```

These checks construct no game controller. Derived title/cover changes are explicitly
marked and do not establish real team deployment or a completed dungeon run.
Private profiles, account frames, logs and runtime evidence are ignored by Git.

## 日本語

Windows 版 Limbus Company 向けの MaaFramework 自動操作ツールです。開発中で、
ハード鏡ダンジョンの5階クリアはまだ実機で確認していません。
安定した文字と位置を利用し、保存チームの選択後にタイトルを確認します。
不明な画面、敗北、未設定の資源消費では証拠を保存して停止します。

## License and sources

AGPL-3.0-or-later. LALC choice/workflow semantics were audited and reimplemented
as Maa-native components; its controller/runtime is not embedded.
MaaFramework and OCR components retain their own licenses in
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES/README.md).
