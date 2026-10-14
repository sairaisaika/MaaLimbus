# 商店经济类饰品的结算审计：折扣与随机返还会不会让「精确经费差」错停

范围（用户 m03919 指定的只读审计）：核对灰机（huijiwiki）经济类饰品中的**购买折扣**与**随机返还**
是否会让现有 `shop_transaction` 的「精确经费差（exact currency delta）」门禁错停，重点是
`New Release Pamphlet`（新品小册，刷新 20% 返还）与 `Prestige Card`（声望卡，购买 −30%）。
只读源码与保留真帧，给出每种机制需要的**原生证据字段**，以及「不能从买过一次推定仍持有」的约束。

本文件只做离线审计与文档：不改运行时/测试/配置/`dist`，不启 controller，不操作游戏，不提交、不推送；
不降低任何 OCR 阈值，不伪造退款已触发。根架构与实机推进由 Codex 负责。
饰品名称与效果来源见 `docs/economy-gift-review.md`。
本文的行号与判定按工作树 `5e9dfc5`（Codex 的商店购买/学习提交链最后一条）读取，只读不改。

## 结论摘要

| 机制（灰机名 / 英文名） | 影响的现有门禁 | 会不会错停 | 真帧状态 |
| :-- | :-- | :-- | :-- |
| 购买 −30%（声望卡 / Prestige Card，250） | `reserve_confirm`→`matching_purchase_question`（授权）、`reconcile_purchase`（结算） | **会停，但停在下单之前**或停在下单之后的结算；不会留下错误账 | 只有「作为货架报价」的真帧（3 个 run、5 帧）；**没有任何真帧**显示持有它时购买 |
| 刷新 20% 返还（新品小册 / New Release Pamphlet，200） | `reserve_refresh`（按钮印出值）→ `reconcile_refresh`（精确差） | **会停，且停在点击之后**（结算拒绝，`pending` 保留） | **零真帧**：全部保留帧里没有该名字 |
| 一般刷新 −30%（预约优惠券 / Pre-order Discount，250） | 同上 | 折扣若体现在按钮印出值上：**不错停**；若只在扣款生效：同「刷新返还」 | **零真帧** |
| 强化 20% 返还（返利礼券 / Rebate Token，200） | 本工程**没有强化结算路径** | 目前**不会**错停 | 真帧证明它被拾取（`GIFT_PICK`，含卡面效果原文），此后没有进过商店 |
| 强化 −30%（翻新的商品 / Renewed Merch，250）、技能替换 −30%（试用计划指南 / Trial Plan Guide，250） | 无对应结算路径 | 不会 | **零真帧** |
| 奖励卡选择数 +1（Special Catalogue，200） | 与经费无关 | 不会 | **零真帧** |

一句话：**现有门禁是 fail-closed 的**——折扣/返还只会让它停止，不会让它记错账；但「停止」本身是
实机推进的失败，而且**折扣与返还这两条路径目前都没有任何真帧**，所以现在既不能证明它们安全，
也不能证明它们会停在哪里。

## 一、现行门禁（源码事实）

购买被**同一个数字**三重锁定，而这个数字只能来自画面：

1. 预留价 = 货架徽标价。`reserve_purchase`（`src/maalimbus/shop_transaction.py:248-269`）要求
   `len(matching)==1 and observed_coins==coins and price<=coins-reserve_coins`
   （`:258-260`），其中 `matching` 就是货架行 `_shelf` 读出的 `name`+`price`；
   `pending` 里存的是 `price`、`coins`、`shelf`、`click`。
2. 授权 = 对话框自身打印的两个余额之差。`matching_purchase_question`
   （`src/maalimbus/shop_vision.py:310-334`）的 native 分支要求
   `len(names)==1 and balances and balances[0]-balances[1]==price and balances[1]>=0`
   且（传入 `coins` 时）`balances[0]==coins`（`:331-332`）；`balances` 由
   `purchase_balances`（`:274-280`）从两处窄 ROI 读出：`.639-.672` 与 `.679-.711`，y `.213-.251`。
3. 结算 = 实际经费差。`reconcile_purchase`（`shop_transaction.py:364-404`）要求
   `record['scene']=='SHOP'`、`coins == pending['coins'] - pending['price']`，且
   被买的名字从货架消失、其余选项与基线完全相同。

刷新同理：

- `reserve_refresh`（`shop_transaction.py:271-293`）用的是**按钮自己印出的 cost**
  （`refreshes()`，`shop_vision.py:218-237`，读 `REFRESH_X=(1440,1620)` / `REFRESH_Y=(140,260)`），
  要求 `refresh.cost==cost and refresh.box is not None and observed_coins==coins and cost<=coins-reserve_coins`（`:283`）。
- `reconcile_refresh`（`:406-414`）要求
  `record['scene']=='SHOP' and _coins(texts,size)==pending['coins']-pending['price']`，
  并且货架指纹必须变化、行数不变（`:411-413`）。

**完全相等是这两条结算路径唯一的成功条件**（`:411`、`reconcile_purchase` 的经费判断），
没有任何容差分支。

## 二、逐机制判定

### 2.1 购买折扣（声望卡 Prestige Card −30%）

现有购买门禁要求 `货架徽标价 == 对话框余额差 == 实际扣款`。三种子情形：

- **(a) 折扣同时体现在货架徽标与扣款上**：徽标 100、对话框 2707→2607、实际扣 100 —— 三者一致，
  **不错停**。
- **(b) 徽标仍是原价、只在扣款时打折**：徽标 144、对话框 2707→2607（差 100）——
  `balances[0]-balances[1]==price` 不成立，`matching_purchase_question` 返回 `None`，
  运行**在下单之前**停止（fail-closed：不会错误扣款，也不会错误记账）。
  在真帧上直接验证过：把价格换成 100（144 的 70%）后授权结果为 `None`（见第六节）。
- **(c) 徽标是折后价、扣款是原价**（反过来的不一致）：授权会通过（对话框差 == 徽标价），
  但 `reconcile_purchase` 会因为实际差 != 预留价而拒绝 —— 停在下单之后、`pending` 保留。

**关键限制**：授权依赖对话框的两个余额**可读**。真帧 `pi-20261012-170045/frame-0238.json`
与 `frame-0239.json` 的 OCR 把这一对并成了一个 token `27072563`（box `[1230,234,132,34]`），
`purchase_balances` 因此返回 `None`。此时 native 分支整体不可用，代码会落到旧的英文问句 schema
（`shop_vision.py:335-347`），而那一条**不校验任何金额**。这两帧里也**没有**第二条原生金额证据
（对话框内除 `Devil's Share` 与两个余额外，只有效果文本 `If the ally has Lust Affinity…`）。
即：**一旦余额对不可读，购买金额就只剩货架徽标一个来源**——这正是折扣情形下需要补证据的地方。

### 2.2 刷新 20% 返还（新品小册 New Release Pamphlet）

- `reserve_refresh` 通过（按钮印出的 cost 仍是全额），点击发出；
- 若 20% 返还触发，`_coins` 的后继值 = `coins - cost + refund`，`reconcile_refresh` 的
  `_coins == pending['coins'] - pending['price']` 不成立 → `ValueError('Fresh refresh currency delta
  and complete changed shelf not proven')` → 运行**在点击之后**停止，`pending` 留在 store 里。
- 现有的 4 条真刷新收据（第三节 3.3）**全部**是精确相等，说明这些 run 里没有返还机制在生效
  （既没有持有新品小册，20% 也没抽中并被记录）。
- 结论：这是**最可能真实发生**的错停（返还只在扣款侧，按钮印出值不变），且**零真帧**。

### 2.3 一般刷新 −30%（预约优惠券 Pre-order Discount）

`reserve_refresh` 与 `reconcile_refresh` 都以**按钮印出的 cost** 为同一来源：
若 −30% 体现在印出值上（15 → 10 之类），预留与结算都用 10，**不错停**；
若只在扣款生效，则与 2.2 相同。`-30%` 是否是印出值无法从资料断言，需要真帧。**零真帧**。

### 2.4 强化类（返利礼券 Rebate Token 20% 返还、翻新的商品 / 试用计划指南 −30%）

- 商店界面确实有强化/融合入口：真帧 `pi-20261012-173651/frame-0001.json` 里有
  `Enhance` `[218,559,90,32]`（上方 `⊕77`）与 `Fuse` / `Gifts` `[414,559,56,34]`。
- 但 `shop_transaction.py` 只有 `reserve_purchase` / `reserve_refresh` / `reserve_confirm` 与
  `reconcile_purchase` / `reconcile_refresh` 两条结算路径，**没有强化/融合的结算**，
  runner 也从不点击 `Enhance`/`Fuse`：`grep -n "enhanc\|fuse\|sell" src/maalimbus/runner.py`
  只命中 `runner.py:1232` 的 `enhance=False`（那是星规记录里的字段，与商店强化无关），
  没有任何商店强化/融合/售出的调用。
- 因此返利礼券**今天不会**让任何门禁错停。若将来加入强化结算，必须复用同一条
  「按钮印出金额 + 前后余额差」证据，并把 20% 返还显式列举为例外。

## 三、有真帧的部分（保留帧，可复现）

### 3.1 唯一的真实购买对话框

`dist/MaaLimbus/evidence/runtime/pi-20261012-173651/frame-0001.json`（记录里的 `scene` 为 `SHOP_PURCHASE`）：

| token | box | score |
| :-- | :-- | :-- |
| `Purchase E.G.O Gifts` | `[674,236,292,34]` | 0.999 |
| `Devil's Share` | `[546,579,178,34]` | 1.000 |
| `2707`（买前） | `[1230,236,53,34]` | 0.953 |
| `2563`（买后） | `[1305,235,57,35]` | 1.000 |
| `27072563`（同帧 OCR 同时给出的合并 token） | `[1230,234,132,34]` | 1.000 |
| `X Cancel` | `[710,702,156,42]` | 0.912 |
| `Purchase` | `[1092,706,128,34]` | 1.000 |

即：`purchase_balances = (2707, 2563)`，差 **144**，与货架徽标价 `Devil's Share 144` 完全一致 ——
这一帧里**没有**任何折扣在生效。

对照帧 `pi-20261012-170045/frame-0238.json` / `frame-0239.json`：`native_purchase_dialog` 为真、
`purchase_balances` 为 `None`（只有合并 token `27072563`）。这两帧在运行时被当时的构建记为
`scene=SHOP`；而**当前源码**会先把它们命名为 `SHOP_PURCHASE`（`vision.py:272-274` 的 native 分支在最前）。
记录内的 `scene` 来自当时的安装版本，不是当前源码的判定——这一点在引用帧字段时要分开。

### 3.2 声望卡只作为「货架报价」出现过

`_shelf` 在以下真帧读出 `Prestige Card price=250`（点击框在 `170045/0236-0237` 是
`[1100,585,120,90]`，在 `173651/0004-0005` 与 `174217/0001` 是 `[870,585,120,90]`，
即同一报价换过位置）：

- `pi-20261012-170045/frame-0236.json`（coins 2707）、`frame-0237.json`（coins 2707，正是购买预留帧）
- `pi-20261012-173651/frame-0004.json`、`frame-0005.json`（coins 2563）
- `pi-20261012-174217/frame-0001.json`（同店第二次进入的起始帧）

同店货架在这些帧里都完整读出六行，价格 77/205/165/155/144/250。**没有任何真帧显示声望卡被购买**
（`config/user-shop-f855ac82c2b1429aae9c747a122213b8.json` 的 `bought` 只有 `Devil's Share 144`），
也没有任何真帧显示它被持有。

### 3.3 4 条刷新 + 1 条购买：全部精确相等

用当前源码重算真收据的前后 `_coins`（命令见第六节）：

| 收据 | 印出价 | 经费 | 差值 | 精确 |
| :-- | --: | :-- | --: | :-- |
| 刷新 visit 1 #1（`pi-20261012-123906/frame-0062→0064`） | 15 | 1662 → 1647 | 15 | 是 |
| 刷新 visit 1 #2（`.../frame-0064 → pi-20261012-135557/frame-0001`） | 30 | 1647 → 1617 | 30 | 是 |
| 刷新 visit 2 #1（`pi-20261012-174217/frame-0001→0003`） | 15 | 2563 → 2548 | 15 | 是 |
| 刷新 visit 2 #2（`.../frame-0003→0005`） | 30 | 2548 → 2518 | 30 | 是 |
| 购买 Devil's Share（`pi-20261012-170045/frame-0237 → pi-20261012-174217/frame-0001`，问句帧 `173651/frame-0001`） | 144 | 2707 → 2563 | 144 | 是 |

注意同一 visit 内印出价从 15 升到 30：**按钮印出值本身会变**，所以「印出值」必须逐帧读，
不能当成常量。

### 3.4 返利礼券被拾取的真实证据（但不是返还证据）

`pi-20261012-174217/frame-0084.json`（`scene=GIFT_PICK`，`image_sha256` 前缀 `b92a9551102fb2ae`）：
卡面自带效果原文 `20% chance to get the Cost refunded when Enhancing In a Shop.`（在 `Rebate Token`
标题旁），页面另打印 `Owned`（对应 `Oracle`），与
`config/user-floor-gift-transaction.json` 中该范围的
`selected: ["Rebate Token","Oracle"]`、`picked_owned: {"Rebate Token": false, "Oracle": true}` 一致。
该次拾取后没有再进入商店（商店 store 只有 visit 1/2，均在拾取之前），因此**没有**任何返还真帧。

## 四、只有资料、没有真帧的部分

| 名称 | 效果（资料） | 真帧 |
| :-- | :-- | :-- |
| 新品小册 New Release Pamphlet | 刷新时 20% 概率返还消耗的经费 | 全部保留帧中 **0 次出现** |
| 预约优惠券 Pre-order Discount | 一般刷新所需经费 −30% | 0 次 |
| 翻新的商品 Renewed Merch | 商店强化饰品所需经费 −30% | 0 次 |
| 试用计划指南 Trial Plan Guide | 技能替换所需经费 −30% | 0 次 |
| Special Catalogue | 奖励卡可选项 +1 | 0 次 |
| 黑色账簿 Black Ledger | 战斗类（资源），与经费无关 | 0 次 |

这些条目的效果来自 huijiwiki 与 wiki.gg（见 `docs/economy-gift-review.md`），
**没有任何本地真帧**支撑其对经费门禁的影响方式。

## 五、「买过」≠「仍持有」

现有代码会把**本次 run 买过的名字**当成「已持有」写进决策上下文：

```python
owned_bought=list(state['shop_bought'])   # src/maalimbus/runner.py:2202
```

该字段随 `reserve_purchase(..., decision_context=...)` 存入 `pending`（`shop_transaction.py:265-267`），
并进入 `shop_outcomes` 的 `sample.json → context`，即它会成为价值模型的输入特征。但持有状态会变：

- 商店界面存在 `Enhance`（`⊕77`）与 `Fuse Gifts` 控件（真帧 `pi-20261012-173651/frame-0001.json`
  `[218,559]` / `[414,559]`），融合会消耗饰品；
- 灰机对「黑暗的残影」的说明是「可在商店售卖或作合成材料」，即饰品可被售出/消耗；
- 画面**自己**提供了持有标记：货架对已购买的报价打徽标（真购买收据的 `shelf_evidence` 即
  `own_purchased_badge`），`GIFT_PICK` 页逐卡打印 `Owned`（见 3.4）。

因此：持有事实必须来自**当前帧的原生标记**（货架 `purchased` 徽标、`GIFT_PICK`/`GET` 页 `Owned`），
不能由历史购买推断；`owned_bought` / `picked_owned` 只能当「本 run 曾购买/曾持有」的历史字段。
目前 runner 只有「本 run 买过什么」与「拾取时是否已持有」（`shop_bought`、`picked_owned`）这两个历史标记，
**没有**当前持有集合，所以折扣/返还在代码里根本没有被建模——门禁只看到「货架印了什么」和「余额差了多少」。

## 六、每种机制需要的原生证据字段（草案，不实现）

| 机制 | 必须读到的原生字段 | 判定式 | 缺一不可的理由 |
| :-- | :-- | :-- | :-- |
| 购买扣款 | 对话框标题 `^Purchase E\.G\.O Gifts$`、对话框内完整英文名、`balance_before`、`balance_after` | `charge = before-after`，且 `charge == 预留价`（预留价来自货架徽标） | 扣款权威是**对话框自己的两个余额**；货架徽标只是预留价 |
| 购买折扣是否生效 | 同上两个余额；另需货架徽标（或另一处价格文本）作对照 | 若 `charge != 徽标价`：先停止并记录，不得按徽标结算 | 真帧 `170045/0238-0239` 证明余额对可能被 OCR 合并成一个 token → 需要第二条原生证据 |
| 刷新扣款 | 按钮印出 `cost`、前后两帧 `_coins`、货架指纹 | `before-after == cost`（精确） | 返还只在扣款侧，印出值不体现 |
| 刷新返还（若将来允许） | 除上式外，还必须读到**返还金额本身**（横幅/浮动 `+N`） | `before-after ∈ {cost, cost-refund}` 且 `refund` 来自帧 | 真帧里没有该字段，所以现在只能停 |
| 强化/融合（若将来加入） | 强化按钮 `Enhance` + `⊕cost`、前后余额 | 同刷新 | 现无路径；返利礼券 20% 返还属此类 |
| 持有 | 货架 `purchased` 徽标、`GIFT_PICK`/`GET` 页 `Owned` | 只用于**当前帧**的决策 | 见第五节，历史购买不可当持有 |

## 七、数据缺口与建议

1. **需要两条新真帧才能定案**：(a) 持有声望卡时的一次购买对话框——看两个余额是否按 −30% 变化、
   货架徽标是否同步；(b) 持有新品小册时的一次刷新——看是否出现返还、返还额是否可读。
   可选 (c)：一次「余额对被 OCR 合并」的购买对话框，确认此时的第二证据是否存在。
2. **在拿到 (a)/(b) 之前，保持精确相等是最安全的行为**：它把不确定性变成一次停止，
   不会留下错误账（`pending` 保留、可人工核对）。不建议「先放宽再看」。
3. 若要放宽，必须是**显式枚举**允许的差值集合（例如 `{cost, cost-refund}`，且 `refund` 必须从帧中读出），
   任何未枚举的差值一律停止；**不要**引入百分比容差或近似匹配。
4. **不要为了通过而降低 OCR 阈值**：`_coins` 要求 `score >= .9`
   （`shop_transaction.py:75-80`），货架读取 `shelf_tokens` 的常规门也是 `.9`、
   仅对带价格的徽标放宽到 `SHELF_PRICE_FLOOR = .8`（`shop_vision.py:57,133-144`）。
   真帧表明 `27072563` 是 OCR 合并行为，不是阈值问题；降阈值只会让金额更不可信。
5. `runner.py:2202` 的 `owned_bought` 建议在特征说明里显式标注为「本 run 购买历史，非持有事实」，
   避免价值模型把「买过」学成「有效」。
6. 真对话框帧右上还有 `5%` `[1286,186,62,42]`（0.927）与 `Supor Shop / On Next Floor?`
   两个 token，本文**无法解释**其含义；在动经费门禁前应先确认它们与折扣/返还无关。本文不假设其含义。

## 八、复现命令（只读）

```powershell
# 1) 真收据的精确差（读 store + 前/后帧，不写任何文件）
@'
import json, sys
sys.path.insert(0, 'src')
from maalimbus.shop_transaction import _verify, _coins
from maalimbus.shop_vision import refreshes
tx = json.load(open('config/user-shop-f855ac82c2b1429aae9c747a122213b8.json', encoding='utf-8'))
for visit, v in sorted(tx['visits'].items()):
    for r in v.get('refresh_receipts', []):
        _, tb, sb = _verify(r['before']); _, ta, sa = _verify(r['successor'])
        cb, ca = _coins(tb, sb), _coins(ta, sa)
        cost = refreshes([t for t in tb if t.score >= .9], sb)['regular'].cost
        print('refresh', visit, cost, cb, '->', ca, ca == cb - cost)
for b in tx['bought']:
    _, tb, sb = _verify(b['before']); _, ta, sa = _verify(b['successor'])
    cb, ca = _coins(tb, sb), _coins(ta, sa)
    print('bought', b['name'], b['price'], cb, '->', ca, ca == cb - b['price'])
'@ | python -

# 2) 真实购买对话框的授权判定（真帧 -> 真实 Confirm；折后价 -> None）
@'
import sys
sys.path.insert(0, 'src')
from maalimbus.shop_transaction import _frame
from maalimbus.shop_vision import matching_purchase_question, purchase_balances
_, toks, size, _ = _frame('dist/MaaLimbus/evidence/runtime/pi-20261012-173651/frame-0001.json')
print(purchase_balances(toks, size))
print(matching_purchase_question(toks, "Devil's Share", 144, size, coins=2707))
print(matching_purchase_question(toks, "Devil's Share", 100, size, coins=2707))
'@ | python -
# 实测输出：balances=(2707, 2563)；144 -> [1092, 706, 128, 34]；100 -> None

# 3) 经济类名字在保留帧中的分布（0 次即「零真帧」）
#    Prestige Card: 170045/0236,0237 + 173651/0004,0005 + 174217/0001
#    Rebate Token : 174217/frame-0084 (GIFT_PICK) + 175907（4 帧）
#    New Release Pamphlet / Pre-order Discount / Renewed Merch / Trial Plan Guide / Special Catalogue: 0
```

## 附：本文引用的源码位置

| 位置 | 内容 |
| :-- | :-- |
| `src/maalimbus/shop_transaction.py:248-269` | `reserve_purchase`：预留价 = 货架徽标价 |
| `src/maalimbus/shop_transaction.py:271-293` | `reserve_refresh`：预留价 = 按钮印出 cost |
| `src/maalimbus/shop_transaction.py:364-404` | `reconcile_purchase`：精确经费差 + 名字消失 + 货架全等 |
| `src/maalimbus/shop_transaction.py:406-420` | `reconcile_refresh`：精确经费差 + 指纹变化 + 行数不变 |
| `src/maalimbus/shop_vision.py:218-237` | `refreshes`：按钮印出的 cost |
| `src/maalimbus/shop_vision.py:274-280` | `purchase_balances`：对话框两个余额的 ROI |
| `src/maalimbus/shop_vision.py:310-347` | `matching_purchase_question`：native 分支要求余额差 == 预留价 |
| `src/maalimbus/vision.py:272-279` | 场景命名：native 分支优先，其次旧 Confirm/Cancel 对 |
| `src/maalimbus/runner.py:2202` | `owned_bought=list(state['shop_bought'])`（本 run 购买历史进决策上下文） |
| `config/user-shop-f855ac82c2b1429aae9c747a122213b8.json` | 真 store：visit 1/2 各 2 条刷新收据、1 条购买 |
| `config/user-floor-gift-transaction.json` | 真拾取：`Rebate Token`（scope `f855ac82…`） |
