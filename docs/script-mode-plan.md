# 脚本模式设计 Plan v1（2026-10-06）

> 一句话：用「**一次标定 + 每层一次整图感知 + 离线决策 + 最小触碰执行**」替代「走一步看一步」。
> 所有需要图片验证的东西压缩到少数几个时间段；线上（执行期）只流动**经过验证的数字与契约**。
>
> 参考来源：LALC（D:\scripts\lalc，原型/机制）、MaaEnd（D:\scripts\maaend，工程实现）、MaaFramework 3.1/3.3 文档（框架）。

---

## 1 目标、约束与本次范围

**用户目标**：困难镜牢**五层真实领奖**、保存队伍轮换再入场、原生 Windows/ADB + PI/MXU 英日、楼层策略、预算体力兑换、邮件每日奖励、GitHub 持久化限流缓存更新、Windows 包（m00094）；先交付「最聪明、最好维护」的脚本模式设计（m01490）。

**本次范围**：只产出设计（本文档）。不改运行行为、不连设备、不点击。

**用户明确的硬约束**（写入设计前提，后续实现逐条遵守）：
- m01490：「把需要图片验证的部分尽量压缩到一个时间段去做，其他地方在线上保留一个验证后的数值接口就好，而不是走一步看一步」。
- 单控制器；活跃期只观察，不因观察超时重启；未经新授权不重开游戏、不绕过 UAC。
- 模拟触摸：随机框内落点 + 有界间隔；不重复 Enter/Confirm/Commit/receipt/refusal/toggle；不拖已选包、不切难度、不重走已完入口；不清空未知 pending 重试。
- 星光：Lix 零基 1,3,4,6 不 Enhance；`max_starlight` 100；`max_floor` 5；轮换 `5,4,1,6,2,7,3`。
- 初始礼物：Wound Clerid、Little and To-be-Naughty Plushie（已确认）。
- 数据/OBS 只作参考；**不照抄 AGPL 代码**，数据须带 source+commit+license。

---

## 2 参考项目各取什么（结论）

| 参考 | 取 | 不取 |
| --- | --- | --- |
| **LALC**（原型/机制） | JSON 状态机 + **枢纽有序候选**（`next` 顺序即优先级，用户改配置不改代码）；模板注册表的 **tag 自动派生**（`general/zh/en` 三语言分层，文件名＝游戏内文本 key）；**涂鸦防作弊的多标签地图连线识别**；`difflib` 纠 OCR；`coordinate_printer` 取坐标；`get_save_*` 自动采集范式；`node_scores` 打分寻路 | 硬编码 1280×720 绝对坐标与强制窗口；缺图即 `raise KeyError` 无降级；整包覆盖式更新；键鼠注入（我们走 ADB 触摸）；AGPL 代码/资源直接搬运 |
| **MaaEnd**（工程实现，注意：**它不是边狱巴士项目**，是《明日方舟：终末地》，3974★） | 当前最完整的 MaaFramework **工程范本**：`interface_version:2` + `"task":[]` 全靠 `"import"` 引 ~70 个 `tasks/*.json`；`assets/resource/{default_pipeline.json,pipeline/,image/,model/}`；多控制器用 `resource_adb|linux|macos/` **整目录叠加** + `attach_resource_path`；`agent/go-service`（组件分 Sink/Pre-Check/General/Business）；`Interface/` 公开节点 vs `__` 内部节点；`SceneManager` 万能跳转 + `[JumpBack]` 弹窗兜底；**ExpressionRecognition**（把多个 OCR 节点当变量算 `"{A}-{B}>=300"`）；`tools/{validate_schema.py,merge_pipeline.py,optimize_templates/,ImageCropper}`；CI（schema 校验、模板优化、i18n 同步）；MXU 驱动 + MirrorChyan 资源包 OTA | 其 AutoFight 把技能轴写死在 Go（无数据格式、改逻辑要重编译）——**我们反过来：战斗轴从第一天就是数据** |
| **MAALimbusCompany**（MaaXYZ，66★，**已弃坑** 2024-08） | 唯一「边狱巴士 + MaaFramework」项目，作为**反面教材**：只点游戏自带 `WinRate2.png` + `ToBattle.png`（推荐阵容），**零决策**，遇镜牢即崩（作者自述「镜牢的关卡选择看起来好麻烦」）；坐标写死在单个大 `daily.json`、无 schema/CI、UI 一更就全量手查；interface 仍是 **V1 格式**（MXU V2 无法接管）；要求 Render Scaling ≥ Medium + 英文 | 结论：**镜牢必须先有自己的地图/路线数据层，再谈 pipeline** |
| **AALC**（KIYI671/AhabAssistantLimbusCompany，2111★，Python，2026-09 仍活跃） | 真正做了镜牢的活跃项目，看它的镜牢流程拆分与素材组织：`tasks/mirror/{search_road,select_theme_pack,in_shop,mirror}.py`、`assets/app/status_effects/{bleed,burn,charge,poise,rupture,sinking,tremor}.png`、`assets/app/theme_packs/*.png`；**成队码** `load_team_code_in_game(team_code)` 也在这一族项目里 | 不照搬代码/资源；其是否基于 MaaFramework 两处情报不一致，**未核实前不引用其框架结论** |
| **MaaFramework** | 声明式 pipeline（`next`/`[JumpBack]`/`[Anchor]`/`on_error`/`timeout`/`rate_limit`/`pre_wait_freezes`/`max_hit`/`repeat`）；`And`/`Or` + **`roi:"前序节点名"` 相对 ROI**；`template`/`roi` 可写**数组**（兼容渲染差异）；ColorMatch 用 HSV/灰度（`method:40/6`）不用 RGB；**OCR 文本锚点 + FeatureMatch 图标锚点交叉**；`Toolkit.find_adb_devices` 自动选控制器；schema 校验 + CI | 别把 controller 押在后台 Win32 截图（MaaEnd 已弃用 `Win32-Window-Background`：「因游戏更新无法继续适配」） |

---

## 3 现有底座（不推倒重来）

- 策略/视觉层：`src/maalimbus/`（`map_vision`、`battle_vision`、`gift_vision`、`theme_vision`、`star_vision`、`team_vision`、`vision`、`policies`、`storage`、`auto_formation`、`lix_profiles`、`adb_device`、`github_cache`、`releases`、`update_stage`、`deployment`…）。
- Maa 层：`assets/interface.json`、`assets/resource/base/pipeline/mirror.json`、`agent/recognition.py`（自定义识别/动作：`limbus_map_observe`、`ThemePackDrag`、`BattleAutoAssign`、`BattleStartTurn`）、`assets/resource/base/model/ocr/{det,rec}.onnx`、`assets/i18n/{zh_cn,ja_jp,en_us}.json`。
- 数据：`assets/resource/base/{gift-catalog,theme-catalog,battle-catalog}.json`（带 source/commit/license）、`config/{user-mirror-settings,user-team-profiles}.json`。
- 证据与回归：`tools/verify_*_replay.py` 约 20 个把实机证据固化为可重放测试；`tests/` 167 passed。
- 已跑通实机链条（MuMu 触摸）：地图识别 → 点节点 → 节点面板 → Enter → 出战队伍页 → Battle! → 战斗 HUD → Win Rate 自动分配 → START 提交 → 胜利 → **返回楼层地图**。

**结论**：本次是「补三条线」——① 感知窗口与数字接口；② 锚点注册表与自检；③ 自动配队。其余按既有范式演进而非重写。

---

## 3.1 镜牢机制基线（实现前提，已核对）

- **一局 5 层**；Hard 需通关 Canto VIII；当前赛季 Mirror of Names and Spiders（2026-02-19~10-15）。Hard 清完第 5 层后可续 Parallel Superposition 到 10 层——本设计只做 5 层，续层留作开关。
- **节点**：普通遭遇／危险遭遇(硬币)／集中遭遇(异想体)／异想体事件(问号)／商店／Boss；**每层 Boss 前必有商店**；Hard 只能看前方 2 个节点。
- **领奖**：结算页点领取，**消耗 5 Enkephalin**；周加成 **3 档/周**（3 档全 Hard：750 狂气＋225 通行证 XP＋360 管理人 EXP；未通关按已清层数比例领奖）。
- **星光**：每局默认 60；通关 +层数（上限 5/层），Hard +4×层数（上限 20/层）；×(1+0.017×人格加成)。用途：Starter Buffs、主题包观察（20 起，每次 +10）、Wishmaking(5)、检索。
- **战斗**：12 人格全员出征（7 在场 + 5 后备），换层回满；界面只有 `Win Rate`/`Damage` 两个自动指派键，**没有真正的全自动开关** → 脚本就是「点胜率 → 提交回合」循环到战斗结束。
- **礼物**：开局 10 类选 1 个 II 阶；掉落率 普通 5%／异想体·集中 70%／危险 35%／Boss 必掉（Normal 3 选 1、Hard 4 选 2，可拒收）。强化 I/II/III/IV = 50/100、60/120、75/150、100/200 Cost；**融合点数** I=3/II=6/III=10/IV=15/V=30，≤10→I、11–16→II、17–24→III、≥25→IV（Super Shop 更低：≤9/10–14/15–21/≥22）。随机融合 2/3/4+ = 60/90/99%；Wishmaking 5 星光 → 90/99/99.99%。
- **Super Shop**：基线 3%，上家商店每花 20 Cost 加 1%。
- **关键词内名**（filter 与目录必须按内名对齐）：`Bleeding/Laceration`=流血、`Burn/Combustion`=烧伤、`Vibration*`(Explosion/Collapse/Echo/Chain)=震颤、`Sinking`=沉沦、**`Burst`=破裂（内名不是 Rupture）**、`Charge/ChoSuperCharge`=充能、`Breath/HoldingBreath`=呼吸法、`UnitKeyword`=阵营（黑云会/剑契组/圣愚/W 公司…）。

---

## 4 核心设计：感知窗口 + 数字接口 + 离线决策

### 4.1 四份「数字/契约」文件（线上只读这些）

| 文件 | 内容 | 谁写 | 谁读 |
| --- | --- | --- | --- |
| `anchors.json` | 锚点注册表：锚点名 → 类型（text/icon/color/rel）＋语言变体＋ROI 搜索带＋容差＋最近验证版本/哈希 | 人/采集工具 | 全部 pipeline 节点 |
| `floor-graph.json` | 本层数字模型：节点（类型+中心坐标+可达性）、连线、当前行/列、主题包名、层号 | 地图感知（每层一次） | 寻路策略（离线） |
| `inventory.json` | 玩家库存：人格名→罪人/稀有度/等级/关键词/owned 证据；`inventory_complete` 或 `descending_level_verified` 标志 | 库存扫描（每轮一次，或人工导入） | 自动配队（离线） |
| `run-ledger.json` | 运行账本：星光、狂气/Enkephalin、模块、每层奖励与耗时、战斗回合数、轮换 index | 每步追加 | 预算策略、通知、复盘 |

原则：**决策只依赖这些文件里的数字；视觉只负责「把屏幕变成数字」和「把数字变成一次点击」。**

### 4.2 时间线（把图片验证压进 3 个窗口）

```
[窗口 A · 开轮前，1 次]  anchor 自检 → 主题包库比对 → 队伍（预设/自动）→ 初始礼物
                        ↓ 产出：anchors 报告、floor 主题候选、team 计划
[窗口 B · 每层开始，1 次]  整层地图一屏解析 → floor-graph.json → 离线算路线/礼赠/商店计划
                        ↓ 层内执行期：只做「点可达节点 → 面板 → Enter」最小动作，无识别决策
[窗口 C · 战斗与结算]     HUD 关键数字 + Win Rate/START 提交；层末奖励与结算 → ledger
```

**为什么能压缩**：镜牢一层地图是**一屏全见**的（节点、连线、当前位置、主题包名全在同一帧）。因此「整层图解析」是 1 次截图 + 1 次离线计算，层内不再需要逐步看看点点。战斗同理：一次 `Win Rate` + 一次 `START`，中间不读画面。

---

## 5 抗 UI 漂移：分层锚点 + 注册表 + 自检（回应「UI 更新还能用」）

### 5.1 锚点分层（从最稳到最脆，按序降级）

1. **语义锚点（首选）**：OCR 文本（`expected` 支持正则/列表；多语言词表取自 `assets/i18n/*`）。换配色、换图标、轻微改版仍命中，且顺带确认「当前在哪一屏」。
2. **图标锚点**：FeatureMatch(SIFT) 或 `And(OCR 文本, FeatureMatch)` 交叉验证；模板 ≥64×64 且有纹理。
3. **相对锚点（跟随位移的关键）**：`roi:"前序节点名"` 把搜索限制在上一步识别框内；`target` 用前序识别框 + `target_offset`，而不是绝对坐标。
4. **形状/颜色锚点**：ColorMatch（HSV/灰度）+ 连通域几何（已在 `battle_vision.warm_control` 验证：START 真正按钮＝START 横幅下方暖色圆钮）。
5. **绝对坐标**：仅作为同版本内的一次性输入，且必须登记在 `anchors.json` 里并标注「脆弱」。

### 5.2 锚点注册表与自检（人只需修坏掉的那几条）

**已实现（2026-10-06，离线）**：`assets/resource/base/anchors.json` 是唯一的锚点真源，三类条目
- `ocr`：正则 + 中心归一化 `roi` + 阈值（沿用 `vision.find` 语义）；
- `template`：1280 基准的模板图 + `roi` + 阈值（验证时按帧宽等比放大，实测 `image/battle/win_rate.png` 在 1920 帧上命中）；
- `geometry`：控件框 + `verified_on{frame, sha256, box, source}`——**只在同一帧 sha 上算「被证明」**，换帧即报 `stale`，绝不静默沿用旧坐标。

`tools/verify_anchors.py` 把注册表逐条回放到留档观测（`evidence/runtime/**/frame-*.json` + 同名 png），打印逐锚点命中表并写 `build/anchors-report.json`；任一页的 identity 锚点在**所有**证据帧上都失配即 exit 1。注册表还带 `pending` 清单，显式列出「尚未被证明的页面」（人格 filter、结算领奖、层礼赠、商店、事件、下一层、轮换再入场），避免把「没验证」当成「已验证」。
- **已实现（2026-10-06，离线）**：`tools/verify_anchors.py --frame <png|json>` 直接对一帧（实机截图或留档帧）只校验 template/geometry 控件，逐条打印 `box / expected / drift / score`，并显式说明「裸帧没有 OCR，identity 锚点不校验」；`geometry` 锚点在别的帧 sha 上是 `skip`（本就算未证明）而不是失配，`--strict-geometry` 才把它算失败。漂移非零即 exit 1。采集侧见 §5.3。
- 维护闭环：跑自检 → 只修失配锚点 → 跑 `verify_*_replay` 回归 → 提交。LALC 的做法是「改 action 里的魔数 + 注释留痕 + 发整包」，我们的做法是「改注册表一条 + 回归」。

### 5.3 资源自动采集（把「截资源」变成一条命令）

- 沿用 LALC `get_save_*` 范式（模板匹配 + OCR 命名 → 自动裁图入库），**已实现（2026-10-06，离线）** `tools/capture_anchors.py`：人工只给名字、帧与框，例如
  `python tools/capture_anchors.py --label battle.start_label --from evidence/runtime/window-20261006-103550/frame-0044.json --box 1518,738,60,28 --page battle_hud --image-dir image/battle`
  —— 裁图→缩到 1280 基准→写 `<template-root>/image/<组>/<名>.png`→登记 `{id,kind:'template',template,roi,threshold,box,note:'captured from …'}`（`--kind geometry` 则登记 `verified_on{frame,sha256,box,source}`）。写完立刻用 `anchors.check_template` 回放这一帧，**不命中就退出 1 且不留半个文件**；重复登记要 `--force`，`--dry-run` 只校验不落盘。（`--lang` 尚未接：多语言词表仍在 `assets/i18n`，采集只登记锚点，不生成词条。）
- 主题包：`theme-catalog.json` 已有 glyphs/names；新增包自动登记（OCR 卡包名 → 查库 → 未命中则采集）。
- 分辨率：统一 720p 基准（`display_short_side=720`），MaaFramework 自动换算回原始截图坐标；录制帧一律「无损原图缩到 720p 再裁」。

---

## 6 自动配队（用户点名功能）

### 6.1 洞察：游戏内 filter 本身就是「关键词 → 人格」的权威索引

用户设想「每个罪人点进去 filter 对应属性，再选等级最高的人格」——这比维护外部人格数据库**更抗版本**：属性对应关系由游戏自己给，补丁改了也同步。

因此自动配队拆成两件事：
- **筛选（语义）**：用游戏内 filter（按属性/关键词）。
- **排序（数值）**：按等级降序 → 取第 1 张。

于是每个罪人只需「过滤 → 排序 → 点第 1 张」这一个**可复用执行原语**，几乎零 OCR。

### 6.2 执行原语与契约

```
select_best_identity(sinner, keywords):
  open_sinner(sinner)
  apply_filter(keywords)      # 需一次 UI 契约验证：filter 入口/关键词表/多选语义
  sort_by_level_desc()        # 需一次 UI 契约验证：排序控件；或已被 inventory 证明降序
  tap_first_card()
  assert(postcondition: 已选中该人格 / SELECTED 出现)
```

每个契约（filter 菜单结构、关键词项位置、排序控件、首卡位置）都登记为 `anchors.json` 条目，并在 `verify_anchors` 里回归；一旦失配，脚本**拒绝**而不是瞎点。

### 6.3 四条获取/复用队伍的路径（按性价比排序）

0. **成队码 / 已存队槽（最省，优先做）**：游戏本身有 Saved Team 槽位与**成队码**；同族活跃项目用 `load_team_code_in_game(team_code)` 一步载入。用户已有 7 支轮换队（`5,4,1,6,2,7,3`），所以「选队」通常只是**按关键词挑槽位**，不涉及逐张点卡。只有在没有合适槽位时才即时配队。
1. **排序法（最省感知的即时配队）**：证明「列表当前按等级降序」⇒ 过滤后取首卡即最高等级。需要验证一次并写入 `descending_level_verified`。
2. **一次扫描法**：逐罪人滑完列表，OCR 名字 + `Lv.` → `inventory.json`（数值），此后离线决策。代价：每轮一次、约 12 次滑动 + OCR。
3. **人工/历史导入**：沿用 `tools/import_lix_profiles.py` / `config/user-team-profiles.json`（LALC 的 `team_orders`+`team_indexes` 已导入，只是**部署顺序**，不是人格选择）。

### 6.3.1 离线人格数据源（用于规划与报告，已验证可直连）

| 源 | 内容 | 状态 |
| --- | --- | --- |
| `LocalizeLimbusCompany/LocalizeLimbusCompany`（官方许可中文包） | `LLC_zh-CN/Personalities.json`（`{dataList:[{id:10101,title:"LCB\n罪人",name:"李箱"}]}`，id 前 3 位＝罪人编号）、`BattleKeywords.json`(569)、`UnitKeyword.json`、`EGOgift_MirrorDungeon*.json`、`Skills_personality-01..12.json`、`MirrorDungeonTheme-1.json` | 活跃（push 2026-10-05），raw.githubusercontent 可直取 |
| `flaglow/LimbusStaticData` | `StaticData/static-data/personality/personality-NN.json`：`id/rank/hp{defaultStat,incrementByLevel}/resistInfo.atkResistList/attributeList/unitKeywordList/associationList/passive`；另有 `skill/`、`passive/`、`ego-gift-mirrordungeon/` | 2025-01-23 后停更，作等级/抗性/被动补充 |

两者 **id 对齐** → 可离线生成 `identity-catalog.json`（中文名＋关键词＋rank）。社区仓库无 SLA，需**自建镜像 + 定时 diff**（本仓库已有 `github_cache.py` 做限流缓存）。
中文 wiki（huijiwiki / fandom）实测 **Cloudflare 403**，不适合脚本直取；替代 `wiki.biligame.com/limbuscompany`（人格一览/E.G.O 礼物筛选/状态图鉴，可直连）。

**已实现（2026-10-06，离线、无设备）**：`tools/fetch_identity_catalog.py` 对每条 URL 用 `github_cache.GitHubState` 做 ETag 条件请求＋有界重试（原始 payload 只落 `build/upstream/state/`，不入库）；合并逻辑在 `src/maalimbus/identity_catalog.py`（纯函数、离线可测）；产物 `assets/resource/base/identity-catalog.json` 记录两个上游 commit＋日期，字段 `id/sinner/title(人格名)/name(罪人名)/rank/hp_default/hp_increment/keywords/buff_keywords/unit_keywords/association/resistances/skills`。
- 关键词由**技能里的 `buffKeyword` 反推**（递归遍历 `skill/personality-skill-NN.json` 的 `skillData`），映射：`Burst→Rupture`、`Breath→Poise`、`Bleeding|Laceration→Bleed`、`Vibration*→Tremor`、`Combustion|Burn→Burn`、`Sinking*→Sinking`、`Charge*→Charge`。抽查吻合：剑契组杀手＝Poise、Seven 南部 6 科＝Rupture、多裂纹事务所收尾人＝Charge、脑叶 E.G.O 赤瞳＝Bleed。
- **覆盖率限制**：`flaglow/LimbusStaticData` 停在 2025-01-23（commit `4e534f88…`），LLC 中文包活跃（2026-08-06）。所以 catalog 只是**离线事实快照**（当前 128 人格 / 122 带关键词），**不能**当作「玩家当前拥有的全部人格」；线上仍以游戏内 filter 为权威（§6.1）。

`src/maalimbus/auto_formation.py` 已写明严谨契约：
`choose_identity(candidates, sinner, keywords, *, inventory_complete=False, descending_level_verified=False)` —— 未证明「库存完整」或「降序已验证」时**禁止**声称最高等级；筛选 `owned and selectable and keywords & keywords and evidence and 1<=level<=100`；排序 `(-level, -|匹配关键词|, name)`。实现只需补上 `inventory.json` 的来源与证明。

### 6.4 兜底与不做

- 兜底：`config/user-team-profiles.json` 的预设（用户已存好的队伍）永远可用；自动配队失败回落到预设，不阻塞。
- 不做：改存档、读内存、注入进程（LALC 也没有；`sinner_avatar` 模型在 LALC 本地都缺失）。

---

## 7 流程编排

- **形态**：沿用既有 `assets/resource/base/pipeline/mirror.json` + `agent/recognition.py`，补 LALC 的两个好范式：
  1. **枢纽节点** `mirror_circle_center`：把「层内任意状态」汇总，`next` 是有序候选＝优先级（选卡包 → 事件 → 寻路 → 战斗 → 商店 → 层奖励 → 礼赠 → 胜/负）。
  2. **每个子节点做完回枢纽**；收尾 `mirror_victory`/`mirror_defeat` → 结算。
- **节点词汇表**（8 类，与 LALC `mirror_legend` 对齐，便于复用其数据经验）：`node_event` / `node_regular_encounter` / `node_elite_encounter` / `node_focused_encounter` / `node_abnormality_encounter` / `node_boss_encounter` / `node_shop` / `node_empty`，外加 `train_head`（当前位置）。
- **路线打分**：`node_scores`（事件优先：event 20 ＞ regular 9 ＞ elite 2 ＞ focused 1 ＞ abnormality/shop/boss 0 ＞ empty −100），可在 `config/user-mirror-settings.json` 覆盖。
- **层结束**：`胜利 → 层奖励选卡 → 下一层`；第 5 层结束 → 真实领奖（`accept_reward` 语义）→ 记账 → 下一轮轮换（`5,4,1,6,2,7,3`，正式 ledger 按轮换 index 2 接续）。

---

## 8 战斗

- **主线（当前实现，保持）**：游戏自带 `Win Rate` 自动分配 → `START` 提交 → 等稳定 → 循环。零策略、最稳、最省识别。
- **必须遵守**：每个动作**一个**（不连点）；`auto_assign_had_no_effect` 时不重试；`page_not_settled` 时先等待稳定页。
- **进阶（可选，P3+）**：技能图标金字塔匹配 + 7 类结果（dominating/favored/neutral/struggling/hopeless/unopposed/unselected）→ 只对 `hopeless/struggling/neutral` 干预；EGO 可用性用血条亮度阈值判（LALC 用 ≥110）。
- **平台差异**：Windows 端可以用 P 键（LALC 做法），Android/MuMu 端**必须**用触摸 `Win Rate` 按钮 + `START` 控件；两者共用同一份 `battle_vision`，只换输入层。

---

## 9 礼赠 / 商店 / 融合策略（数字模型）

- **机制要点**（供策略层）：礼赠有 Tier I–V + EX；融合按**融合点数**决定产出 Tier；**2 件融合约 60% 命中指定关键词，3 件约 90%**；Wishmaking（花 5 星光）把 2/3 件提升到约 90%/99%；存在**配方融合**（固定组合产出特定强力礼赠，优先于随机融合）；星光升级顺序：New Discovery → Fruits of Labor → Wishmaking/一致性 → Theme Pack Observation（首次换包 20 星光，之后每次 +10）。
- **落地**：`gift_vision` + `gift-catalog.json`（142KB）给出礼赠识别与关键词；策略层产出「买什么/留什么/合什么/是否 Wishmaking」的**计划**，执行层只做点击。
- **预算护栏**（`policies.py`）：`mirror_stop_purchase_gift_money` 门限、星光 100 上限、Lix 零基 1,3,4,6 不 Enhance。

---

## 10 人类维护工作流（「最好维护」的具体含义）

| 场景 | 人的动作 | 工具 |
| --- | --- | --- |
| 游戏更新，某页认得不对 | 跑自检，只修失配的锚点 | `tools/verify_anchors.py` |
| 新增主题包 | 无需动作（自动采集+登记），必要时命名 | 采集工具 + `theme-catalog.json` |
| 新增人格 | 无需动作（游戏内 filter 即索引） | — |
| 新增流程分支 | 改 `tasks/*.json`（声明式），不动 Python | 状态机 + schema 校验 |
| 证据固化 | 新截图入库 → 新回归测试 | `tools/verify_*_replay.py` |
| 发版 | 打 tag → CI 校验 schema + 跑测试 → 资源包 | `interface.json` + MirrorChyan |

### 10.1 直接照抄的工程纪律（来自参考项目，逐条落实）

1. **任务定义与 pipeline 实现分离**：`tasks/*.json` 只写「任务 + option + pipeline_override」，pipeline 只写原子页面节点（MaaEnd 的 `"task":[]` + `"import"` 用法即正确姿势）。
2. **`Interface/` 公开节点 vs `__` 内部节点**的边界纪律 + `SceneManager`（任意界面 → 目标场景）+ `[JumpBack]`（弹窗后回父节点）＝**把防卡死做成基建**，而不是每个分支各写一遍。
3. **ExpressionRecognition 范式**：把多个 OCR 节点当**数值变量**求布尔表达式（如 `"{star}-{cost}>=100"`），而不是在 Agent 里写 if-else —— 与本文档「数字接口」完全同构，直接复刻。
4. **ImageCropper「文件名即 ROI」**：`{name}_{x},{y},{w},{h}.png`，四边外扩 100px，`INTER_AREA` 缩到 720p 再裁 → 取图与写 roi 一步完成（并入 §5.3 的 `capture_anchors`）。
5. **CI**：schema 校验（`pipeline.schema.json` / `interface.schema.json`）、跨文件重名检查、模板优化（oxipng）、i18n 同步；资源包走 MirrorChyan OTA。
6. **多控制器用整目录叠加**（`resource_adb/` 只放差异 + `attach_resource_path`），而不是在节点里写条件分支。
7. **不押注后台 Win32 截图**（MaaEnd 已弃用 `Win32-Window-Background`：PrintWindow/SendMessage「因游戏更新无法继续适配」）→ 主路径走 ADB 前台截图（MuMu 12 EmulatorExtras）。
8. **战斗轴从第一天就是数据**（MaaEnd AutoFight 把技能轴写死在 Go，正在还债）；我们的战斗策略一律进 `battle-plan.json`，Agent 只执行。

---

## 11 目录与模块（在现有仓库上扩展）

```
assets/interface.json                     # PI v2：controller/resource/agent/import/languages
assets/resource/base/pipeline/*.json      # 声明式流水线（mirror.json 等）
assets/resource/base/image/**             # 720p 基准模板（按 tasks 名分目录）
assets/resource/base/model/ocr/**         # PP-OCR det/rec + keys
assets/resource/base/{theme,gift,battle}-catalog.json
assets/resource/base/identity-catalog.json # ★ 新增：离线人格事实（128 条，含关键词）
assets/resource/base/anchors.json         # ★ 新增：锚点注册表
assets/i18n/{zh_cn,ja_jp,en_us}.json      # 语义锚点词表
agent/recognition.py                      # 自定义识别/动作（感知窗口的入口）
src/maalimbus/*.py                        # 纯策略与视觉（可离线单测）
src/maalimbus/identity_catalog.py         # ★ 新增：静态数据合并与关键词映射（纯函数）
tools/fetch_identity_catalog.py           # ★ 新增：ETag/限流缓存抓取社区数据
tools/verify_anchors.py                   # ★ 新增：自检报告
tools/capture_anchors.py                  # ★ 新增：一次点击式采集
tools/verify_*_replay.py                  # 既有：证据回归
config/user-mirror-settings.json          # 预算/层数/星光/难度
config/user-team-profiles.json            # 轮换与队伍偏好
```

---

## 12 路线图与验收（每条都要有「验证过的数值接口」）

- **P0 五层跑通 + 真实领奖**（进行中）：地图→节点→面板→队伍→战斗→胜利→回地图已实机验证；待补「层奖励选择 → 下一层 → 第 5 层结算领奖 → 轮换再入场」。
  验收：`run-ledger.json` 记录 5 层、真实领奖证据帧、轮换 index 递增。
- **P1 自检与采集（已完成，2026-10-06 离线）**：`anchors.json` + `verify_anchors.py`（留档回放，以及 `--frame` 对当前帧的漂移自检）+ `capture_anchors.py`（一条命令采集模板/几何并登记，写完即回放，不命中不留文件）。
  验收：故意改一版 UI 后自检能列出失配锚点及其影响的 Task（`--frame` 逐条 `drift`/`MISS` 且 exit 1）；采集命令能新增一条模板并登记（`tests/test_capture_anchors.py`）。
- **P2 自动配队**：filter/sort 契约验证 + `select_best_identity` 原语 + `inventory.json`（排序法优先）。
  验收：对每个罪人给出「符合关键词且等级最高」的人格名 + 证据帧；未证明完整/降序时**拒绝**并回落预设队。
- **P3 路线与礼赠策略**：`floor-graph.json` 路线打分、商店/融合计划、Wishmaking 决策。
  - 已实现（2026-10-06，离线）：`assets/resource/base/route-policy.json`（按节点种类的可编辑权重表 + 三个修正项 `avoid_wounded` / `promote_fusion_shop` / `push_boss_on_last_floor`，种类沿用 LALC 的八类 legend）与 `src/maalimbus/route_plan.py`（`load_policy` / `score_node` / `plan_route`：只给「种类已知」的候选打分，无法打分的候选被跳过、全部无法打分则拒为 `route_kind_unknown`，同分按输入顺序定序，返回 `target`/`box`/`score`/`reasons`/`ranked`）。命名注意：**`floor-graph.json` 留给运行时每层模型**（`map_vision` 每层写出的节点/连线/行列/包名/层号），策略表另叫 `route-policy.json`。
  - 已接上（2026-10-06）：`map_vision.route_decision(header, size, *, current, cleared, candidates, policy=None, kinds=None, context=None)` 在「多个未访问候选」时改用 `route_plan.plan_route` 排序并返回 `{'next_node', 'reason': 'policy_ranked_candidate', 'plan'}`；不传 `policy` 时语义完全不变（仍是 `ambiguous_unvisited_candidates`），种类读不出的候选被跳过、全体读不出则拒为 `route_kind_unknown`，只有一个候选时仍走 `single_unvisited_candidate`（不做多余排序）。
  - 待办：① 商店/融合（Wishmaking）计划与预算门限；② 验收需要一次实机映射出的真实 floor-graph（节点 id 与种类怎么从帧里读出来是它自己的问题）。
  验收：同一层给出可复现的路线与购买/融合计划；预算门限生效。
- **P4 预算/邮件/每日 + 打包**：体力兑换预算、邮件每日奖励、Windows 包（含 OTA）。
  验收：预算不越界；每日奖励幂等（有 receipt）；打包产物可跑 `verify_deployment_replay`。

---

## 13 风险、许可与开放问题（需要拍板）

1. **许可**：`gift-catalog.json`/`theme-catalog.json` 等带 `license: AGPL-3.0` + LALC commit。若随产物分发，需评估传染性；备选是「只保留来源引用、重新自行采集」。**建议**：数据文件保留 source/commit/license 字段，发布前单独审查。
2. **游戏内 filter 能力**：filter 是否支持按状态关键词（流血/震颤…）多选、是否可排序——**必须实机验证一次**（P2 第一件事）。若不支持 → 走「一次扫描 inventory + 本地关键词表」。
3. **人格数据源**：已定位可用源（见 §6.3.1）——`LocalizeLimbusCompany`（中文名/关键词/礼物，活跃）＋`flaglow/LimbusStaticData`（rank/抗性/被动，停更），id 对齐；中文 wiki 被 Cloudflare 拦，改 `wiki.biligame.com`。需拍板：是否引入「自建镜像 + 定时 diff」这一运维负担（本仓库已有 `github_cache.py`，倾向复用）。
4. **两处情报冲突**：AALC 是否基于 MaaFramework 说法不一致，未核实前不引用其框架结论；已确认 **MaaEnd 不是边狱巴士项目**、**MAALimbusCompany 已弃坑**——实现参考的定位按 §2 表执行。
5. **分辨率/语言**：统一 720p；英日双语靠 `assets/i18n` 词表；用户 Lix 配置里 `mirror_mode hard`。
6. **风控/封号**：仅 ADB 触摸 + 截图，不注入进程；保持随机落点与有界间隔，避免高频同点连击。
7. **分发**：是否上 MirrorChyan（`mirrorchyan_rid`）；Windows 包与 OTA 由 `tools/build_windows_package.py` + `releases.py` 承担。

---

## 14 与既有文档的关系

- 本文档是**脚本模式总设计**（感知/决策/执行的分层与维护闭环）。
- 细节见：`docs/design.md`（总设计）、`docs/acceptance.md`（验收证据）、`docs/battle-planning.md`、`docs/theme-packs.md`、`docs/deployment.md`、`docs/update-staging.md`、`docs/windows-package.md`、`docs/native-control.md`。
