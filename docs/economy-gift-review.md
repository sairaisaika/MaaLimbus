# 通用经济类 E.G.O 饰品：中文/英文名称核对

范围（用户 m03084 指定的唯一离线任务）：核对灰机 wiki（huijiwiki）通用经济类 E.G.O 饰品的
中文/英文名称，重点是玩家口中的「黑卡」、`Prestige Card`、`Black Ledger` 三者**不能混为一谈**；
给出带来源 URL 的精确目录，以及一份可配置的「手动高优先级」候选数据草案。
本文件与 `build/deepseek-continuation-20261012/` 下的离线报告只做**离线取证**，不改
`runner` / `window` / `shop_vision` / `shop_transaction` / `agent`、全局配置、`dist`、游戏或 GUI，
不提交、不推送。评分与交易门禁仍由 Codex 负责。

## 经 Codex 复核：正式目录名与玩家昵称须分开

| 说法 | 是什么 | 证据 |
| :-- | :-- | :-- |
| **黑卡** | 玩家昵称；该词未出现在本次正式饰品表筛选结果中。其他论坛的同名用法不能排除玩家在这里指代黑色卡面饰品，因此不能据此断言其与镜牢无关。当前画面确有黑色卡面、完整英文名 Prestige Card 的报价。 | 见筛选证据及 `pi-20261012-170045/frame-0237.png` |
| **Prestige Card** | 灰机名 **声望卡**，价格 250，效果「商店购买 E.G.O 饰品所需经费减少 30%」。日文 wiki 同项为「プレステージカード」（汎用ギフト/コスト関連，ランクⅢ），英文效果 `Shop E.G.O Gift Purchase Cost -30%`。 | 见「经济类目录」 |
| **Black Ledger** | 灰机名 **黑色账簿**，价格 195，效果「关卡的首个回合开始时，根据敌方单位个数，随机获得相应个数的 E.G.O 资源；若参与本场战斗的属于剑契组或黑云会的友方单位不低于 4 名，则改为获得持有量最少的 E.G.O 资源」，获得方式 **肉斩骨断**（英文卡包 `Yield My Flesh to Claim Their Bones`）。它是剑契组事件饰品，**不是**商店折扣。 | 见「经济类目录」 |

声望卡与黑色账簿的名称、价格和效果不同。玩家昵称不参与机器身份匹配；运行时以实际完整英文名绑定报价，不能从昵称直接推出一个不同饰品。

## 取证方法（可复现）

1. **灰机 wiki 的通道**：`limbuscompany.huijiwiki.com` 对 `web_fetch` 返回 Cloudflare 403
   （`Just a moment…`），对共享 Playwright 浏览器同样 403，`r.jina.ai`、`api.allorigins.win`
   也不通；只有侧边栏自有浏览器（真实 Chromium）能通过。
   页面 <https://limbuscompany.huijiwiki.com/wiki/E.G.O饰品> 的饰品表由灰机自有 tabx 引擎渲染
   （`{{ask|table=Giftchoose.tabx|query=Data_Giftchoose::Gift|…}}`，共 **447 个饰品 / 569 条数据**，
   共 30 页），**不是** SMW，因此 `api.php` 的 `action=ask` 对任何 `[[Data_Giftchoose::Gift]]`
   查询都返回 0 行，`Data` 命名空间也不进全文索引——这正是「搜索查不到饰品」的原因。
   可靠读法是使用页面上的筛选模块，再用快照读结果。
2. **筛选配方 A（回答「黑卡」）**：`饰品名称 = 黑` → 7 条：
   黑色乐谱 427、黑兽丸 - 卯 201、黑檀胸针 192、**黑色账簿 195**、黑焰烟斗 252、黑铁马胄 205、
   黑暗的残影 100。**没有「黑卡」。**
3. **筛选配方 B（回答「声望卡」）**：`饰品名称 = 卡` → 5 条：
   卡蜜拉 217、蜜拉卡 204、**声望卡 250**、口袋助记卡 201、作战批准卡 252。**没有「威望卡」**，
   也没有「黑卡」。（此前全文搜索「威望」返回 608 条均为无关页面，可互相印证。）
4. **筛选配方 C（经济类全集）**：`关键词查找 = 经费` → 11 条（下表）。这一条是本任务的主证据，
   第 2、3 条是它的交叉验证。
5. **英文侧来源**：`limbuscompany.wiki.gg` 的饰品**没有**独立条目（`/wiki/Prestige_Card`、
   `/wiki/Black_Ledger` 均 404），数据在 Lua 模块 `Module:EgoGift/data`
   （每件饰品的 `name` / `imgname` / `tier` / `cost` / `category` / `sin` / `desc`），
   归属在 `Module:EgoGiftList/data`（`p.MainGifts` / `p.ThemedGifts` / `p.ExtremeGifts` /
   `p.CursedGifts` / `p.EnchancableGifts`）。饰品图标证明了二者是两件不同饰品：
   `File:Prestige Card Gift.png` 与 `File:Black Ledger Gift.png` 同时存在。
6. **日文侧交叉验证**：<https://wikiwiki.jp/lcbwiki/鏡ダンジョン/E.G.Oギフト/汎用ギフト>（2026-10-11 更新）
   的「コスト関連」分组列出 黄金色の壺 / 意地汚いハンマー / 生存の道しるべ / プレステージカード，
   其中プレステージカード = 「ショップでのE.G.Oギフト購入コストが30%下がる」，与本目录一致。
7. **原始证据**：筛选结果截图
   `build/deepseek-continuation-20261012/economy-gift-review-huijiwiki-jingfei.png`
   （配方 C 的现场）；逐字行与失败通道记录在
   `build/deepseek-continuation-20261012/economy-gift-review-evidence.md`。

> 筛选结果可按上述配方在灰机页面上重放：打开 `E.G.O饰品` 页 → 在对应输入框填词 →
> 点「筛选」。价格列即该饰品的商店经费价。

## 经济类目录（`关键词查找 = 经费`，共 11 条）

价格取自灰机表格（`：NNN`），中文效果为灰机原文（未升级效果），英文名/英文效果取自
wiki.gg 的 `Module:EgoGift/data`（英文效果与中文逐条对齐，非翻译推测）。

| 中文名 | 价格 | 中文效果（灰机原文要点） | 英文名 | 英文效果（wiki.gg） |
| :-- | --: | :-- | :-- | :-- |
| 贪婪之锤 | 213 | 战斗胜利后，获得(阵亡敌方单位数量×3)点经费。 | Voracious Hammer | After winning a combat Encounter, gain 3 Cost for each enemy defeated. |
| 金瓮 | 180 | 战斗胜利后获得的经费增加 20%（不受开局增益与其他 E.G.O 饰品的影响）。 | Golden Urn | Gain +20% Cost after winning a combat Encounter. |
| 生存的里程标 | 182 | 通过阶层头目时，额外获得(80+该战斗参战人格数×5)点经费（不受通过战斗时获得经费增加的效果影响）。 | Milepost of Survival | Upon clearing Floor Boss: gain (80 + # of Identities participating in the Encounter x 5) Cost. |
| **声望卡** | 250 | 商店购买 E.G.O 饰品所需经费减少 30%。 | **Prestige Card** | Shop E.G.O Gift Purchase Cost -30%. |
| 翻新的商品 | 250 | 商店强化 E.G.O 饰品所需经费减少 30%。 | Renewed Merch | Shop E.G.O Gift Enhance Cost -30%. |
| 试用计划指南 | 250 | 商店技能替换所需经费减少 30%（不包括技能观测的消耗）。 | Trial Plan Guide | Shop Skill Replacement Cost -30% (excluding Skill Search fee). |
| 预约优惠券 | 250 | 商店一般刷新所需经费减少 30%。 | Pre-order Discount | Shop Regular Refresh Cost -30%. |
| 返利礼券 | 200 | 在商店进行强化时，有 20% 概率返还消耗的经费。 | Rebate Token | 20% chance to get the Cost refunded when Enhancing in a Shop. |
| 新品小册 | 200 | 在商店进行刷新时，有 20% 概率返还消耗的经费。 | New Release Pamphlet | 20% chance to get the Cost refunded when Refreshing in a Shop. |
| 小凤玩偶 | 600 | 通过阶层时使拥有的经费变为 1.5 倍；每拥有 1 个饰品使自身造成的伤害 +0.5%（最多 +100%）；每拥有 20 个饰品，回合开始时自身获得 1 层强壮（最多 10 层）。获得方式：凤·皇。 | *（英文名未确认）* | *（未确认）* |
| 富 | 999 | 所有饰品的购买与强化费用固定为 1；每拥有 500 点经费，使全体友方单位获得 1 层攻击等级提升（最多 20 层）。获得方式：特殊事件。 | *（英文名未确认）* | *（未确认）* |

与商店经济相邻、但**不含「经费」字样**因而不在上表内的两条（列出以免遗漏）：

| 中文名 | 价格 | 中文效果 | 英文名 | 英文效果 |
| :-- | --: | :-- | :-- | :-- |
| *（未确认）* | *（未确认）* | 遭遇战奖励卡的可选张数 +1 | Special Catalogue | Number of Encounter Reward Card Choices +1 |
| 黑暗的残影 | 100 | 视作 1 级 E.G.O 饰品，可在商店中进行售卖或作为合成材料使用。获得方式：重复获得同一件饰品。 | *（未确认）* | *（未确认）* |

## 候选数据草案（手动高优先级，配置化）

草案文件：`build/deepseek-continuation-20261012/economy-gift-priority-candidates.json`。
它**只是一份数据**，在被 Codex 接入评分与交易门禁之前完全惰性；它
（1）不覆盖「体系（关键词）」分块的优先级，（2）不动硬保留额与刷新上限，
（3）只对商店里已经出现的报价生效，不新增购买动作，
（4）每条候选都带 `effect_verified` 标记——没有效果数据的饰品只作为**名称锚点**列出，
不编造任何收益。

建议的排序思路（草案里按此给出 `suggested_rank`，仅作候选，不构成结论）：

1. 声望卡（Prestige Card）：购买成本 -30%，是所有经济饰品里对「花钱」最直接的一条；
2. 翻新的商品 / 试用计划指南 / 预约优惠券：分别对准强化、技能替换、普通刷新三笔支出；
3. 金瓮 / 贪婪之锤 / 生存的里程标：把战斗与阶层推进转成经费，越早拿到收益越大（三者均为通用饰品）；
4. 返利礼券 / 新品小册：概率返还，属次级；
5. 小凤玩偶 / 富 / Special Catalogue / 黑暗的残影：数据未齐或场景特殊，只登记名称与已知效果。

**没有效果数据的一律不排序**（例如上表里英文名未确认的两条），这正是用户的硬约束。

## 数据缺口（明确标注，不填补）

1. **中文名是社区译名，不是官方译名**：《边狱公司》未在中国区发行（灰机页脚：「不包括中国区域」），
   所以中文名来自各 wiki 的翻译，**不同 wiki 会不一样**。同一件 Milepost of Survival：
   灰机作「生存的里程标」，bilibili wiki 作「生存的路标」；Voracious Hammer 两边都作「贪婪之锤」。
   `Prestige Card` 在 bilibili wiki 的 89 条饰品里没有对应页面，所以「声望卡」只有灰机一个中文来源。
2. **小凤玩偶 / 富 的英文名未确认**（`关键词查找 = 经费` 只给中文侧；wiki.gg 的对应条目未逐一核对）。
3. **Special Catalogue / 黑暗的残影 的中文（前者）/ 英文（后者）名未确认**；
   Special Catalogue 的中文名不在「经费」结果里，黑暗的残影的英文名未核。
4. **效果文本是「未升级效果」**：灰机的筛选查询取的是 `?desc=未升级效果`，
   强化（++）后的数值不在本目录内。
5. **「黑卡」的真正指代未定论**：能确定的是灰机没有任何叫「黑卡」的饰品，
   且该词在 NGA 语境里指向抽卡/补偿券；但「玩家说的黑卡」到底是哪一个具体物件，
   属于待用户澄清的开放问题，本目录不替它指定 E.G.O 饰品。
6. 灰机 `Data:Giftchoose.tabx` 原始 JSON 无法整篇读出（侧边栏快照文本约 4K 字符上限），
   所以本目录由**筛选 + 快照**逐条取证，而非解析原始数据；行数与「已加载 569 条数据」的口径一致。

## 来源

- 灰机 wiki 饰品页（筛选模块）：<https://limbuscompany.huijiwiki.com/wiki/E.G.O饰品>
- wiki.gg 饰品数据模块：<https://limbuscompany.wiki.gg/wiki/Module:EgoGift/data>、
  <https://limbuscompany.wiki.gg/wiki/Module:EgoGiftList/data>
- wiki.gg 饰品列表页：<https://limbuscompany.wiki.gg/wiki/List_of_E.G.O_Gifts>
- 日文 wiki 汎用ギフト：<https://wikiwiki.jp/lcbwiki/鏡ダンジョン/E.G.Oギフト/汎用ギフト>
- bilibili wiki（中文对照，89 条）：<https://wiki.biligame.com/limbuscompany>
