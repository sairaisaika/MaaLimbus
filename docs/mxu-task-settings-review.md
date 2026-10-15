# MXU 脚本任务设置审查：自动镜牢（`mirror_loop`）

## Review of the MXU script-task settings — Mirror Dungeon task

**Scope / 范围**：这是只读分析与改造提案。本文不修改任何源码、`dist/`、`evidence/runtime`，不连接设备、不启动游戏、不运行测试。
所有断言都带 `file:line`。仓库内事实源为 `assets/interface.json`（源，3.42 MB / 147,277 行）、`assets/i18n/zh_cn.json`、`assets/resource/base/pipeline/mirror.json`、`src/maalimbus/**`、`agent/recognition.py`、`tools/patch_mxu_client.py`、`desktop/mxu/**`。

**一句话结论**：11 个选项全部默认 `saved`，但 `saved` 在不同选项上分别意味着「保留保存值」「读 `user-launch.json`」「落到硬编码 CLI 默认」三种完全不同的东西；其中 4 个选项**会写盘**（改写队伍轮换、编队星光、队伍藏品偏好），而唯一能表达「我要跑几局」的选项排在倒数第 3 位、和「步数上限」并列成两个裸数字下拉框。用户抱怨的不是文案，是信息结构。

---

## 1. 现状清单 (Current-state inventory)

任务定义：`assets/interface.json:111-130`（`name: "mirror_loop"`，`entry: "MirrorTask"`，`default_check: false`）。展示顺序 = `option` 数组顺序（`assets/interface.json:117-129`），共 11 个顶层选项，全部 `type: "select"`，全部 `default_case: "saved"`。

`file:line` 缩写：`IF` = `assets/interface.json`，`MJ` = `assets/resource/base/pipeline/mirror.json`，`I18N` = `assets/i18n/zh_cn.json`。

### 1.1 顶层 11 个选项

| # | 内部名 | 界面显示名（zh） | 默认 | 真正含义 | 消费点 file:line |
|---|---|---|---|---|---|
| 1 | `mirror_team_mode` | 「队伍使用方式」`I18N:65` | `saved` | 决定**是否改写**保存的轮换：单队 → 队列写成一个槽，轮换 → 按数量取槽；`saved` 表示不写、沿用账本。**唯一没有 description 的选项** | IF:86521-86566（无 `description` 字段，见 86523-86524）；`agent/recognition.py:1467-1469`；`src/maalimbus/task_preferences.py:106-116`、`:69-103` |
| 2 | `mirror_star_source` | 「星光规则来源」`I18N:89` | `saved` | 星光（Lix 0–9）选择规则的来源：编队 / 本任务 / 自动（预算内） | IF:66802-66883；`src/maalimbus/mirror_starlight.py:17-38`、`:41-58`；`agent/recognition.py:1632-1634`；`src/maalimbus/runner.py:1314` |
| 3 | `mirror_initial_keyword` | 「初始藏品体系」`I18N:112` | `saved` | 初始藏品组（Bleed/Poise/… 共 12 系）；`saved` → 读 `user-launch.json` 的 `gift_keyword`，否则运行期默认 `bleed` | IF:67774-67923；`src/maalimbus/mirror_task_options.py:6`、`:18-21`；`src/maalimbus/runner.py:160`、`:1811`、`:2195`、`:2203` |
| 4 | `mirror_gift_search` | 「藏品搜索」`I18N:115` | `saved` | **只能关闭**。没有付费搜索通路：非 `saved`/`refuse` 的值会抛错 | IF:67925-67953（只有 saved/refuse 两个 case）；`src/maalimbus/mirror_task_options.py:22-26` |
| 5 | `mirror_shop_policy` | 「商店购买规则」`I18N:148` | `saved` | BOSS 前商店的购买规则；`learned` 不含任何模型判断 | IF:67955-67994；`src/maalimbus/shop_settings.py:45-47`、`:282-295`；`agent/recognition.py:1640-1643` |
| 6 | `mirror_shop_refresh_limit` | 「商店刷新上限」`I18N:152` | `saved` | 每次进店的**普通刷新次数**；下拉只有 0/1/2/3/5，**没有 4**；解析器接受 0..5 任意整数 | IF:67996-68069；`src/maalimbus/shop_settings.py:50`、`:56`、`:99-108`；`src/maalimbus/runner.py:2542` |
| 7 | `mirror_shop_coin_reserve` | 「商店金币保留」`I18N:159` | `saved` | 每次进店**不花掉的**金币下限；解析后默认 500（不是 0） | IF:68070-68143；`src/maalimbus/shop_settings.py:51`、`:74`；`src/maalimbus/runner.py:1956`、`:2542` |
| 8 | `mirror_run_bounds` | 「本次运行步数上限」`I18N:116` | `saved` | **一个启动窗口的步数预算**，不是局数；`saved` 落到硬编码 400 | IF:68218-68280；`agent/recognition.py:1262`；`src/maalimbus/runner.py:3010-3014`；`src/maalimbus/mirror_task_options.py:27-30` |
| 9 | `mirror_run_count` | 「本次运行镜牢次数」`I18N:120` | `saved` | 本次启动要交付的**完整局数**（五层通关+领奖+回大厅才计数）；`saved`/0 都表示「未指定」 | IF:68144-68217；`src/maalimbus/mirror_task_options.py:12`、`:31-36`；`src/maalimbus/runner.py:1393-1407`、`:2846-2859` |
| 10 | `mirror_preferences` | 「队伍藏品与主题包偏好」`I18N:123` | `saved` | 编辑并**保存**所选队伍的藏品允许/屏蔽、主题包权重（9 个子项） | IF:68333-68359（`edit` case 的 9 个子项见 IF:68360）；`src/maalimbus/mirror_preferences.py:6-18`、`:21-68`；`agent/recognition.py:1626-1631` |
| 11 | `mirror_battle_assignment` | 「战斗自动配卡」`I18N:136` | `saved` | 用游戏的胜率/伤害自动配卡按钮；`observe` 会停 | IF:68281-68332；`src/maalimbus/mirror_task_options.py:13`、`:15-17`；`src/maalimbus/runner.py:2419`、`window.py:978-994` |

### 1.2 条件显示的子选项（只在父 case 被选中时出现）

| 父选项 | 出现条件 | 子选项（按声明顺序） | 默认 | 消费点 file:line |
|---|---|---|---|---|
| `mirror_team_mode` | 选 `single` | `mirror_single_team`「使用队伍」 | **`"2"`** | IF:86540-86542、:56068-56071；`MJ:5089-5095`（`slot: 2`）；`task_preferences.py:109-110` |
| `mirror_team_mode` | 选 `rotation` | `mirror_queue_count`「轮换队伍数量」→ 再展开 `mirror_queue_1..40` | **`"5"`** | IF:56554-56556、:56515-56518；`MJ:5097-5103`（`count: 5`）；`task_preferences.py:111-114` |
| `mirror_star_source` | 选 `team` | `mirror_star_team_editor`「编队星光方案」 | `saved` | IF:66829-66831、:66884 |
| `mirror_star_source` | 选 `team` | ↑ 的 `edit` → `mirror_star_team_slot` + `mirror_star_team_budget` + `mirror_star_team_0..9` | — | IF:66927、:67464、:67484-67745 |
| `mirror_star_source` | 选 `task` / `auto` | `mirror_star_task_budget` + `mirror_star_task_0..9`（`auto` 另加 `mirror_star_team_editor`） | — | IF:66843-66855、:66867-66880；`mirror_starlight.py:74-89` |
| `mirror_preferences` | 选 `edit` | `slot` → `allow` → `block` → `pack` → `weight`(默认 `"75"`) → `avoid_pack` → `remove_allow` → `remove_block` → `remove_pack` | — | IF:68360、:76777、:77004、:80674、:84344、:86470、:85407、:68374、:72044、:75714 |

界面元素被项目自有补丁接管（`tools/patch_mxu_client.py`）：`mirror_star_task_N` / `mirror_star_team_N` 被隐藏、`mirror_star_*_budget` 换成 `StarCardsEditor`（`tools/patch_mxu_client.py:54-64`）；`global_team_N` 换成 `TeamBuildEditor`（`:13`、`:16-18`）。

### 1.3 「什么都不改」时实际发生什么

`MirrorLoop` 节点的 `custom_action_param` 只声明了 `directory/steps:400/interval/rounds/battle_rounds/unknown_rounds/map_tries/claim_tries/defeat_tries/defeat_accept/gift_plan/observe_only/stop_page/run_store/team:5`（`MJ:1530-1546`）—— 不含 `gift_search`、`gift_keyword`、`shop_*`、`battle_assignment`、`run_count`。其余值按以下三级回落：

| 键 | 「saved」真正落到哪 | 证据 |
|---|---|---|
| `gift_keyword` / `gift_search` / `battle_assignment` / `graces` / `grace_budget` / `shop_policy` / `shop_refreshes` / `shop_reserve_coins` | 读 `config/user-launch.json`，不存在则 CLI 默认 | `agent/recognition.py:1304-1308` |
| `steps` | `LOOP_DEFAULTS['steps'] = 400`（硬编码，**不读任何保存值**） | `agent/recognition.py:1262` |
| `run_count` | `0` = 未指定 | `src/maalimbus/runner.py:158` |
| `team` | `5`（仅当没有账本时才用；有 `run_store` 时用账本轮换） | `src/maalimbus/runner.py:159`、`:1685` |
| 商店三项的最终默认 | `manual` / 刷新 2 / 保留 500 | `src/maalimbus/shop_settings.py:74` |

即未配置安装的等效行为：**困难、胜率自动配卡、不搜索藏品、手动上限买、每次进店刷新 2 次、留 500、一次启动最多走 400 步、局数不限**。

消费链：`MirrorTask`（`MJ:5284`）→ `MainTaskAction`（`agent/recognition.py:1571`）→ 校验/写盘（`:1604-1643`）→ `MirrorLoopAction`（`:1478-1561`）→ `runner.MirrorRunner`（`:1526`）。

---

## 2. 用户视角的问题 (Problems from the user's side)

### 2.1 命名 (Naming)

| 问题 | 证据 |
|---|---|
| `mirror_gift_search`「藏品搜索」这个选项**买不到任何搜索**，只能关掉它 | 只有两个 case `saved`/`refuse`（`IF:67925-67953`）；`refuse` 之外的值抛 `ValueError('Gift search payment is not supported by task settings')`（`src/maalimbus/mirror_task_options.py:22-26`） |
| `mirror_shop_policy` 的 `learned` 中文名叫「学习（有上限）」，但解析器明确不做出任何学习判断 | `src/maalimbus/shop_settings.py:236-239`（`model_trained=False`）、`:262-272`（`decides_here=False`，无样本时回落规则） |
| 「本次运行步数上限」与「本次运行镜牢次数」都以「本次运行」开头，且相邻 | `I18N:116`、`I18N:120`；顺序 `IF:125-126` |
| 队伍选择器只显示裸数字（`1`…`40`），不显示保存队伍的**名字**，而项目已经有一个能显示名字的编辑器 | 队伍 case 标签是原始数字（`IF:56077-56081` 等）；`TeamBuildEditor` 只注入 `/^global_team_\d+$/`（`tools/patch_mxu_client.py:13`、`:16-18`），镜牢任务用的是 `mirror_single_team`/`mirror_queue_N`，不匹配该正则 |
| `mirror_run_count` 的「saved」在界面上写「不指定（走到其他上限）」，管道默认又是 `run_count: 0`，同一个意思有三个名字 | `I18N:122`；`IF:68151-68157`；`MJ:5583` |

### 2.2 顺序 (Ordering)

`option` 数组就是展示顺序（`build/mxu-interactive-source/MXU-2.7.1/src/components/TaskItem.tsx:1093` 直接把 `taskDef.option` 交给选项渲染；`:199-235` 的 `groups` 只把连续的 `switch` 合并成网格，`select` 一律保持数组顺序、一项一张卡）。当前顺序（`IF:117-129`）：

```
队伍使用方式 → 星光规则来源 → 初始藏品体系 → 藏品搜索 → 商店购买规则
→ 商店刷新上限 → 商店金币保留 → 本次运行步数上限 → 本次运行镜牢次数
→ 队伍藏品与主题包偏好 → 战斗自动配卡
```

- 「要跑几局」「跑多久」被压在倒数第 3、4 位，而这两项是用户最先决定的事。
- 最会**写盘**的选项（`mirror_team_mode`）排第 1，最容易误解的两个数字选项（步数/次数）排第 8、9。
- 「怎么花钱」的三项（5/6/7）插在「跑什么」和「跑多少」之间，不属于同一逻辑块。
- 无任何分节/小标题：`assets/interface.json` 里只有任务级 `option` 数组，PI V2 在本仓库没有可用的选项分组构造（全文只有 `task` 级 `option` 与 case 级 `option`，见 `IF:117`、`IF:66843` 等），顶层 `group` 只有 `mirror`/`daily` 两个（`IF:93-102`），且未挂到任务上。

### 2.3 默认值 (Defaults) 与「saved」的多义

- 11/11 选项 `default_case` 都是 `saved`，但 `saved` 至少指三种行为（§1.3）：保留账本、读 `user-launch.json`（8 个键，`agent/recognition.py:1304-1308`）、落到硬编码默认（`steps`=400、`run_count`=0、`team`=5）。`mirror_run_bounds` 的界面上写「跟随已有启动设置」（`I18N:113`），而它**没有任何保存值可跟**。
- 单队默认槽位是 **2**（`IF:56071` + `MJ:5093`）：用户只要把「队伍使用方式」从默认改成「单队」，下一个启动就指向 Team 2，不经过任何确认。
- 轮换默认数量是 **5**（`IF:56518` + `MJ:5101`），于是切到「多队按顺序轮换」立即隐含 Teams 1..5；这些槽若没保存，`TaskPreferences.validate` 会以 `Mirror queue must reference distinct saved teams` 拒绝（`src/maalimbus/task_preferences.py:19-21`），任务在**输入前**停止（`agent/recognition.py:1624`、`:1582-1587`）。
- `mirror_queue_21..40` 的管道默认全是 `slot: 20`（`MJ:9355-9361` 处的 `MirrorTaskQueue40.attach.slot = 20`；Q21–Q40 同值）→ 数量 > 20 且没逐个选队时会重复，同样被上面的校验拒绝。未做 UI 实测。

### 2.4 互相矛盾 (Contradictions)

- 「跟随已有启动设置」对 8 个键成立、对 `steps`/`run_count`/`team` 不成立（`agent/recognition.py:1304-1308` vs `:1262`、`src/maalimbus/runner.py:158-159`）。
- 「藏品搜索」不可开启（§2.1）。
- 同一个词「步数」在两处指两件事：任务选项「本次运行步数上限」（`I18N:116`）与 runner CLI 的 `--steps`「how many steps to walk (default: one)」（`src/maalimbus/runner.py:3401-3402`）。
- `mirror_shop_refresh_limit` 下拉没有 `4`，解析器却接受 `4`（`IF:67996-68068` vs `src/maalimbus/shop_settings.py:50`、`:56`）——属于一致性瑕疵（`docs/shop-settings.md` 已把「下拉不给 4」写成有意为之，因此不算 bug，但用户看不出来）。
- 困难模式**没有选项**：`assets/` 全域没有 `mirror_difficulty` 键（grep 无命中），难度固定由 `TaskPreferences` 默认 `hard` 决定（`src/maalimbus/task_preferences.py:59`、校验 `:17`），运行期只记录 `difficulty_gate … required='hard'`（`src/maalimbus/runner.py:2413-2414`）。用户在设置面板里无法选择、也无法看到「困难」从何而来。

### 2.5 缺说明 (Missing explanations)

- 唯一没有 `description` 的顶层选项是 `mirror_team_mode`（`IF:86521-86525` 只有 `type`/`label`/`default_case`；`assets/` 无 `mirror_team_mode_description` 键，grep 无命中）——它恰好是唯一会改写保存轮换的选项。
- 会写盘但说明不足的行为：`mirror_preferences` 的「屏蔽优先」（代码注释在 `src/maalimbus/mirror_preferences.py:52-53`，界面文案未写）；`mirror_star_team_editor` 会把 `graces`/`grace_budget` 写进队伍档案（`src/maalimbus/mirror_starlight.py:23-36`）。

### 2.6 危险 (Dangerous)

| 危险 | 机制 | 证据 file:line |
|---|---|---|
| **静默改写队伍顺序** | 选单队/轮换 → `set_mirror_queue` 同时重写 `user-task-settings.json` 与账本的 `team_slots`/`rotation` | `agent/recognition.py:1467-1469`；`src/maalimbus/task_preferences.py:92-102` |
| **覆盖编队星光方案** | `mirror_star_team_editor = edit` 直接改写所选队伍的 `graces`/`grace_budget` | `src/maalimbus/mirror_starlight.py:23-36` |
| **覆盖队伍藏品偏好** | `mirror_preferences = edit` 直接改写所选队伍的 allow/block/pack 权重 | `src/maalimbus/mirror_preferences.py:44-67` |
| **隐藏的「超 1500 就花掉」** | 一次进店仍会带走 >1500 金币时，改为把余额买在货架上；这是运行期常量，**没有任何界面字段** | `src/maalimbus/shop_settings.py:59-67`、`:254-261`（`stored_option=False`）；效果见 `src/maalimbus/runner.py:1956`、`:2542` |
| **乱花钱的默认不是 0 保留** | `saved` 解析成保留 500（不是「不设保留额」） | `src/maalimbus/shop_settings.py:74`；下拉的 `0` 标签是「不设保留额」`I18N:161` |
| **局数不限 + 400 步窗口 = 会自己开下一局** | `run_count=0` 时唯一的停止条件是 400 步；循环会继续走进下一局（每局各自记账），直到步数用尽 | `agent/recognition.py:1262`；`src/maalimbus/runner.py:2843-2845`、`:3010-3014` |
| **设置看着生效、运行时才被拒** | 队列/星光/偏好三项都在活动局上拒绝写盘，任务以 `mirror_settings_rejected` 在输入前停止 | `src/maalimbus/task_preferences.py:93-94`；`src/maalimbus/mirror_starlight.py:31-32`；`src/maalimbus/mirror_preferences.py:64-65`；`agent/recognition.py:1624`、`:1450-1461` |

**次数 vs 步数**（用户原话点名的混淆）：`mirror_run_bounds`（步数，`IF:68218-68280`，case `120/400/800/2000`）与 `mirror_run_count`（次数，`IF:68144-68217`，case `1/2/3/5/10`）在界面上都是裸数字下拉，且相邻；真正约束「跑几局」的是后者，但默认值是 `saved` → 0 → 「未指定」，于是实际约束变成前者。两者的语义边界在代码里写得很清楚（`src/maalimbus/mirror_task_options.py:31-32` 注释、`src/maalimbus/runner.py:155-157` 注释、单测 `tests/test_mirror_task_options.py:23-25`），在界面上一个字的解释都没有。

---

## 3. 想要「3 次困难镜牢 · 指定 team 2 · 不乱花钱 · 该买藏品就买 · 留钱刷新」的最小设置集

`Minimal setting set for the requested run`。困难是隐式默认，无需也无法设置（§2.4）。

| 选项 | 设成 | 为什么必须 |
|---|---|---|
| 队伍使用方式 | **单队（编辑队伍后继续使用）** | 不写这一项就沿用账本轮换，可能指向别的队（`src/maalimbus/task_preferences.py:107-108`） |
| 使用队伍 | **2** | 单队的槽位（默认已是 `2`，仍应显式确认：`IF:56071`、`MJ:5093`） |
| 本次运行镜牢次数 | **3** | 唯一的「完整局」停止条件（`src/maalimbus/runner.py:1393-1407`、`:2846-2859`） |
| 本次运行步数上限 | **2000** | 必须抬离默认 400：步数用尽时循环以步数上限停止，3 局跑不满（`agent/recognition.py:1262`；`src/maalimbus/runner.py:3010-3014`） |
| 商店购买规则 | **手动上限** | 显式固定为「按下面两个上限执行」，不依赖 `saved` 回落到 `user-launch.json`（`agent/recognition.py:1304-1308`） |
| 商店刷新上限 | **2** | 「留钱刷新」：每次进店 2 次普通刷新是运行期默认，也是可行上限之一；没有「无限刷新」（`src/maalimbus/shop_settings.py:50`、`:74`；`I18N:153`） |
| 商店金币保留 | **500**（想更省可 300） | 「留钱」的显式下限；注意 >1500 会被强制花掉（`src/maalimbus/shop_settings.py:59-67`） |
| 藏品搜索 | **不搜索（零消费）** | 唯一被允许的非 `saved` 值（`src/maalimbus/mirror_task_options.py:22-26`） |
| 星光规则来源 | **沿用已保存规则** | 不动编队档案；若要本局专用方案改选「跟随本任务」（`src/maalimbus/mirror_starlight.py:19-20`） |
| 战斗自动配卡 | **胜率配卡** | 与运行期默认一致，显式写上避免歧义（`src/maalimbus/runner.py:164`） |
| 初始藏品体系 / 队伍藏品与主题包偏好 | **保留 `saved`**（除非要改藏品） | 「该买藏品就买」由队伍偏好 + 商店决策决定，不由任务选项决定（`src/maalimbus/runner.py:1811`、`:1864-1961`） |

**「该买藏品就买」怎么落地**：购买决策来自队伍档案的 allow/block 列表与 `wanted_gifts(state['gift_plan'], settings.gift_keyword)`（`src/maalimbus/runner.py:1811`、`:2203`）加上商店决策排序（`src/maalimbus/runner.py:1864-1961`）。若目标藏品不在已保存的优先清单里，就用「队伍藏品与主题包偏好 → 编辑保存的队伍偏好 → 要编辑的保存队伍 = 2 → 新增优先藏品 = <藏品名>」，并记住**屏蔽优先**（`src/maalimbus/mirror_preferences.py:44-48`、注释 `:52-53`）。

**注意**：这条路径**没有实机验证**（§5）。

---

## 4. 改造提案 (Concrete redesign proposal)

原则：只动文案、顺序与项目自有的注入面板，不动 MXU 上游，不动运行语义。P1–P4 是低风险高收益，P5–P7 需要更多验证。

### P1 补齐/重写文案（i18n 与 description）

文件：`assets/i18n/zh_cn.json`、`assets/i18n/en_us.json`、`assets/i18n/ja_jp.json`（三份同 key 同行号，`assets/i18n/en_us.json:116`、`:120` 与 zh 对齐），以及 `assets/interface.json` 的 `label`/`description` 指针。

| 目标 | 改哪一行 | 建议 |
|---|---|---|
| 给 `mirror_team_mode` 补说明 | 新增 `mirror_team_mode_description`；在 `IF:86523` 旁加 `"description": "$mirror_team_mode_description"` | 「这里的单队/轮换会写进保存设置，并改写运行账本的队伍顺序；只在确实想换队时改。」 |
| 「步数」与「次数」解耦 | `assets/i18n/zh_cn.json:116` | 「本次启动的**步数预算**（不是局数；用完即停）」 |
| 同上 | `assets/i18n/zh_cn.json:120` | 「完成后还要再跑几**局**完整镜牢」 |
| 「藏品搜索」不再承诺搜索 | `assets/i18n/zh_cn.json:115` | 「藏品搜索（只能关闭）」 |
| `learned` 不再承诺模型 | `assets/i18n/zh_cn.json:151` | 「按规则买（有样本时微调）」或直接删掉该 case |
| 暴露隐藏的花钱上限 | `assets/i18n/zh_cn.json:160` | 在描述末尾加：「本次进店若仍会带走超过 1500 金币，脚本会把余额买在货架上。」（对应 `src/maalimbus/shop_settings.py:59-67`） |
| 说明困难是固定的 | 任务描述 `assets/i18n/zh_cn.json:78` | 「当前固定困难模式，不可在设置里切换。」 |

### P2 重排 `option` 数组（唯一可用的顺序旋钮）

文件：`assets/interface.json:117-129`。建议顺序改为「队伍 → 跑多少 → 怎么花钱 → 战斗 → 偏好」：

```
mirror_team_mode, mirror_run_count, mirror_run_bounds,
mirror_shop_policy, mirror_shop_refresh_limit, mirror_shop_coin_reserve,
mirror_battle_assignment, mirror_initial_keyword, mirror_gift_search,
mirror_star_source, mirror_preferences
```

（`mirror_preferences` 会写盘，放最后；`mirror_star_source` 的子项会撑开面板，也靠后。）

### P3 默认值

| 项 | 现状 | 建议 | file:line |
|---|---|---|---|
| `mirror_run_bounds` 默认 | `saved` → 硬编码 400 | 保持 `saved`，但把 case 标签写成代价可读的形式（「一局（约 400 步）」「三局（约 1200 步）」），或把 `LOOP_DEFAULTS['steps']` 与 `mirror_run_count` 挂钩 | `IF:68218-68280`；`agent/recognition.py:1262` |
| `mirror_run_count` 默认 | `saved`（0 = 不限） | 保持 `saved`，但文案必须写清「不限」意味着「步数用尽才停」 | `IF:68148-68157`；`src/maalimbus/runner.py:158` |
| `mirror_shop_coin_reserve` | `saved` → 500 | 保留 500（与经济口径一致），但让界面能看到「1500 上限」 | `src/maalimbus/shop_settings.py:74` |
| `mirror_shop_refresh_limit` | 下拉缺 `4` | 可选：补一个 `4` case 使下拉与 0..5 的接受范围一致 | `IF:67996-68068`；`src/maalimbus/shop_settings.py:50` |

### P4 让队伍选择器显示**队伍名**（最高收益项）

现状：`mirror_single_team` / `mirror_queue_1..40` / `mirror_preference_slot` / `mirror_star_team_slot` 都渲染成裸数字下拉（`IF:56074-56081` 等），而项目已经有一个按名字渲染的编辑器 `TeamBuildEditor`，只是正则不匹配这些键（`tools/patch_mxu_client.py:13`、`:16-18` 只匹配 `/^global_team_\d+$/`）。

改法（项目自有补丁，不动上游）：在 `tools/patch_mxu_client.py:54-64` 已有的 `OptionEditor` 包装里，把 `/^mirror_(single_team|queue_\d+|preference_slot|star_team_slot)$/` 也纳入 MaaLimbus 分支，渲染一个带名字的下拉；名字来源与 `TeamBuildEditor` 相同（`config/user-team-profiles.json`，`src/maalimbus/storage.py:69-95` 的 `ProfileStore`；`desktop/mxu/TeamBuildEditor.tsx`）。同时给 `mirror_queue_N` 加一句「按顺序第 N 队」的前缀提示。

### P5 分组与小节

PI V2 在本仓库没有选项分组构造（§2.2），因此两条路：

1. **补丁路径（推荐）**：`tools/patch_mxu_client.py:16-18` 已经在替换 `function TaskOptionCard(...)`，可以在此基础上为 `projectInterface.name === 'MaaLimbus'` 的 `mirror_loop` 任务渲染小节标题（「队伍」「跑多少」「买卖与花钱」「战斗与偏好」）。这是本仓库既有机制（`StarCardsEditor`、`TeamBuildEditor`、`RotationPanel` 都走这条路）。
2. **协议路径（次选）**：沿用 case 级嵌套，把商店三项挂在 `mirror_shop_policy != saved` 之下——会改变语义（`saved` 时看不到三项），需先确认 `agent/recognition.py:1640-1643` 的读取顺序不受影响。

顺带：`RotationPanel`（`desktop/mxu/RotationPanel.tsx`，由 `tools/patch_mxu_client.py:28-32` 注入设置页）已经展示「下次队伍」与「跳过当前队伍」，与任务里的「队伍使用方式」是同一件事的两半——建议在两个面板里互相指路，避免用户在任务卡里改队、又去设置页跳队。

### P6 危险行为的可见化

- 在 `mirror_team_mode` 的说明里写明「会改写账本队伍顺序」（P1）。
- 在 `mirror_preferences` 说明里补「屏蔽优先」（`src/maalimbus/mirror_preferences.py:52-53`）。
- 在 `mirror_star_team_editor` 说明里写明「会写进编队档案的星光方案」（`src/maalimbus/mirror_starlight.py:23-36`）。
- 商店三项的说明里补 1500 上限（P1）。

### P7 需要更多验证后才动

- 是否把 `mirror_run_count` 的默认从 `saved` 改成显式数字（例如 1）：会改变既有用户的行为，需先有实机证据。
- 是否给困难/普通加一个 `mirror_difficulty` 选项：`TaskPreferences` 已支持 `normal`（`src/maalimbus/task_preferences.py:17`），但没有任何 PI 选项承载它；加选项需要新增管道节点与 i18n。

---

## 5. 未验证项与风险 (Unverified items and risks)

1. **「跑 3 局」这条路径没有实机证据**。`docs/wiki/zh_cn/9-execution-plan.md:115`（英文本 `docs/wiki/en_us/9-execution-plan.md:115`）写明：`run_count` 的停止路径「目前只有单测覆盖」，本窗口还没有打完一局。因此第 3 节的方案在当前证据下只能保证**设置正确**，不能保证 3 局真的跑完。
2. **步数与局数的换算没有证据**。我未能找到「一局完整镜牢实际需要多少步」的实测值，`2000` 是按「400 是一局的量级、3 局需抬升」的保守选择；建议实机一次后再定死默认。
3. **`dist/MaaLimbus/assets/` 的打包副本未检查**（约束禁止触碰 `dist/`）。本审查基于仓库源 `assets/interface.json`；若打包副本与源漂移，出货界面会与本文不符。相关工具：`tools/build_mxu_client.py`、`tools/patch_mxu_client.py`。
4. **MXU 的嵌套 case 渲染只做了源码级推断**，未运行客户端。依据：`build/mxu-interactive-source/MXU-2.7.1/src/components/TaskItem.tsx:199-235`（`groups` 只合并连续 `switch`）、`:273-310`（逐项渲染）、`:1093`（`optionKeys={taskDef.option}`）、`OptionEditor.tsx:458-464`/`:656-657`（case 标签解析）。未做浏览器或原生客户端实测。
5. **`mirror_queue_21..40` 默认 `slot: 20`**（`MJ:9355-9361` 一带）：数量 > 20 而没逐个选队会被 `src/maalimbus/task_preferences.py:19-21` 拒绝。UI 上是否真的能选到 21+，以及拒绝后的用户可见提示，未验证。
6. **轮换默认 5 队假设 Teams 1..5 已保存**（`IF:56518`、`MJ:5101`）：不满足时任务在输入前以 `mirror_settings_rejected` 停止，界面上只是「设置没生效」。未实测。
7. **`assets/i18n/en_us.json` / `ja_jp.json` 只抽查了关键行**（`en_us.json:116`、`:120-121`、`:151`）；未逐 key 审计三语一致性。`mirror_team_mode` 缺 description 是全域 grep 结论（`assets/` 无 `mirror_team_mode_description`）。
8. **困难模式不可选**是从「`assets/` 全域无 `mirror_difficulty` 键」+ `src/maalimbus/task_preferences.py:17`、`:59` 推得；未验证是否存在其它入口（例如 MXU 任务的 `difficulty` 字段）间接设置它。
9. **`mirror_star_*` 一族只做了阅读**：`StarCardsEditor` 注入（`tools/patch_mxu_client.py:54-64`）与 `mirror_starlight.py` 的读写路径都没有实际执行，`auto` 模式的预算取小逻辑（`src/maalimbus/mirror_starlight.py:55-56`）未验证。
10. **本文未运行任何测试**（约束）。相关测试仅作证据引用：`tests/test_mirror_task_options.py:23-25`（次数与步数分离）、`:28-30`（未指定局数 ≠ 0 局）、`:37-42`（拒绝付费搜索值）。

---

## 6. 证据索引 (Evidence index)

| 主题 | 位置 |
|---|---|
| 任务与选项声明 | `assets/interface.json:111-130`（`mirror_loop`，选项顺序 `:117-129`） |
| 各选项块 | `IF:86521`（team_mode）、`IF:66802`（star_source）、`IF:67774`（initial_keyword）、`IF:67925`（gift_search）、`IF:67955`（shop_policy）、`IF:67996`（shop_refresh）、`IF:68070`（shop_reserve）、`IF:68218`（run_bounds）、`IF:68144`（run_count）、`IF:68333`（preferences）、`IF:68281`（battle_assignment） |
| 子选项 | `IF:56068`（single_team，默认 `2`）、`IF:56515`（queue_count，默认 `5`）、`IF:57862`–`IF:66355`（queue_1..20）、`IF:89984`–`IF:146414`（queue_21..40）、`IF:66884`/`IF:66927`/`IF:67464`（star team）、`IF:67154`（star task budget）、`IF:68374`/`IF:72044`/`IF:75714`/`IF:76777`/`IF:77004`/`IF:80674`/`IF:84344`/`IF:85407`/`IF:86470`（preferences 9 子项） |
| 文案 | `assets/i18n/zh_cn.json:65-70`、`:89-101`、`:112-141`、`:148-165`；`assets/i18n/en_us.json:65`、`:115-121`、`:151` |
| 管道载体节点 | `assets/resource/base/pipeline/mirror.json:1526-1552`（MirrorLoop）、`:5265-5272`（TeamMode）、`:5089-5104`（SingleTeam/QueueCount）、`:5355-5361`（StarSource）、`:5555-5570`（InitialKeyword/GiftSearch）、`:5571-5586`（RunBounds/RunCount）、`:5667-5673`（BattleAssignment）、`:9363-9385`（三个商店节点） |
| 选项收集 | `src/maalimbus/mirror_task_options.py:5-37`；`src/maalimbus/task_preferences.py:106-116` |
| 写盘与校验 | `src/maalimbus/task_preferences.py:69-103`、`:13-30`；`src/maalimbus/mirror_preferences.py:6-68`；`src/maalimbus/mirror_starlight.py:17-38` |
| 运行期默认与校验 | `agent/recognition.py:1259`、`:1262`、`:1294-1315`、`:1444-1475`、`:1478-1561`、`:1564-1647`；`src/maalimbus/runner.py:147-191` |
| 局数停止路径 | `src/maalimbus/runner.py:1393-1407`、`:2843-2859`、`:2999-3021` |
| 商店语义 | `src/maalimbus/shop_settings.py:42-92`、`:99-119`、`:243-295` |
| MXU 渲染与注入 | `build/mxu-interactive-source/MXU-2.7.1/src/components/TaskItem.tsx:199-235`、`:557-645`、`:1093`；`tools/patch_mxu_client.py:13-18`、`:28-32`、`:49-65`；`desktop/mxu/RotationPanel.tsx` |
| 既有文档 | `docs/shop-settings.md`（三个商店选项的正式口径）、`docs/task-settings.md:27-38`、`:56-62`（队伍/轮换口径）、`docs/wiki/zh_cn/9-execution-plan.md:113-115`（局数未实测） |
