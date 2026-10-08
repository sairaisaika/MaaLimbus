# Source and license provenance

MaaLimbus-owned code declares AGPL-3.0-or-later in the root `LICENSE`.
This is a project choice, not MaaFramework's license or an application-license
requirement imposed by MaaFramework. Third-party material keeps its original
terms; the root's `or-later` designation does not extend third-party permissions.

- MaaFramework `cc5fef675f42ca899e12bc4932ff37ac1278853c`: development/API guidance;
  the unmodified 5.12.2 native runtime in the local development package is LGPL-3.0.
  Original [license text](MaaFramework-LGPL-3.0.md), verified against
  [upstream LICENSE.md](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/LICENSE.md).
  The incorporated [GPL v3 text](GPL-3.0.txt) is retained from
  [GNU](https://www.gnu.org/licenses/gpl-3.0.txt).
  The v5.12.2 runtime's actual release commit is
  `f625a60edeccd4549f9a71c0f74628d827ade8fb`; the candidate package also includes
  its pinned source archive in `sources/MaaFramework-v5.12.2-source.zip`.
  Its LICENSE matches the retained notice. This does not claim the separate
  native dependency source/notices audit is complete.
- MXU 2.7.1, `9fa8cc51e8ff8cd89d99f3ea55fe3a7a82e6ede3`: unmodified
  Windows desktop executable; [original AGPL notice](MXU-AGPL-3.0.txt).
  The cached corresponding source archive accompanies the local development
  package in `sources/MXU-v2.7.1-source.zip`; package metadata identifies its hash.
  Desktop UI acceptance remains pending.
- LixAssistantLimbusCompany `431b432e22f0b0da08b95d7c478fa213be20b3e8`:
  AGPL-3.0, audited saved-team, gift, dungeon and deployment semantics.
  Native policies do not import its input/recognition runtime.
  Cropped gift icons/keyword groups are imported from
  `lalc_backend/img/general/ego_gifts` into `assets/resource/base/image/gifts`.
  `gift-catalog.json` retains each source path, SHA256, keyword and pinned revision.
  Five small fixed theme-page UI glyphs and 95 reference names are imported into
  `image/themes` / `theme-catalog.json`, with hashes, source paths and revision.
  Theme card artwork is not imported. Original reference weights are provenance
  only; active defaults remain neutral unless the team config overrides them.
  This includes game artwork originating in the reference project; it does not
  assert that MaaLimbus owns the artwork or that upstream provenance establishes
  the game rights holder's redistribution permission. That scope remains to be
  checked before public distribution. No account screenshots are imported.
- MaaCommonAssets `dabcd4681ac990dc4361de26416d986abd80e4aa`: MIT, packaged
  `ppocr_v6_small` detector/recognizer/key resources from its OCR model bundle.
- PaddleOCR: Apache-2.0, underlying OCR implementation/model provenance retained
  with the MaaCommonAssets model README in `assets/resource/base/model/ocr`.

Corresponding license texts are included alongside this notice. No user account
screenshots or private configuration are part of this distribution.
This source inventory does not establish that the unfinished Windows package
meets all distribution requirements. See the
[README/license reference comparison](../docs/readme-license-reference.md).
