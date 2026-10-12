# DeepSeek continuation — 2026-10-12 11:36 local

The user explicitly asks DeepSeek Harness to continue until Codex returns, and
asks for DSH's task board to track the plan. Codex owns the framework architecture;
continue its existing implementation, fix defects, and verify actual gameplay.
Read PROJECT.md, docs/design.md, docs/acceptance.md and AGENTS.md first. Current
git/process/native reports supersede all old heartbeat descriptions.

## Immediate process ownership

- Actual GUI PID13240, child Agent40172 were alive at the checkpoint. GUI Start
  really dispatched MirrorTask/MainTask. Actual journal:
  `dist/MaaLimbus/evidence/runtime/pi-20261012-112240/events.jsonl`.
- Current run/team come from authoritative `config/user-run-ledger.json`, bound
  by installed `config/user-data-root.json`. Do not copy/replace the installed
  stale ledger. The current game is MAP floor2; a complete dungeon is unverified.
- While this task lives: observe only, no other controller, no app replacement,
  no restart because it takes time. Check CIM and actual terminal/result first.
  The task has a normal bounded stop. Do not interfere with unrelated processes.
- Initial/floor1 gifts, GET receipts, stars and floor2 theme drag are completed;
  never replay them. Preserve unresolved transaction intents. Fresh independent
  successors can resolve a known intent; unknown intent is not permission to retry.

## Root code ready for the next safe install

The last installed source repairs the real GUI NameError in map caption recovery.
The actual observer replay is `build/actual-agent-map-replay-20261012/verification.json`.
Root has additionally written source changes (not installed in the active app):

1. MainTask reads three independent shop nodes; loop_parameters resolves saved
   settings. Defaults manual/2 refreshes/0 coin reserve, strict bounded integers.
2. ShopTransaction enforces coin reserve AGAIN before purchase/refresh intent,
   stores immutable visit context; no module budget is affected.
3. `shop_learning.py` reaudits complete native shelves + exact coin delta and
   queues evidence, proposal, human review and trace under
   `build/learning-review/shop`. Refresh learning can reduce low-yield spending
   after three verified visits. Purchase-strength learning remains honest rule
   fallback; buying successfully is not evidence of combat benefit.
4. Map settling stops after two independently recognized unchanged MAP reads,
   capped at six reads instead of thirty. It remains failed until NODE_PANEL.
5. A54px actual bright question glyph outranks neutral white path cubes and small
   reward badges. Actual frame0095 replay + masked negative:
   `build/gui-map-candidate-replay-20261012.json`. This is candidate evidence,
   not a proved live node entry. The party strip is excluded from map probes.
6. GUI phase/failed-map-attempt/verified-shop-receipt logs now print concise
   reasons. Callback failures retain the original message/traceback. Neural
   review bundles now collect in the authoritative workspace's single directory.

Focused checks: shop/root wiring110 passed, map/options/dispatch140 passed.
The earlier whole run had1345 passes,1 skip,5 failures: four obsolete option/dispatch
fixtures are repaired; one canonical lease test competed with the live controller.
Do not call the whole suite green. Re-run the two real canonical-lease tests only
after the actual controller exits, then the appropriate full suite.

## Task board and execution order

Use DSH task-board tools if available; otherwise maintain a local board in this
document. Columns: To do / Doing / Awaiting real evidence / Done. Each card needs
implementation files, acceptance evidence paths and a precise next action.

1. **Doing: take over current GUI run observation.** Capture natural result and
   truthful input counts/page/floor. Preserve its screenshots/journal. If it is
   stuck, diagnose candidate priorities from actual frames; do not manually play
   past it. The script must perform the actions.
2. **To do: safe build and actual GUI regression.** After runner and GUI exit
   normally, use `tools/make_local_app.py --mxu-exe
   build/mxu-interactive-artifact/mxu.exe --mxu-proof
   build/mxu-interactive-artifact/build-proof.json`. Keep private hashes/backups,
   installed Agent self-test and model-policy hashes. Relaunch normally, click
   GUI Start and prove the node panel, inherited order reuse without Clear, and
   actual battle progression. Never silently switch to a separate controller.
3. **To do: real shop purchase/refresh including pre-boss shops.** Verify GUI
   settings reach the actual Runner, read saved-team keywords/allow/block, then
   one purchase, question and successor receipt. A named GET overlay is a known
   integration gap: implement a durable one-shot receipt acknowledgment using
   full matching title/native GET and retain pending until exact coin delta and
   complete shelf prove payment. Do not reuse floor-gift bookkeeping as a shop
   receipt. Skills need a separately proven subpage and transaction, not a fake
   enabled switch. Root's `shop_skill_vision.py` handoff needs exact possessive
   name normalization and native price crop evidence. No price guessing.
4. **To do: finish one complete script-driven Mirror run.** Collect per-floor
   gift/receipt/next-floor evidence. Fresh payout cost requires an explicitly
   configured budget for this current scope; old6-module permission is not
   transferable. If budget is absent preserve the offer, continue offline work,
   don't toggle weekly/GiveUp/ToWindow or repeatedly ask old unanswered questions.
   Full pipeline success means actual floor5/victory/receipt/HOME, not task callback
   success, alive process or test counts.
5. **To do: neural and labels real pipeline verification.** The installed local
   square ONNX is real trained130 crops/12 classes but has quality failures.
   `build/sinner-shadow-native-resize-20261012` and
   `build/deepseek-neural-resume-handoff.json` document them. The research model
   must remain shadow/productionFalse/inputFalse. Collect actual PRE boxes,
   independent native caption/corner/identity teachers and separate episodes;
   archive predictions/evidence/corrections together. Do not turn its own boxes
   into ground truth. Train/evaluate improvements in the isolated
   `build/neural-learning-venv`, never replace the machine CUDA environment.
   Use HuiJi public catalogue index, reconcile owned identities, preserve unknown
   ownership. Actual E.G.O/system equip verification is still open.
6. **To do: end-to-end stress/continuation.** GUI Start, unknown bounded attempts,
   stop/restart intent recovery, shop visit limits, full run and actionable logs.
   Unknown recognized navigation may try a bounded alternative and self-propose
   labels; no change after a few attempts ends with retained evidence. Never
   clear unknown paid/selection intents or invent successor credit.

## Boundaries

- Maa owns screenshot/OCR/NN/input/task graph; use its public OOP APIs. No game
  memory, private game API, injection or ad-hoc ADB taps as a substitute.
- Only one controller; Maa touches inside detected boxes350–750ms and bounded
  swipes. Windows UI uses the supplied native computer-use tooling; user handles
  UAC, no bypass. If elevation blocks unattended work record the blocker and do
  independent offline work.
- No FGO input/start/config/release mixing. No limit checks/purchases/resets.
- Do not upload private screenshots/config/logs externally. Local reports are
  evidence; public code/metadata can be committed. User authorizes commit/push
  and necessary releases, but no release claiming unfinished gates are complete.
- Existing separate `mirror_learning_policy.py` is an unwired offline heuristic
  helper, not a trained NN. Review before using; do not replace Root architecture.
- At each real milestone update PROJECT/acceptance, board and an exact continuation
  manifest. Tell the user truthful completion, failure or needed interaction only.
