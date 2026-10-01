# OCR model provenance

These are the `ppocr_v6/small` pre-converted ONNX assets from
[`MaaXYZ/MaaCommonAssets`](https://github.com/MaaXYZ/MaaCommonAssets), pinned at
commit `dabcd4681ac990dc4361de26416d986abd80e4aa` on 2026-09-03. MaaFramework's
official quick-start recommends MaaCommonAssets for ready-to-use OCR models.

The upstream conversion identifies the source models as
`PP-OCRv6_small_det` and `PP-OCRv6_small_rec` from PaddleOCR. They support
Simplified Chinese, Traditional Chinese, English, Japanese and the documented
Latin-script languages.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `det.onnx` | 9,893,172 | `66c0f34caaf432553710fd9973a7134d8cf924db7109310c3d2562dcc39b209d` |
| `rec.onnx` | 21,146,753 | `7dcf6298d77d2a6eb44c1ebeed990826ca895a9c68d955a3eace00763d052949` |
| `keys.txt` | 93,655 | `769e7fa79bb297b5f18d8dbd149e364a45bc61f2b3f574e5ea836f0b261c23a6` |

MaaCommonAssets is MIT licensed. PaddleOCR is Apache-2.0 licensed. Exact
license texts are retained under `THIRD_PARTY_NOTICES/` at the project root.
