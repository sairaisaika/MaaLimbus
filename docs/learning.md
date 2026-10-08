# Native learning in Mirror Dungeon

MaaFramework supports ONNX `NeuralNetworkClassify` for fixed page regions and
`NeuralNetworkDetect` for object boxes. The runtime remains Maa Pipeline + Agent;
learning does not create another device controller. See the official
[Pipeline protocol](https://maafw.com/en/docs/3.1-PipelineProtocol/).

The first model should propose page identity and candidate boxes, including an
UNKNOWN class. It must not infer costs, consent, difficulty, reward acquisition or
floor completion. Existing independent current-page OCR, budget transactions,
unique input intents and actual successors still decide whether input is allowed.
Changed seasons, unsupported Japanese text or conflicting evidence stop and retain
the capture. A classifier confidence is not a victory or reward receipt.

`learning_dataset.manifest` accepts explicit reviewed labels bound to a real
verifier's image hash. A raw OCR scene label is not a training target. Samples
retain image/proof hashes and the actual run scope. Entire scopes share one split,
so consecutive animation frames cannot leak between training and validation.
Conflicting duplicate frames, missing/changed evidence and external paths reject.
Missing class coverage leaves training readiness false. The data manifest never
enables a model or input; an ONNX model and held-out native replay are separate gates.

After enough independent runs exist, export a classifier to `model/classify`,
compare it on held-out English/Japanese runs and changed layouts, then add a
read-only shadow node. Log disagreements with the current recognizer. Only measured
coverage can promote recognition; UNKNOWN and independent action gates remain.
No trained model or self-learning runtime is currently accepted.

Strategy learning is separate from page recognition. Record offered gifts and
complete trials, saved team systems, owned gifts, HP state, chosen action and real
terminal outcome. Start with offline candidate ranking against the conservative
policy. A high-level team winning one run does not identify a gift's causal benefit;
missing counterfactuals and poor coverage must remain explicit. Learning may rank
already authorized candidates, but cannot buy training attempts, spend resources,
remove stop boundaries or replace a real payout receipt with task success.
