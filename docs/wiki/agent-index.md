# MaaLimbus: agent quick routes

从问题找功能，再打开当前符号和对应局部图。无需通读全站；源码/当前实证优先于过期叙述。
Query → current symbol → local explanation/diagram → narrow check → evidence boundary.
Queries recompute source positions. Navigation aid, not completion proof or workflow lock.

`python tools/wiki_route.py "星光余额"` · `--list` · `--check` · `--build`

| Route / question | Current source | Explanation / plan |
| --- | --- | --- |
| **startup** — GUI开始红停 / actual Start pipeline | `agent/recognition.py:1707` `MainTaskAction.run`<br>`agent/recognition.py:1623` `MirrorLoopAction.run`<br>`src/maalimbus/runner.py:566` `MaaDevice.__init__`<br>`src/maalimbus/runner.py:1536` `run_node`<br>`agent/recognition.py:1552` `AgentTasker.post_task` | [feature-9-3-1](zh_cn/9-execution-plan.md#feature-9-3-1)<br>[feature-9-3-1](en_us/9-execution-plan.md#feature-9-3-1)<br>[feature-4-3-2](zh_cn/4-business-flows.md#feature-4-3-2) |
| **queue** — 单队、轮换和离屏Team查找 | `src/maalimbus/task_preferences.py:69` `TaskPreferences.set_mirror_queue`<br>`src/maalimbus/team_vision.py:14` `selected_saved_team` | [feature-4-10](zh_cn/4-business-flows.md#feature-4-10)<br>[feature-4-10](en_us/4-business-flows.md#feature-4-10) |
| **stars** — 星光余额、卡片和已发送购买恢复 | `src/maalimbus/grace_balance_native.py:7` `repair`<br>`src/maalimbus/grace_transaction.py:138` `GraceTransaction.recover`<br>`src/maalimbus/mirror_starlight.py:41` `resolve` | [feature-4-3-5](zh_cn/4-business-flows.md#feature-4-3-5)<br>[feature-4-3-5](en_us/4-business-flows.md#feature-4-3-5) |
| **deployment** — 部署顺序复用与实际人数 | `src/maalimbus/deployment_transaction.py:5` `DeploymentTransaction.prepare`<br>`src/maalimbus/team_vision.py:123` `carries_saved_order` | [feature-4-3-3](zh_cn/4-business-flows.md#feature-4-3-3)<br>[feature-4-3-3](en_us/4-business-flows.md#feature-4-3-3) |
| **shop** — 商店购买、刷新和金币对账 | `src/maalimbus/shop_vision.py:354` `matching_purchase_question`<br>`src/maalimbus/shop_transaction.py:487` `ShopTransaction.reconcile_purchase`<br>`src/maalimbus/shop_transaction.py:596` `ShopTransaction.reconcile_refresh` | [feature-4-3-8](zh_cn/4-business-flows.md#feature-4-3-8)<br>[feature-4-3-8](en_us/4-business-flows.md#feature-4-3-8) |
| **receipts** — 藏品GET与后继恢复 | `src/maalimbus/floor_gift_transaction.py:173` `FloorGiftTransaction.observe_receipt` | [feature-4-3-4](zh_cn/4-business-flows.md#feature-4-3-4)<br>[feature-4-3-4](en_us/4-business-flows.md#feature-4-3-4) |
| **progress** — 这一局走到哪一层、这层还剩几步 | `src/maalimbus/dungeon_progress.py:41` `dungeon_progress`<br>`src/maalimbus/dungeon_progress.py:92` `steps_left` | [feature-9-3-11](zh_cn/9-execution-plan.md#feature-9-3-11)<br>[feature-9-3-11](en_us/9-execution-plan.md#feature-9-3-11) |
| **scores** — 候选权重与最终评分日志 | `src/maalimbus/decision_log.py:4` `lines`<br>`src/maalimbus/floor_gifts.py:303` `rank`<br>`src/maalimbus/theme_vision.py:183` `recommend_pack` | [feature-9-5](zh_cn/9-execution-plan.md#feature-9-5)<br>[feature-9-5](en_us/9-execution-plan.md#feature-9-5) |
| **unknown** — 未知页面的有界探索和证据包 | `src/maalimbus/unknown_exploration.py:68` `Exploration`<br>`src/maalimbus/semantic_labels.py:38` `persist_frame_proposals` | [feature-9-3](zh_cn/9-execution-plan.md#feature-9-3)<br>[feature-9-3](en_us/9-execution-plan.md#feature-9-3) |
| **neural** — 神经模型是否真正用于识别或策略 | `src/maalimbus/neural_shadow.py:98` `verified_model`<br>`src/maalimbus/shop_value_shadow.py:7` `rank_preview` | [feature-9-4](zh_cn/9-execution-plan.md#feature-9-4)<br>[feature-9-4](en_us/9-execution-plan.md#feature-9-4) |
| **gpu** — CPU、内存、GPU和显存占用 | `src/maalimbus/resource_diagnostics.py:354` `sample`<br>`src/maalimbus/resource_diagnostics.py:218` `NvidiaSmiProvider`<br>`src/maalimbus/resource_diagnostics.py:331` `_process_gpu_block` | [feature-9-6](zh_cn/9-execution-plan.md#feature-9-6)<br>[feature-9-6](en_us/9-execution-plan.md#feature-9-6) |
| **run-count** — 镜牢完整局数与步数上限 | `src/maalimbus/runner.py:188` `Settings` | [feature-9-3](zh_cn/9-execution-plan.md#feature-9-3)<br>[feature-9-3](en_us/9-execution-plan.md#feature-9-3) |
| **payout** — 领奖、返回和一次轮换记账 | `src/maalimbus/reward_task.py:27` `finish`<br>`src/maalimbus/storage.py:249` `RunStore.record` | [feature-4-6-1](zh_cn/4-business-flows.md#feature-4-6-1)<br>[feature-4-6-1](en_us/4-business-flows.md#feature-4-6-1) |
| **settings** — 头像编队和星光卡片编辑器 | `desktop/mxu/TeamBuildEditor.tsx:9` `export function TeamBuildEditor`<br>`desktop/mxu/StarCardsEditor.tsx:8` `export function StarCardsEditor` | [feature-9-2](zh_cn/9-execution-plan.md#feature-9-2)<br>[feature-9-2](en_us/9-execution-plan.md#feature-9-2) |
| **updater** — GitHub更新按钮与安装分发 | `desktop/mxu/SoftwareUpdatePanel.tsx:6` `export function SoftwareUpdatePanel` | [feature-6-4-5](zh_cn/6-deployment.md#feature-6-4-5)<br>[feature-6-4-5](en_us/6-deployment.md#feature-6-4-5) |
| **recovery** — 一步没落地时的视角手势与识别卡死看门狗 | `src/maalimbus/runner.py:478` `pinch_out`<br>`src/maalimbus/runner.py:4439` `MirrorRunner._recover`<br>`src/maalimbus/runner.py:505` `stall_watchdog` | [feature-9-3-8](zh_cn/9-execution-plan.md#feature-9-3-8)<br>[feature-9-3-8](en_us/9-execution-plan.md#feature-9-3-8) |
| **plan** — 实施计划、依赖、工程图和完成标准 | Planned; see specification | [feature-9-2](zh_cn/9-execution-plan.md#feature-9-2)<br>[feature-9-2](en_us/9-execution-plan.md#feature-9-2) |

## Evidence and checks

Query responses include only the selected routes: aliases, current locations, tests, checks and scope boundary.
Acceptance/PROJECT carry volatile progress. Planned features have no invented source location.
Regenerate with `--build` after structural changes. `--check` reports stale snapshots without locking work.
