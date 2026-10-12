# Maa-native sinner detection and Mirror learning implementation

## Contract and architecture

October11 clarification: **box means the account's owned identities**, opened
by clicking each sinner. Detector bounding boxes are supporting vision only.
The finishing priorities are a revisioned full identity index / owned-inventory
reconciliation, and evidence-backed Mirror self-label / learning. A public index
never marks an identity owned; an incomplete account scan never marks it absent.

Identity records use game personality ID as key, with independent EN/JP/ZH titles,
source revision/hash, and nullable missing keyword/skill facts. The retained
localization currently yields184 playable IDs; the old statics yield128 facts.
The initial184 snapshot is superseded by a normal browser read of HuiJi revision
145235:189 playable IDs, all189 EN/ZH aliases, five JP aliases pending. The Wiki
Buffchoose.tabx revision145587 contributes188 explicit system flag rows, with
empty fields preserved as unknown and one identity's systems absent. Attribution
and CC BY-SA4.0 provenance are retained. Direct raw HTTP403 is distinct from the
successful rendered public table extraction; no search snippet became raw data.
Wiki-revision ID completeness is separate from live-game/account completeness.

MuMu ownership collection uses native Maa OCR and native TemplateMatch for the
Owned checked / ALL unchecked controls, a unique sinner header and hash-bound
navigation intent. Sidebar filters only change the viewed sinner. Ordinary click
opens the gallery; holding a library card opens its details. Known guide/detail
return arrows are native-matched and closed once. Every observed card retains
its OCR tokens and source image; exact normalized title matching only, unknown
or low-confidence rows remain unresolved. Level/uptie stay null if unproven.
End-of-list coverage and all12 sinners are required before full inventory claims.

Implementation order:
1. Refresh and version the whole ID catalogue, fill missing aliases/facts and
   compare with current Wiki inventory. Reject NPCs/duplicate IDs.
2. Scan twelve owned galleries, support bounded scrolling and independent end
   detection, reconcile exact aliases, retain unresolved rows and account hashes.
3. Feed independently verified page/card outcomes to the correction queue;
   train/export/evaluate ONNX offline, then replay via Maa native recognizers.
4. Learn Mirror rankings from complete verified outcome episodes, measure HP,
   time and expenses, and compare held-out policies before any promotion.
Completion requires a real full inventory round trip and a trained/evaluated
native model; current protocol tests or progression90 alone do not satisfy it.

Pinned runtime: MaaFramework5.12.2, ProjectInterfaceV2, Python Agent and MXU.
Maa provides inference; it does not itself automatically train or approve labels.
Use its YOLOv8/YOLO11 ONNX protocol, `model/detect`, zero-based `expected`
indices and native `run_recognition_direct`. Training dependencies are offline
tools only, never a second gameplay controller or a Python inference replacement.

References:
- [Pinned protocol](https://github.com/MaaXYZ/MaaFramework/blob/f625a60edeccd4549f9a71c0f74628d827ade8fb/docs/en_us/3.1-PipelineProtocol.md)
- [Official detection recipe](https://github.com/MaaXYZ/MaaNeuralNetworkCookbook/tree/main/NeuralNetworkDetect)
- [Wiki sinners](https://limbuscompany.huijiwiki.com/wiki/罪人)
- [Wiki current-season reference](https://limbuscompany.huijiwiki.com/wiki/名与蛛之镜)

```mermaid
flowchart LR
  A[Maa capture and native detection] --> B[Hash-bound box proposals]
  B --> C[Review and independent teacher evidence]
  C --> D[Episode-split YOLO dataset]
  D --> E[Offline YOLO training and ONNX export]
  E --> F[Held-out evaluation and Maa native replay]
  F --> G[Read-only shadow recognition]
  G --> B
  A --> H[Verified Mirror outcome and scoring]
  H --> I[Offline strategy comparison]
```

## Stages and acceptance

| Stage | Implementation | Acceptance / real-device boundary |
|---|---|---|
|1 offline foundation|12 stable sinner classes, box validation, proposal queue, episode deduplication, YOLO export, explicit run progression score, Wiki provenance|Tests/retained-frame audit; no trained-model claim|
|2 data collection|Maa native template/OCR teachers or reviewed card boxes; uncertain NN boxes remain proposals; correction creates a new review|**MuMu required**: English/Japanese card selection, party details and battle HUD; identities/skins/scales/occlusion and negatives|
|3 train/export|Official YOLO11n workflow, fixed seed, opset17 ONNX, raw pre-NMS output, hashes and split manifest|Every class represented in train/validation/test by independent episodes; no adjacent-frame leakage|
|4 evaluate/shadow|Native Maa replay of held-out images, per-class precision/recall/IoU, unknown/background tests, speed, drift queue|**MuMu required**: read-only shadow, same single controller; no model-generated click|
|5 controlled integration|Replace fixed deployment boxes only after model/native replay and fresh identity agreement; retain count/order/intent/successor gates|**MuMu required**: bounded deployment with selected ordinal proof; budget and pending transactions unchanged|
|6 strategy learning|Gift/theme/trial candidate rankings plus outcome, team/system/HP/time/resource coverage; offline comparison with current heuristics|Multiple independent runs; distinguish prediction from causal gift benefit, real payout from victory|

## Labels and self-label policy

The box target is the **visible sinner card/unit**, not a fixed grid cell or OCR
text box. Class order is storage.SINNERS; Sinclair class9 is game sinner11,
Outis class10/game12, Gregor class11/game13. Dante is not a detector class.
Missing/occluded objects are not filled in from slot coordinates. Keep duplicates
and conflicting class predictions in the correction queue, not the training set.

Automatic labels are proposals. Promotion requires a hash-bound review of the
actual visible card boundary and identity, or separately audited native teachers.
A model cannot certify its own prediction. Validation/test reviews are independent
of that model. Duplicate images across episodes/splits refuse. Complete negative
frames need explicit review; partial labels cannot be silently treated as negatives.
Readiness is a coverage gate, not proof of good accuracy. Model promotion is separate
and remains disabled until native replay and real-device shadow are verified.

## Wiki data and scoring

Wiki names/effects/recipes are revisioned background facts, never screen truth,
owned inventory, current resource cost or reward proof. Keep URL, retrieval method,
revision if available and content hash. On October11 the public raw JSON request
returned403; search-index metadata is explicitly distinguished from API data.
Do not bypass access restrictions or infer current costs from the old 湖之镜 page.
Raw exports stay in build; normalized facts require review before policy use.

Run progression score v1 is70*verified floors/5 +20*verified victory +10*verified
reward. It measures completion only. Efficiency/survival/gift utility scores stay
unknown without measured HP/time/cost; missing data is not zero loss. Incomplete
or unpaid runs are censored outcomes and cannot become positive strategy targets.
Score calculation is read-only and does not update the run ledger or rotation.

## Immediate MuMu request when stage1 passes

Ask the user to open **Limbus**, identify EN/JP, and leave the party/card page
visible. First collect read-only screenshots. Ask before game navigation if the
current unpaid run would be disturbed; never touch FGO or replay old claims.
Need at least three independent sessions per split and20 reviewed instances per
class/split as the initial collection target, plus reviewed negatives. Final model
quality is decided by held-out metrics, not that count alone.

## Research training and continuous runtime evidence

Production coverage targets above do not prohibit an explicitly labelled research
fit. `autolabel_owned_gallery_research.py` binds each gallery to its native unique
sinner header and Owned/ALL template results. It measures four visible card-border
strips before cropping actual pixels; every crop retains original JSON/PNG hashes,
crop coordinates and the collection-proof hash. All twelve pages in one collection
remain one episode. These labels are research-only, never production review.
`autolabel_sinner_retained.py` additionally checks native sinner-emblem matches on
retained pre-battle pages, binding each page's episode to its actual run result.
Ambiguous emblem matches and unproven borders are excluded, not filled from slots.

`train_sinner_detector.py --research --execute` permits actual incomplete reviewed
data. With no validation episode, optimization diagnostics may reuse training
images, explicitly marked `fit_validation_uses_training_images`; they are not
held-out accuracy. Real exported ONNX hashes and actual available val/test metrics
are retained. `evaluate_sinner_detector_native.py --research --research-fit` replays
training images through Maa's `NeuralNetworkDetect` with a no-input offline
controller, expressly unable to pass production quality. Ordinary evaluation
requires every validation/test frame exactly once and counts unmatched/duplicate
boxes as errors; missing classes or negatives cannot pass.

`prepare_sinner_shadow.py` creates a new isolated resource, binding actual training,
ONNX bytes, class order and native replay. It never replaces installed resources or
enables input. The runtime shadow refuses changed/missing model cards and native
evaluation files. A research model may run as untrusted shadow and reports its
quality gate separately. `semantic_labels.persist_frame_proposals` is the Mirror
observer hook: it queues hash-bound current-frame predictions and native semantic
observations continuously, without altering account/run/budget state or certifying
the model's own predictions. Corrections and independent held-out reviews remain
required for promotion. Maa inference protocol reference remains the official
[NeuralNetworkDetect documentation](https://maafw.com/en/docs/3.1-PipelineProtocol/).
