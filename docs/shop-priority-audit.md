# 商店优先级与规则排序审计：它们真的改动过一次真实购买吗？神经识别是真的还是只做影子？

范围（card ⑤ 离线半，只读审计）：回答两个问题——

1. 商店的**优先级权重**（`Prestige Card` 的 100，以及 90/85/80/70/60）与**规则排序**（`shop-policy: learned` 那条学习策略）
   有没有真的改动过一次**真实购买**的选择；
2. 出厂/打包里的**神经识别**（`sinners.onnx`）是真实生效的判定，还是只写影子、不能影响任何输入。

本文件只做离线审计与文档：不改运行时/测试/配置/`assets`/`dist`，不启 controller，不操作游戏，
不提交、不推送。行号与判定按工作树**当前**读取，写作时逐条打开核对；凡未亲自打开的，收在第七节「未验收」。

前置：**商店优先级这条链不是「只显示」**——下面的源码路径与 3 组留档实证都表明，
`gift_plan.py:61` 的排序会进入 `runner.py:1029` 的购买选择，并且真实发生过「为了排序靠前而多付 50 金币」的购买。
真正「只显示、从未改动真实购买」的是**学习策略（`learned`）那条规则排序**，以及**神经识别的全部输出**。

## 结论摘要

| 问题 | 判定 | 触发/证据锚点 | 留档实证 |
| :-- | :-- | :-- | :-- |
| 优先级权重是否改变过真实购买 | **权重值本身从未**（100/90/85/80/70/60 六件礼物从未有两件同时在同一个货架上） | `assets/resource/base/shop-priorities.json:5-13`、`src/maalimbus/gift_plan.py:61`、`src/maalimbus/runner.py:1957` | 5 条 `shop_decision_ranking` 里 `Prestige Card` 零出现 |
| 规则/计划顺序是否改变过真实购买 | **改变过，3 次**，且是当次货架上**更贵**的那个被买走 | `src/maalimbus/shop_vision.py:280`、`src/maalimbus/runner.py:1029` | `Cigarette Holder@197` 胜过同货架 `Grimy Iron Stake@147`（见第四节） |
| `shop-policy: learned` 的规则排序是否改变过真实购买 | **没有任何一次**，且**即使启用也不改顺序**（`rank_preview` 每条返回路径都原样返回 `list(offers)`） | `src/maalimbus/shop_learning.py:101-102`、`src/maalimbus/shop_value_shadow.py:11,53,56` | 23 条 `shop_policy` 全部 `mode=manual`；5 条 ranking 事件 `learning=null` |
| 学习到的「刷新收益」是否能停刷新 | 代码上**只能减少花费**，从未在留档里生效 | `src/maalimbus/shop_learning.py:105-120` | `refresh_learning_applied` 零次为真 |
| 神经识别是否真实执行 | **真实执行**（真切片推理，非桩） | `src/maalimbus/neural_shadow.py:124-149`、`agent/recognition.py:366-374` | 23202 帧中 74 帧 `native_inference_executed: true` 且 `boxes` 非空 |
| 神经识别能否影响输入/购买/训练 | **不能**：`mode: shadow` 只允许写日志与未复核队列 | `neural_shadow.py:119-120,149`、`semantic_labels.py:69,87` | 1346 条 `semantic_frame_proposal`，全部 `training_eligible=False, input_authorized=False` |
| 出厂默认是否开神经识别 | **出厂默认 off**；跑起来是靠一个**不被 git 跟踪**的本地覆盖文件 | `assets/resource/base/neural-learning.json:3`、`neural_shadow.py:126-127` | 724 帧 `status=off`，1295 帧 `status=shadow` |
| 模型卡是否自承缺陷 | **自承**：拟合期验证喂了训练图、无验证/测试划分、`quality_passed=false` | `sinners.model-card.json:31,33,36,40`、`sinners.native-evaluation.json:2578,2582,2588,2589` | 影子照样执行，只把 `native_quality_passed=false` 记进帧 |

一句话：**优先级这条链是活的、承重的**（计划顺序直接决定买哪一个，已观测到 3 次真实改选）；
**学习策略那条「规则排序」是死的**（从未启用，且启用也返回原序）；
**神经识别是真的在推理，但被硬关在影子通道里**——它唯一的出口是一份未复核、不可训练的提案队列，
而它绑定的模型卡自己写着「验证用了训练图、没有独立的验证/测试」。

## 一、优先级值被谁消费（源码事实）

权重从文件进计划，再从计划进购买选择，四跳：

1. **读文件**：`src/maalimbus/runner.py:1824-1825`
   `from .shop_priority import load as load_shop_priorities` ／
   `explicit_priorities=load_shop_priorities(ROOT/'assets/resource/base/shop-priorities.json',catalog)`。
   `src/maalimbus/shop_priority.py:5` `def load(path,catalog)`：文件不存在返回 `{}`（`:6`），
   `:15` 要求「目录里已知的、唯一的礼物名 + 0..100 的整数」，否则 `raise ValueError`。
   出厂的六条就是 `assets/resource/base/shop-priorities.json:5-13`：`Prestige Card 100`、`Golden Urn 90`、
   `Voracious Hammer 85`、`Milepost of Survival 80`、`Pre-order Discount 70`、`New Release Pamphlet 60`。

2. **进计划顺序**：`src/maalimbus/runner.py:1826` `names=shop_wanted(profile,catalog,explicit_priorities)`。
   `src/maalimbus/gift_plan.py:51` `def shop_wanted(team,catalog,priorities=None)`，
   `:58-60` 先筛出「队里允许、或关键词命中、或**权重>0**」的礼物，然后

   ```python
   # src/maalimbus/gift_plan.py:61
   return sorted(preferred,key=lambda name:(-priorities.get(name,0),name not in team.allow,name))
   ```

   即：**权重降序 → 队允许优先 → 名字字母序**。没有显式权重的礼物权重按 `0` 处理（不是 100），
   所以队语义里那一大串礼物是「按字母序」排在六个权重礼物**之后**的。

3. **计划顺序决定候选顺序**：`src/maalimbus/shop_vision.py:267` `def wanted_offers(found,names,bought=())`，
   文档串（`:268`）写明「in the plan's own order」，实现 `:273 order=[...names...]`、
   `:279 ranked.append((order.index(key),offer))`、`:280 ranked.sort(key=lambda row:(row[0],row[1].index))`
   ——**第一关键字是计划里的名次，第二关键字才是货架位置**。已买过的名字被排除（`:274,278`）。

4. **买第一个**：`src/maalimbus/runner.py:996` 读货架 → `:998 wanted_offers_now=wanted_offers(found,wanted,bought)` →
   `:1020-1021` 只留「印出的价格 ≤ 现有金币 − 预留」的 → `:1029 offer=affordable[0]` →
   `:1030-1032 buy={... 'why':'gift_plan'}`。**买的就是计划顺序里的第一个可负担项，与价格高低和货架位置无关。**

因此：**只要某次货架上有两个及以上「计划想要且买得起」的礼物，优先级/计划顺序就决定了买哪一个。**
这是一条承重路径，不是展示字段。

配套的第三个兜底规则与优先级无关：`src/maalimbus/runner.py:1064-1078` 的 `carry_cap`，
在「计划没得买、也没得刷新」时**按最低价**花掉超出上限的金币（`:1076 offer=min(cheap,key=lambda item:(item[1].price,item.index))`，
实现为 `item.price, item.index`），`why='carry_cap'`——它刻意**不看**计划顺序。

## 二、`learned` 规则排序为什么不可能改动真实购买

`shop-policy: learned` 时才会走这条路（`src/maalimbus/runner.py:1023-1027`）：

- `src/maalimbus/shop_learning.py:96` `def rank_offers(offers,samples,context=None)`，
  文档串（`:97`）自称「No survival/strength evidence yet: deterministic affordable rule fallback」，
  `:100-101` 委托 `from .shop_value_shadow import rank_preview`，`ROOT/'assets/resource/base/model/shop-value'`，
  `:102 return ordered,dict(trace,mode='learned',samples=len(samples))`——**直接把 `rank_preview` 的返回值当顺序返回**。
- `src/maalimbus/shop_value_shadow.py` 的**每一条返回路径都原样返回 `list(offers)`**：
  `:11` 权重/模型卡文件缺失时 `return list(offers),trace`；
  `:53-54` 影子模型真的跑完时 `return list(offers),dict(trace,neural_value_shadow_applied=True,...,reason='candidate_shadow_only_not_a_promoted_purchase_policy')`；
  `:55-56` 任何校验失败时 `return list(offers),dict(trace,reason='invalid_value_candidate_rule_fallback',...)`。
  它只把 `scores` 挂进 trace，**没有一处按分数重排**。
- 也就是说：即使把 `shop-policy` 打开成 `learned`，`affordable` 的顺序与 `runner.py:1020-1021` 出来的顺序**逐元素相同**，
  `runner.py:1029` 仍然买同一个；`decision_log.py:23` 对该 trace 的渲染也如实写成
  「仅影子预测，不改变购买顺序」。

学习只在一个地方能改变**花费**而不是顺序：`src/maalimbus/shop_learning.py:105-120 refresh_decision`。
`len(episodes)<3` 时永远返回 `True`（`:114-115`，继续按规则刷新）；只有「≥3 次相互独立的访问且有用产出为 0」才返回
`False`（`:116-119 refresh_learning_applied=True`）。它**只能少花钱，不能买更多**，且留档里从未生效（见第三节）。

## 三、留档实证：事件计数与策略

统计口径：`evidence/runtime/**/events.jsonl`（含 `dist/MaaLimbus/evidence/runtime/pi-*` 的留档），
以及 `config/user-shop-*.json` 两份真 store。

| 事件 | 条数 | 关键字段实测 |
| :-- | --: | :-- |
| `shop_policy` | 23 | **全部 `mode=manual`**（`refresh=2`、`reserve=500`、`carry=1500`）→ `learned` 分支一次都没进 |
| `shop_decision_ranking` | 5 | 全在 `packaged-mirror-20261014-065112`；**5/5 `learning=null`**；事件本身没有 `policy` 字段，同 run 的 `shop_policy` 为 `manual` |
| `shop_offers` | 23 | 每次决策都记了完整 `offers` 与 `buy` |
| `shop_purchase_sent` / `shop_purchase_confirmed` | 8 / 7 | 每笔都有 `why`，见下 |
| `shop_purchase_learning_samples` | 13 | `neural_policy_applied=false` **13/13**；`samples` 0..3 |
| `shop_learning_unavailable` | 10 | 原因全部是 `Shop policy purchase evidence differs`（`sync_receipts` 抛错 → `learning` 回落成 `[]`） |
| `shop_shelf_refreshed` | 4 | 刷新走的是规则路径 |

5 条 ranking 事件逐行读（`ranking[]` 的 `status` 是「可购买 / 超过可用金币 / 不在候选队列」，
`manual_weight` 取自当前 run 的 `explicit_priorities`，`chosen` 是该行是否被买）：

| # | 货架状态 | 可购买且可负担的行 | 结果 |
| --: | :-- | :-- | :-- |
| 1 | `Emerald Elytra 160`（`score=1`）+ `New Release Pamphiet 200`（OCR 拼错，`manual_weight=0`，不在候选队列） | **1 行** | 买到 `Emerald Elytra` |
| 2 | `New Release Pamphlet 200`（`manual_weight=60`，`score=1`） | **1 行** | 买到 `New Release Pamphlet` |
| 3 | 无可负担候选 | 0 | 刷新 |
| 4 | `Devil's Share 144`（`score=2`）、`Ornamental Horseshoe 154`（`score=1`）**两行都在候选队列但都超过可用金币** | 0 | 未购买（`every_offer_the_plan_asked_for_costs_more_than_the_shop_holds`） |
| 5 | 无可负担候选 | 0 | 未购买 |

两点必须写清：
① `score` 的语义是「计划顺序的倒排名次」：`runner.py:1952 ranks={o.index:len(matches)-n for n,o in enumerate(matches)}`
——**分数越大越靠前**，分数 1 是最后一个。第 1/2 条各自**只有一行**合格（`len(matches)==1`，故 `score` 恒为 1），
所以那两次优先级不可能改选；第 4 条两行的 `score=2,1` 说明 `Devil's Share` 排在 `Ornamental Horseshoe` 之前。
② 第 4 条是全留档里**唯一**同时出现两行候选的一次，恰好两行都超预算——**最接近「优先级本可生效」的一次以未购买收场**。
③ 第 1 条还把优先级机制的一个真实失效模式拍了下来：同一个礼物在相邻两次决策里先是 `New Release Pamphiet`（`manual_weight=0`，不进候选），
后是 `New Release Pamphlet`（`manual_weight=60`，候选人）。匹配是**精确名字**：`shop_vision.py:277 key=offer.name.strip().lower()`，
`gift_plan.py:59-60` 也要求名字在 `catalog.entries` 里——OCR 多/少一个字符，权重就整条丢失。

## 四、真实购买里，计划顺序确实改了选择（3 例，最强反证与最强正证）

从 `config/user-shop-*.json` 的 `bought[].decision_context`（键 `wanted` 是完整的计划全序、`offers` 是当次货架报价）逐笔重算，
14 笔成交里 10 笔是 `why=gift_plan`、3 笔 `why=carry_cap`。其中 3 笔当次货架上有**两个及以上**计划想要的礼物：

| 买到 | 价 | 同为「计划想要」的竞品（同货架） | 竞品计划名次 | 结论 |
| :-- | --: | :-- | --: | :-- |
| `Cigarette Holder` | 197 | `Grimy Iron Stake` 在**货架 idx2**、147 金币 | 计划 #29 | 买走的 `Cigarette Holder` 是 **#12**：**既更贵、又在货架上更靠后**，仍被买走 → **只有计划顺序能解释** |
| `Grimy Iron Stake` | 147 | `Stone Tomb` 196（`Cigarette Holder` 已在上一笔买过、被 `wanted_offers` 排除） | 计划 #56 | 买 #29 而非 #56 |
| `Rusted Cutting Knife` | 244 | `Tangled Bundle` 159 | 计划 #57 | 买 #51 而非 #57；货架顺序相同，但**价格差 85 金币**说明不是按价挑 |

第一行是最强的正证：如果选择按**货架顺序**，应当买 idx2 的 `Grimy Iron Stake`；如果按**价格**，也应当买 147 的它；
实际买的是 197 的 `Cigarette Holder`，唯一能解释的键就是 `shop_vision.py:280` 的第一关键字（计划名次 12 < 29）。
即：**「优先级/计划顺序改动真实购买」这件事在留档里发生过 3 次，其中 1 次明确战胜了价格与货架位置。**

同一个决策里还藏着一个反证细节：当次货架上其实有一件**权重礼物**——`Pre-orderDiscount @250`
（`weight=70`，本应排计划 #4）。它被 OCR 读成一整块 `Pre-orderDiscount`（空格丢失），
既不在 `catalog.entries` 里、也过不了 `shop_vision.py:277` 的精确名匹配，于是**权重 70 整条丢失**。
所以「权重值改变购买」之所以一次都没被观测到，一部分原因是**权重礼物很难正好好地被 OCR 读对并同时出现两件**，
而不是因为权重不参与选择。

## 五、神经识别：真的在推理，但被硬关在影子里

**它真的跑。** `src/maalimbus/neural_shadow.py:124 def observe(...)` 在 `:126-127` 先找
`assets/resource/base/neural-learning.local.json`，缺失才回落 `neural-learning.json`；`:129` `mode=='off'` 直接返回
`dict(status='off',...)`；`:130` 任何非 `shadow` 的 mode 直接 `raise ValueError('Only read-only neural shadow is supported')`；
`:131` 过 `verified_model`；`:137-143` 逐 ROI 调
`context.run_recognition_direct(JRecognitionType.NeuralNetworkDetect, JNeuralNetworkDetect(model='sinners.onnx',...))`，
真读原生 `filtered_results`；`:145-149` 回填 `status='shadow'`、`boxes`、`model_sha256`、
`native_inference_executed=bool(rois)`。

**出厂默认是关的，开影子靠的是一个不被 git 跟踪的本地覆盖。** 出厂文件
`assets/resource/base/neural-learning.json:3` 是 `"mode": "off"`，文件末尾自述
「Enable read-only shadow only with a reviewed sinner ONNX artifact. Never auto-promote predictions.」；
而它的同目录兄弟 `assets/resource/base/neural-learning.local.json:3` 是 `"mode": "shadow"`、
`roi_mode: verified_card_edges`——这个 `.local` 文件**不被 git 跟踪**（由 `.git/info/exclude` 排除，
`git status` 里看不到），却实实在在存在于工作树与 `dist/MaaLimbus/assets/resource/base/`（打包产物）里，
这正是 packaged-mirror 那次运行能写出 `status=shadow` 的原因。也就是说：**clone 下来默认不跑影子，
跑起来的那份是把一个本地未跟踪文件连同资源一起打包进了 dist**。
按帧统计：23202 帧里 **724 帧 `status=off`**、**1295 帧 `status=shadow`**、**74 帧 `native_inference_executed=true` 且 `boxes` 非空**、
其余 21183 帧没有 `neural_sinners` 字段（旧帧格式）。即影子确实开过、也确实算过，但只覆盖 `verified_card_edges`
允许的页面（`neural_shadow.py:32` 要求 `scene=='PRE_BATTLE_TEAM'` 且 1920×1080、`:35-37` 还要求 `To Battle!` 与 `Details` 各命中一次）。

**它允许影响什么、禁止影响什么（代码自己写的）：**

- 允许：只允许成为**日志字段**与**未复核提案**。
  `agent/recognition.py:366-374` 在 `try` 里调用它，注释原文
  `# Optional shadow cannot change recognition, intents or device input.`；
  拿到结果后 `:375-377` 用 **OCR 派生的 `records`** 建帧，影子只作为 `neural_sinners=` 参数写进 journal；
  `:378-391` 场景命中或影子成立时，才把这一帧交给 `semantic_labels.persist_frame_proposals` 进未复核队列。
- 允许（严格受限）：`src/maalimbus/semantic_labels.py:55-59` 会读 `neural_sinners.boxes`，但注释写明
  `# Revalidate native output rather than trusting serialized proposal flags`——它**重新过一遍** `proposals(...)`，
  不信任序列化标记；产物 `:69` 与 `:87` 都带 `reviewed=False`、`training_eligible=False`、`input_authorized=False`，
  末行 trace 自述 `Unreviewed neural boxes: N`。该模块文档串 `:41-43` 写着
  「None may turn their own boxes into reviewed training truth.」留档计数：`semantic_frame_proposal` 1346 条排队、**0 条被拒**。
- 禁止：`neural_shadow.py:119-120` 只要策略里写了 `production_enabled` 或 `input_authorized` 就
  `raise ValueError('Shadow cannot grant gameplay input')`；`:149` 的返回值本身固定
  `training_eligible=False,production_enabled=False,input_authorized=False`。
  `src/maalimbus/pre_battle_identity.py:3` 把这条写成不变量：「The neural shadow may not approve its own labels」。
- 摘要：影子**不能**授权输入、不能购买、不能训练、不能把自己的框变成已复核真值；它**只能**产出一份
  内容寻址、`reviewed=False` 的提案队列和帧日志字段。

**绑定是真的。** `neural_shadow.py:98 def verified_model(resource,policy)` 在 `:104-105` 要求
`model/detect/sinners.onnx`、`sinners.model-card.json`、`sinners.native-evaluation.json` 三个都在且不是软链；
`:106-111` 对三个文件算 SHA256 并与策略里写的 `model_sha256`/`model_card_sha256`/`native_evaluation_sha256` 逐一对齐，
还要求标签表等于 `LABELS`；`:112-118` 要求 `training_complete is True`、`synthetic_model is False`、
`onnx_sha256` 与原生评估的 `model_sha256` 都等于实算值、`recognizer=='MaaFramework.NeuralNetworkDetect'`、
`input_sent is False`、`game_controller is False`。当前树实测三件哈希与策略/卡片互相一致：
`sinners.onnx = 859b8546292fc32007a22ac1723dded382bbb77a25d34246369d78200ebc1a59`、
`sinners.model-card.json = cb633384e6b3c4d93735e4945dbe8f8e924fdd4738484d557ec4d89643ce6579`、
`sinners.native-evaluation.json = b9f9eadea9511d4231e71de650881e19697202684224b77965efc84eb7aa3b61`
（与卡片 `sinners.model-card.json:38 onnx_sha256`、`:3 weights_sha256` 的**不同**是正常的：前者是导出的 ONNX，后者是训练权重）。

## 六、模型卡自己承认的缺陷（照抄，不替它圆）

`verified_model` 只校验「真有训练、哈希自洽、非合成、没发过输入」，**并不校验质量**。而模型卡与原生评估自己写着：

| 事实 | 原文锚点 |
| :-- | :-- |
| 拟合期验证用的是训练图 | `assets/resource/base/model/detect/sinners.model-card.json:36` `"fit_validation_uses_training_images": true` |
| 留出集指标未经验证 | `sinners.model-card.json:33` `"held_out_metrics_verified": false` |
| 只有研究用途 | `sinners.model-card.json:31` `"research_only": true` |
| 导出的 ONNX 指标是空的 | `sinners.model-card.json:40-42` `"exported_onnx_metrics": { "val": null, "test": null }` |
| 唯一 episode 被划进 `train` | `sinners.model-card.json:27-29` `"episodes": { "owned-gallery-…": "train" }` ——**没有 validation/test 划分** |
| 原生评估自述只有拟合 | `sinners.native-evaluation.json:2589` `"research_fit_only": true`、`:2588` `"validation_and_test_independent": false` |
| 质量未通过 | `sinners.native-evaluation.json:2582` `"quality_passed": false`、`sinners.model-card.json:49` `"native_quality_passed": false` |
| 拟合集里**一张负样本都没有** | `sinners.native-evaluation.json:2578` `"negative_images": { "train": 0 }` |

`neural_shadow.py:90-91` 的通过条件是 `not research_fit and ... and negative[p]>0 and precision/recall/IoU 达标`——
用 `research_fit=True` 评估出来的这份 JSON 天然 `quality_passed=False`；
`:148` 把它如实记进帧（`native_quality_passed=native.get('quality_passed') is True` → `false`），
但**不因此停止影子执行**。所以准确说法是：**影子跑的是「自知未过质量门、且其验证曾喂过训练图」的模型**，
它之所以还算安全，靠的不是模型质量，而是第五节那套「不许影响输入」的管线约束。

## 七、从未在留档里观察到（未验收清单）

以下均为**零观测**，不是「已经没问题」：

1. `shop-policy` 取 `learned` 的任何一次运行（23/23 `shop_policy` 为 `manual`）。
2. `shop_decision_ranking` 里 `learning` 非 `null` 的任何一次（5/5 为 `null`）——因为 `runner.py:1022 policy_trace=None`，
   只有 `learned` 才会被填。
3. `refresh_decision` 返回 `False` 从而**真的跳过刷新**的任何一次（`refresh_learning_applied` 从未为真）。
4. `shop_value_shadow.rank_preview` 的**成功分支**（`neural_value_shadow_applied=True`）——
   该分支要求 `assets/resource/base/model/shop-value/` 下有自洽的 `weights.json`+`modelcard.json`
   （`shop_value_shadow.py:10-31`）。实测：`assets/resource/base/model/shop-value/` **不存在**
   （`assets/resource/base/model/` 下只有 `detect` 与 `ocr`），整棵 `model/` 树里也没有任何 `weights.json`/`modelcard.json`，
   因此该分支每次都从 `shop_value_shadow.py:11` 提前返回；**商店价值模型一次都没跑过**。
5. 一次决策里**同时有两件及以上可负担的权重礼物**（100/90/85/80/70/60 任意两件同架）——因此
   「权重数值」是否会影响真实购买，**在留档里无法判定**；只有「计划顺序」被证明了。
6. `Prestige Card`（100）出现在任何货架上——零帧。
7. 神经影子输出被任何**判定/输入**消费的任何一次：`neural_sinners` 的读者只有
   `agent/recognition.py:375` 的 journal 字段与 `semantic_labels.py:55` 的提案队列；
   1346 条提案**没有任何一条**被复核（`reviewed=False`）或转成训练真值。
8. 影子的复核闭环：`build/learning-review/frames/**/review.json` 未见任何 `approved=True` 的留档。
9. `native_inference_executed=true` 只出现在 `verified_card_edges` 页面（`PRE_BATTLE_TEAM`）；
   在 `DEPLOYMENT`/`TEAM_LIBRARY`/商店/战斗页从未算过（`neural_shadow.py:32` 直接返回 `[]`），
   所以「影子能否在其它页面给出框」**未被观测**。

## 附：本文引用的源码/资源位置

| 位置 | 内容 |
| :-- | :-- |
| `assets/resource/base/shop-priorities.json:5-13` | 六条手动权重（100/90/85/80/70/60），自述「不是学到的效用」 |
| `src/maalimbus/shop_priority.py:5-17` | `load()`：只接受目录内已知、唯一、0..100 的整数权重 |
| `src/maalimbus/gift_plan.py:51-61` | `shop_wanted()`；`:61` 权重降序→allow→字母序，无权重按 0 |
| `src/maalimbus/shop_vision.py:267-281` | `wanted_offers()`：`:280` 先按计划名次、再按货架位置排序 |
| `src/maalimbus/runner.py:1824-1826` | 读权重文件 → 计划顺序 `names` |
| `src/maalimbus/runner.py:996-998` | 读货架 → 计划候选 |
| `src/maalimbus/runner.py:1020-1032` | 可负担过滤 → `:1029 affordable[0]` 即买它，`why='gift_plan'` |
| `src/maalimbus/runner.py:1064-1078` | `carry_cap` 兜底：`:1076` 按最低价，刻意不看计划顺序 |
| `src/maalimbus/runner.py:1942-1961` | `shop_policy`（`:1942 mode`）与 `shop_decision_ranking`（`:1957 manual_weight`、`:1958 status`、`:1959 chosen`） |
| `src/maalimbus/shop_learning.py:96-102` | `rank_offers()`：`:101` 委托影子，`:102` 原样返回顺序 |
| `src/maalimbus/shop_learning.py:105-120` | `refresh_decision()`：只能少花，≥3 次独立零产出才停 |
| `src/maalimbus/shop_value_shadow.py:11,53-56` | 三条返回路径都 `list(offers)`，只挂 `scores`/`trace` |
| `src/maalimbus/decision_log.py:18-23` | ranking 的中文渲染，`:23`「不改变购买顺序」 |
| `src/maalimbus/neural_shadow.py:98-121` | `verified_model()`：`:104-118` 三件哈希与原生绑定；`:119-120` 拒绝授权输入 |
| `src/maalimbus/neural_shadow.py:124-149` | `observe()`：`:126-127` 本地覆盖优先、`:129 off`、`:130 只允许 shadow`、`:137-143` 真推理、`:145-149` 返回值固定不可输入/不可训练 |
| `agent/recognition.py:366-391` | 调用点；`:372` 注释「cannot change recognition, intents or device input」；`:378-391` 只进未复核队列 |
| `src/maalimbus/semantic_labels.py:41-43,55-59,69,87` | 重新校验影子框；产物 `reviewed/training_eligible/input_authorized` 全为假 |
| `src/maalimbus/pre_battle_identity.py:3` | 不变量：影子不得批准自己的标签 |
| `assets/resource/base/neural-learning.json:3-7` | 被跟踪的出厂策略：`mode: off` |
| `assets/resource/base/neural-learning.local.json:3,22-23` | 未被跟踪的本地覆盖：`mode: shadow`，仍 `production_enabled/input_authorized: false` |
| `assets/resource/base/model/detect/sinners.model-card.json:27-49` | 自承：`:36` 验证喂训练图、`:33` 未验证留出、`:31` 仅研究、`:40` 指标为空、`:49` 质量未过 |
| `assets/resource/base/model/detect/sinners.native-evaluation.json:2578,2582,2588-2589` | 拟合专用评估：零负样本、未过质量、非独立划分 |
| `evidence/runtime/**/events.jsonl` | `shop_policy`×23、`shop_decision_ranking`×5、`shop_offers`×23、`shop_purchase_*`、`semantic_frame_proposal`×1346 |
| `config/user-shop-*.json` | 真 store：`bought[].decision_context`（wanted 全序 + 货架报价）与逐笔成交 |
