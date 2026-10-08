# Native model recognition for Mirror Dungeon

Runtime target: MaaFramework5.12.2, MXU ProjectInterface2, one Maa controller.
The model proposes observations; MirrorRunner validates pages, budgets, successors
and receipts. It does not issue input or determine that a dungeon was cleared.

## Appropriate learned observations

| Observation | Native Maa recognition | Evidence needed before use |
| --- | --- | --- |
| Highlighted/disabled UI control in a known ROI | NeuralNetworkClassify | Label order, held-out screenshots from different sessions, false-positive counts |
| Map nodes at changing locations | NeuralNetworkDetect | Annotated boxes and node classes, visible path/current-position evidence |
| Owned identity keyword and level | OCR plus identity evidence | Filter/sort proof and complete candidate inventory |
| Gift keyword/value ranking | Pure policy after OCR/visual identity | Saved build and current gift effects, no stale seasonal art assumptions |

Classify loads ONNX below `model/classify`; Detect loads compatible YOLO ONNX below
`model/detect`. Labels must match the model output. Current shipped resources contain
OCR det/rec models only: no trained map classifier/detector has been accepted.
Do not create a fake ONNX model or relabel a template matcher as machine learning.

Pinned Lix431b432 provides examples of map legend/path models. Its path classifier
uses preprocessed highlighted option regions rather than arbitrary map-node boxes;
the existing comparison shows these coordinates do not identify our retained map.
Reuse requires input/output/preprocessing compatibility evidence, not file copying.

## Acceptance and integration

Retain each screenshot and its hash, game locale, floor and session identifier.
Separate train/validation/test by whole session and UI version, so adjacent frames
cannot leak between sets. Include tutorial, modal, hidden, disabled, changed-art
and unknown-node negatives. Record confusion matrices and unsafe false positives;
a chosen threshold needs measured justification. Low-confidence/conflicting
observations remain UNKNOWN and preserve evidence.

First replay model inference through Maa with a CustomController that intercepts
all input. Compare predicted boxes with independently annotated boxes. Then run a
bounded live observation-only trial. Enable one native simulated touch only after
independent page/control evidence agrees. Compare the actual successor screenshot;
model confidence, task_succeeded and click success never replace floor/reward proof.

Keep the shared MirrorRunner and native context controller as the CLI/MXU seam.
Model inference belongs in recognition, saved builds and route/gift ranking in pure
policy, budgets and ordered receipts in RunStore, package/update verification in
the existing release client. No Lix runtime or second controller is introduced.

Official versioned protocol checked October8:
https://github.com/MaaXYZ/MaaFramework/blob/v5.12.2/docs/en_us/3.1-PipelineProtocol.md
Local source: `sources/upstream/MaaFramework/docs/zh_cn/3.1-任务流水线协议.md`,
NeuralNetworkClassify/NeuralNetworkDetect sections. These requirements are a plan;
trained-model and live full-loop acceptance remain incomplete.
