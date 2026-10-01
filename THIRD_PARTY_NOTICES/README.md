# Source and license provenance

- MaaFramework `cc5fef675f42ca899e12bc4932ff37ac1278853c`: development/API guidance;
  the native runtime is separately distributed under LGPL-3.0.
- LixAssistantLimbusCompany `431b432e22f0b0da08b95d7c478fa213be20b3e8`:
  AGPL-3.0, audited saved-team, gift, dungeon and deployment semantics.
  Native policies do not import its input/recognition runtime.
  Cropped gift icons/keyword groups are imported from
  `lalc_backend/img/general/ego_gifts` into `assets/resource/base/image/gifts`.
  `gift-catalog.json` retains each source path, SHA256, keyword and pinned revision.
  This includes game artwork originating in the reference project; it does not
  assert that MaaLimbus owns the artwork. No account screenshots are imported.
- MaaCommonAssets `dabcd4681ac990dc4361de26416d986abd80e4aa`: MIT, packaged
  `ppocr_v6_small` detector/recognizer/key resources from its OCR model bundle.
- PaddleOCR: Apache-2.0, underlying OCR implementation/model provenance retained
  with the MaaCommonAssets model README in `assets/resource/base/model/ocr`.

Corresponding license texts are included alongside this notice. No user account
screenshots or private configuration are part of this distribution.
