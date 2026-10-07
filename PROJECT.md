---
type: Project
title: MaaLimbus
tags: [project, maaframework, windows-native, limbus-company, mirror-dungeon]
---
# MaaLimbus

MaaFramework Win32 controller + ProjectInterface V2 + MXU + Python Agent.
Goal: Hard Mirror Dungeon floors 1–5, verified rewards, saved-team rotation and repeat;
then budgeted Enkephalin conversion/refill, mail and daily missions. English/Japanese.

## Latest continuation: 2026-10-07 15:40 local
- **从大厅驱动一局、盯停机点的结果：抓到三个真停机点，全部修掉**（用户的当前指令 m12942）。
  1. **`GIFT_GET → GIFT_SEARCH` 被判成 `unexpected_successor`（提交 `030c777`）**：起始礼物的 GET 提示点掉后紧接的是可选礼物搜索，而计划的后继表里没有它——同一发点击在早先窗口能过，只是因为 settle 窗口**恰好**抓到中间页；这次是 `late_observation`（`build/window-run-continue-2.json` step 71）。已把 `GIFT_SEARCH` 列进 `GIFT_GET` 的 expect 并注释记下这次失败。
  2. **账本在通关时什么都没记（提交 `a961044`）**：`build/window-run-continue-2.json` 里 step 52 `BATTLE_VICTORY → RUN_CLAIM`、53 领奖、54 弹窗 Claim、55 弹窗 Confirm → 回结算页，之后回大厅并**又开了一局**，但 `ledger_events` 全空、rotation 一动不动。真因：旧规则要求「五层都已入账」才认 `RUN_CLAIM` 是最终胜利，而 **floor 5 永远无法先入账**（地图页靠「站在 floor n」证明 n-1 清除，没有 floor 6 可站）。现在结算页先settle `floor_clear 5`，再在同一个循环的下一轮 settle `final_victory`；窗口改成**反复追问直到该页不再settle任何东西**（`record_ledger_event` 返回列表、报告字段 `ledger_events`），账本自己仍然守顺序（1..5 → victory → reward → entry_returned，最后一步才旋转）。
  3. 上一轮的团灭页与冷启动（见下）。**401 passed**。
- **实机（`--run-store`，从大厅起）**：`build/window-run-from-home.json`（159 次点击）→ `build/window-run-continue-1.json` → `build/window-run-continue-2.json`：从 HOME 一路打到 **BATTLE_VICTORY → RUN_CLAIM → RUN_REWARD_DIALOG → RUN_REWARD_CONFIRM → HOME → 又进场开下一局**（`STAR_GRACES`/`STAR_CONFIRM`/`INITIAL_GIFTS`/`GIFT_GET`/`GIFT_SEARCH` 都实机过了一遍）。账本 `active run 8de51ee3 team 4 floors=[1,2,3,4]`：那一局的五层已通，但结算事件因上面第 2 条而丢失，所以 rotation 当时没动；修正后的窗口会把当前这一局的结算记全并让 rotation 前进到 `team 1`。

## Prior continuation: 2026-10-07 14:00 local
- **用户的当前指令（m12942）**：从零开始驱动脚本打镜牢，我只负责看它卡在哪里、结合网络资料完善脚本。
- **冷启动打通（提交 `98db0dc`）**：`--flow launch` 过去被 `src/maalimbus/adb_preflight.py::foreground()` 拦住（客户端不在前台就抛 `RuntimeError('Limbus is not the uniquely identified foreground app')`）。现在新增 `foreground_any()`／`adb_device.foreground_any_of()`：**只有首个流程步是 `start_app` 的会话**才允许读「当前是谁在前台」并记进 `foreground_before`／`launched_by_flow`，由 Maa 自己的 start-app（绝不用桌面启动器）把游戏拉起来；其它会话仍是严格前检。实机：Android 桌面 → `start_app` → `TOUCH TO START` [846,810,222,41] 0.95 点掉 → `LUNACY` 出现 → `Confirm` 弹窗清掉 → 停在 `HOME`（前检期间 `clicks_sent` 为 0）。
- **团灭页（提交 `41ac26d`＋`b8324d0`）**：5 层 boss 把 12 人全灭后，游戏弹出「Floor In Progress 5/5 / All participating Sinners have been killed. / Remaining Units: 0/12」＋三行选择（Return to Stage Select／Retry Stage／Accept results…）＋ Confirm。新页 `BATTLE_DEFEAT` 默认选 **Retry Stage**（唯一能让这一局活下去的输入），而且**有界**（`--defeat-tries`，默认 2）；两个「放弃这一局」的行只登记、永不自动点；重试次数在 **Confirm 落地后**才 +1。**400 passed**，anchors **41 页 0 broken**。
- **实机从大厅驱动一整段（`build/window-run-from-home.json`）**：`HOME→DRIVE→MIRROR_ENTRY→ENTRY_CONFIRM→DUNGEON_TEAM（按账本选队）→STAR_GRACES（买 5 张）→STAR_CONFIRM→INITIAL_GIFTS→GIFT_GET→GIFT_SEARCH(refuse)→GIFT_SEARCH_FORGO→THEME_PACKS→MAP→…` 一路推进，159 次点击内**没有一次非设计内的停机**；窗口只是把 150 步预算用光（`passed: False` 是预算用尽，不是失败）。
- **轮换账本实机生效**：这一局由 `config/user-run-ledger.json`（`slots=[5,4,1,6,2,7,3] rotation=1 -> team 4`）驱动，报告的 `run_ledger` 记 `team: 4`；站上 floor 2 时账本自己记下第一条 `floor_clear: 1`（`active run 8de51ee3 team 4 floors=[1]`）。
- 教训：`tools/verify_anchors.py` 用默认参数跑（`41 page(s), 0 broken`）；手动传 `--template-root .` 会让 `battle_hud`/`tutorial` 的 evidence 解析失败并报 2 broken —— 那不是真回归。

## Prior continuation: 2026-10-07 04:25 local
- **实机 run114/115/116（`--stop-page HOME`）**：run114 从 floor 4 打到 floor 5 后停在 `page_unreadable_after_waiting`，run115/116 接着把 floor 5 的几场战斗打下去（每步都 `passed: true`，只有地图候选按设计轮换时记 6 次 `map_click_opened_no_panel`）。run115 用满 60 步预算（报告顶层 `verified_clear: False`、exit 1 ＝预算用尽而非失败），所以窗口的步数上限就是长局的唯一约束。
- **header 又一种 OCR 形态（提交 `7abfec1`）**：`ExploringFloor5`（词与 Floor 之间**没有空格**）此前不被 `HEADER_PATTERN` 接受 ⇒ 页面判 UNKNOWN。现在分隔符可选、floor 词用惰性 `\w{3,5}?`（贪婪会把 `Floor5` 整个吃掉、floor 号丢成 None）；测试钉 `evidence/runtime/window-20261007-034308/frame-0198.json`。
- **`--stop-page NAME`（提交 `c273643`）**：镜牢结算后游戏会自动回大厅并再次进场，长窗口会在调用者还没决定前就用旧队开下一局。现在命中该页即 `stopped: stop_page_reached` 并交回控制权（这一步也把「DUNGEON_TEAM 的队槽每次从账本现读」的改动带上，避免跨局用已退役的队）。
- **账本可重播种（提交 `0203482`）**：`seed_run_store(..., overwrite=True)` 只允许覆盖**从未记过任何东西**的账本（有 active run 或任何回执就仍拒绝），`tools/run_ledger.py seed --force` 走这条路。这是为了修「一局在接线之前打完、玩家顺序已经前进，而账本还指着旧队」的局面。
- **Windows 包：五个硬地板的证据可以申报了（提交 `49cfa6d`）**。`tools/build_windows_package.py --verified-dungeon-clear` 才把 `clear_evidence`（默认 `docs/acceptance.md`，带 sha256）写进 `build-info.json`，否则 `pending` 里保留 `full five-floor loop`。三个输入归档（MXU v2.5.1、MaaFramework v5.12.2、MXU 源码）都已在本机并逐一核对哈希，重出一次构建即可（产物落在 `build/windows-package-<uuid>/`，`dist/` 从未产出）。
- 全量测试 **398 passed**；`tools/verify_anchors.py` **40 page(s), 0 broken**。
- **待办**：等这一局（team 5）在大厅交回 → `tools/run_ledger.py seed --slots 5,4,1,6,2,7,3 --rotation 1 --force`（对齐到 team 4）→ 带 `--run-store config/user-run-ledger.json` 跑一整局，验证 `entry_returned` 之后 rotation 自己前进一格。

## Prior continuation: 2026-10-07 03:40 local
- **实机：地图卡死的两个真因都修掉，闭环重新稳定跑通。** `build/window-run111.json`（24 步）与 `build/window-run112.json`（30 步，`steps 32 / clicks 32`）都是「地图→节点面板→出战编队→战斗（Win Rate／START 交替）→奖励卡→层礼物→主题包」再回地图，没有再出现 `no_candidate_node_observed` 或 `page_unreadable_after_waiting`。
- **`MapProgress`（提交 `6f92953`）**：run110 在 floor 3「To be Cleaved」连出 7 次 `map_click_opened_no_panel`，日志里真正点过的 target 只有 `[1010,103]`/`[681,441]`/`[748,416]`/`[1819,709]`，而 `[681,441]` 与 `[748,416]` **交替重复 8 次**、可达的「?」节点 `[303,708]` 一次都没点到。真因是 header 的 floor 读数在 `3 / None / 3` 之间抖动（OCR 丢 token），旧代码 `if floor != map_floor:` 每次抖动都清空「已试过」。新 `src/maalimbus/map_progress.py::MapProgress`：**只有具名且不同的层号才开新一层**，`None` 读数保留层号与已试点；测试 `tests/test_map_progress.py` 三条。
- **header 尾部截断（提交 `6220f97`）**：run111 停在 `page_unreadable_after_waiting` 时，`evidence/runtime/window-20261007-030756/frame-0093..0100.json` 每帧都把标题读成 **`Explorin`**（掉尾字母 g、且没有 floor token），`HEADER_PATTERN`/`HEADER_LABEL_PATTERN` 都要求 `Exploring` ⇒ `map_header()` 返回 None ⇒ 页面判 UNKNOWN。现在两者共用 `HEADER_WORD = r'(?:Explori\w{0,3}|Before\s+Entry)'`；pack 行仍是身份闸门。测试 `tests/test_map_vision.py::test_the_map_survives_a_label_whose_tail_ocr_dropped`（钉 frame-0096）。
- **轮换账本接线（提交 `f70b204`）**：以前窗口永远带 `--team 5` 且不记账，轮换不自增。新增 `src/maalimbus/run_wiring.py`（纯函数，把「观察到的页」映射成**唯一**该记的账本事件：站在 floor n 证明 floor n-1 已清除、`RUN_CLAIM` 是最终胜利（需五层齐）、`RUN_REWARD_CONFIRM` 的 Confirm 是奖励到手、`DUNGEON_TEAM` 的 Confirm 是再入场；绝不上报会被账本拒绝的事件）、`tools/window_step.py --run-store`（用账本的队槽代替 `--team`，每个事件都带**它所来自的帧**做证据；被账本拒绝就记 `run_ledger_refused` 而不打断窗口）、`tools/run_ledger.py`（`status`/`seed`）与 `src/maalimbus/storage.py::seed_run_store`（拒绝覆盖已有账本）。已按用户口径播种 `config/user-run-ledger.json`：`slots=[5,4,1,6,2,7,3] rotation=0 -> team 5`。
- 全量测试 **390 passed**；`tools/verify_anchors.py` **40 page(s), 0 broken**。
- **待办**：用 `--run-store` 跑一整局（从大厅进场）验证轮换在结算后真的前进一格；然后才是 Windows 包（`dist/` 仍未产出）与邮件/体力兑换。

## Prior continuation: 2026-10-07 03:00 local
- **实机里程碑：一局镜牢从开局打到五层通关、领奖、再入场、第二轮已开打。** `build/window-run104.json`（领奖）、`build/window-run105.json`、`build/window-run106.json`（领奖→大厅→Drive→镜牢入口→确认入场→轮换队槽位→等级警告→星辉 Grace→起始礼物→放弃礼物搜索→主题包→地图→节点→出战编队→部署→战斗→回地图，30 步全 passed）。结算页是 "Exploration Complete"（Floor1..Floor5 各 6/6、Total Progress 100%、Starlight 15、Net Amount 7,556）。
- **这一段新命名的页（都带 anchors 页、计划分支与测试）**：`BATTLE_TIP`（点到技能卡弹出的 "Skill Effects" 说明浮层，提交 `b18ce58`）、`BATTLE_VICTORY`（'Victory' + 'EX-CLEAR'，自己不会消失，提交 `208866c`）、`RUN_CLAIM`（结算页四词同帧：Exploration/Complete/Total Progress/Claim，只领奖绝不翻页，提交 `6f8aae9`）、`RUN_REWARD_DIALOG`（'Exploration Reward' 弹窗，提交 `08526bb`）、`RUN_REWARD_CONFIRM`（弹窗 Claim 之后的 "Claim the rewards?" 确认，Cancel 进 `FORBIDDEN_CONTROLS`，提交 `52e5152`）。
- **`map_clicks` 排序修复（提交 `7a17842`）**：run107 在地图 "The Forgotten"（floor 1）连点四个**抬升的徽章框**（`(578,14)`/`(194,334)`/`(232,14)`）而面板一直不开；该层唯一可走的是红色「?」六边形，它的自身图标被读在 `(1087,409)`，手工 1920 空间点 `(1080,428)` **确实打开了节点面板** ⇒ 直接读自帧的 `lit_icon` 现在排在徽章抬升（`node_away_from_player`）之前。测试 `tests/test_map_vision.py::test_the_offered_question_node_outranks_the_lifted_badge_boxes`（钉 `evidence/runtime/window-20261007-023156/frame-0053.png`）。
- **循环守卫教训**：逐页守卫（`guard_page`）在页面每次跳变时清零，所以「`RUN_REWARD_DIALOG ↔ RUN_CLAIM` 来回跳」这种族内回环它看不见——新增 `CLAIM_FAMILY` 与 `--claim-tries`（默认 6）按族计步；`LOOP_GUARD_EXEMPT_REASONS` 只豁免「按用户规则必须连点同一面板」的剧情步。任何豁免都必须配一个步数预算，否则一次无效连点会烧掉整轮（run91 曾空点 40 步）。
- 全量测试 **378 passed**；`tools/verify_anchors.py` **40 page(s), 0 broken**。

## Prior continuation: 2026-10-06 13:20 local
- **管道场景自检（离线，可测）**：新增 `tests/test_pipeline_scenes.py`——冻结管道里 21 个 `limbus_scene` 场景名，断言每个名字都被 agent 侧模块（`agent/recognition.py` ＋ `src/maalimbus/*.py`）提到（防「改名/拼错/凭空发明」这类只在实机半途才炸的错）、冻结列表与管道现状一致、以及**普通 Click/Swipe/Key 节点必须带 `max_hit`**（`Custom`/`DoNothing` 豁免：它们的边界在自己的 Python 回调里，实测有 10 个 `action: Custom` 节点确实按设计不带 `max_hit`）。全量 **302 passed**（原 299）。
- **实机侧**：本轮发过一次**有界**探针（1 步、`--map-tries 2`）确认软锁仍在：MAP 点节点 → `map_click_opened_no_panel` → 驱动如实停机，未继续点击。仍需用户手工结算/结束那一局或重启客户端。

## Prior continuation: 2026-10-06 13:00 local
- **P4 的第一块（离线、可测）：预算闸门——出厂即「什么都不许花」**
  - 新增 `assets/resource/base/budget.json`：`status: "pending"`、`module_budget: 0`、`spent: 0`、`conversion_step: 1`、`allowed_purposes: ["enkephalin_refill","module_conversion"]`，`note` 写明这是用户硬约束（模块预算 0/pending）的出厂态，**只有用户明确给额度才可把 status 改成 active 并提高 module_budget**。
  - 新增 `src/maalimbus/budget.py`：`load_budget(path)`（校验 version/status/module_budget≥0/spent≥0/conversion_step≥1/allowed_purposes 合法性，非法即 `BudgetError`）、`plan_spend(amount, *, budget, spent=None, purpose=...)`、`apply_spend(...)`（额外给出 `spent_next` 供持久化）。拒绝理由按检查顺序：`budget_not_configured`（无表或 `status != active`，**出厂态就是它**）、`budget_amount_must_be_positive`、`purpose_not_allowed`、`budget_zero`、`budget_exhausted`、`request_exceeds_remaining`、`amount_not_multiple_of_step`；全部通过才是 `within_budget` 并给出 `spent_after`。
  - 调用约定（写进模块 docstring）：**先问预算、再发输入**——一次拒绝就是「没有点击」的理由，符合「不买额度不重置」与「有界点击」。
  - 测试 `tests/test_budget.py` 7 条：出厂态/Pending/零预算/无表全部拒绝、六种非法表被拒、金额与 purpose 校验、账本触顶与超限、允许时给出应持久化的账本（拒绝时 `spent_next` 不变）、`conversion_step` 整步门、显式 `spent` 覆盖表值且表本身不被改动（纯函数）。全量 **299 passed**（原 292）；`tools/verify_anchors.py` 仍 **22 page(s), 0 broken**。
  - `docs/script-mode-plan.md` §12 的 P4 条目改为「已实现（离线）＋三条待办」（接实机兑换入口并记录 refusals、邮件每日锚点、Windows 包 OTA）。
- **实机侧**：floor 3 地图软锁**依旧**（本轮未拍帧核对以外未发任何输入）；需要用户手工结算/结束那一局或重启客户端后才能继续 P0 实机验证。

## Prior continuation: 2026-10-06 12:40 local
- **P3 接线：`map_vision.route_decision` 用策略表排序（离线，可测）**
  - `route_decision(header, size, *, current=None, cleared=(), candidates=(), policy=None, kinds=None, context=None)`：仍是「先证后选」——`map_header_not_identified` / `current_position_not_proven` / `no_unvisited_candidate_observed` / `no_unvisited_reachable_node` 四道拒绝不变；**多个未访问候选**时若给了 `policy`（`route_plan.load_policy` 的表）与 `kinds`（节点 id → 本帧读到的种类），改由 `route_plan.plan_route` 排序，返回 `{'next_node', 'reason': 'policy_ranked_candidate', 'plan'}`；种类读不出的候选被跳过，**全体读不出则拒为 `route_kind_unknown`**（仍是拒绝，不是猜）；只有一个候选时不做多余排序，仍返回 `single_unvisited_candidate`。凡不传 `policy` 的调用方（含 `tools/map_live_observe.py:120`）语义逐字不变。
  - 实机冒烟（离线喂 `{'floor':3,'pack':'Repressed Wrath'}` + 三个候选 kinds `shop/abnormality/boss`）→ `next_node='r'`、`reason='policy_ranked_candidate'`、`plan.score=3.0`，`ranked` 依次为 boss 3.0 / abnormality 1.8 / shop 1.2。
  - 测试：`tests/test_map_vision.py` 新增 3 条（策略排序并带出 `ranked`、无人读出种类时拒绝而不是排序、有种类可读时跳过读不出的并把 `regular` 选中、单候选与无 policy 路径逐字不变）。全量 **292 passed**（原 289）；`tools/verify_anchors.py` 仍 **22 page(s), 0 broken**。
  - `docs/script-mode-plan.md` §12 的 P3 待办缩为两条：商店/融合（Wishmaking）计划与预算门限、需要一次实机映射出的真实 floor-graph。
- **实机侧**：floor 3 地图软锁**依旧**（本轮只拍一帧核对：mean 11.59，与软锁期一致），未发任何输入。

## Prior continuation: 2026-10-06 12:20 local
- **P3 的第一块（离线、可测）：路线打分策略表与打分器**
  - 新增 `assets/resource/base/route-policy.json`（version 1）：按八类节点（`boss`/`elite`/`focused`/`abnormality`/`event`/`regular`/`shop`/`empty`，沿用 LALC 的 legend 分类）给权重，另加三个修正项 `avoid_wounded` 2.0、`promote_fusion_shop` 1.6、`push_boss_on_last_floor` 0.8；`note` 明说这是**可编辑的偏好表、不是游戏内部数值**。
  - 新增 `src/maalimbus/route_plan.py`：`load_policy(path)`（校验 version、权重键必须是已知种类、修正项必须是已知名字，非法即 `PolicyError`）、`score_node(kind, *, policy, context)`（返回 `{kind, score, reasons}`，未收录的种类返回 `None`）、`plan_route(candidates, *, policy, context)`（`candidates` 是 `{id, kind, box?}`；**只给种类已知的候选打分**，其余跳过；全部无法打分 → `refused='route_kind_unknown'`，空候选 → `route_candidates_empty`；同分按输入顺序定序，返回 `target/box/kind/score/reasons/ranked/refused`）。
  - **命名澄清（避免踩坑）**：`floor-graph.json` 在 `docs/script-mode-plan.md` §4 里是**运行时每层模型**（节点/连线/行列/包名/层号，由地图感知每层写一次），所以策略表另起名 `route-policy.json`；`route_plan.py` 只负责给那个模型交来的候选打分，不读像素、不发明节点。
  - 测试 `tests/test_route_plan.py` 8 条：shipped 策略覆盖全部八类且不含未知键、非法策略被拒、按分数取最高并带出 `box`、无法打分的候选被跳过且全盲时拒绝、受伤时精英被普通战反超（`wounded_penalty_2.000`）、待融合时商店反超精英（`fusion_shop_bonus_1.600`）、末层推 Boss 且同分按输入顺序、纯函数稳定性（同输入两次调用结果相同）。全量 **289 passed**（原 281）。
  - `docs/script-mode-plan.md` §12 的 P3 条目改为「已实现（离线）＋待办三条」（让 `map_vision.route_decision` 接上每层 floor-graph、商店/融合计划与预算门限、需要一次实机映射验收）。
- **实机侧**：floor 3 地图软锁**依旧**（本轮只拍了一帧核对：mean 11.67，与软锁期一致），未发任何输入；需要用户手工结算/结束那一局或重启客户端后才能继续 P0 的实机验证。

## Prior continuation: 2026-10-06 11:55 local
- **P1 自检与采集闭环补齐（离线，`docs/script-mode-plan.md` §5.2/§5.3 的两条「下一步」）**：
  - `tools/capture_anchors.py`：一条命令采集并登记锚点。`--label/--from/--box/--page`，裁图→缩到 1280 基准→写 `assets/resource/base/image/<组>/<名>.png`→登记
    `{id,kind:'template',template,roi,threshold,box,note:'captured from …'}`（`--kind geometry` 登记 `verified_on{frame,sha256,box,source}`）。
    写完**立刻回放这一帧**：不命中就 exit 1 并删掉半成品；重复 id 要 `--force`；`--dry-run` 只校验不落盘。真实帧实测
    `--label battle.start_label --from evidence/runtime/window-20261006-103550/frame-0044.json --box 1518,738,60,28 --dry-run` → `score=0.9932`、`observed box=[1518,738,60,28]`、journal sha 与 png sha 一致。
  - `tools/verify_anchors.py --frame <png|json>`：只对 template/geometry 控件跑「当前帧自检」，逐条打印 `box / expected / drift / score`，漂移即 exit 1；裸帧没有 OCR 所以 identity 锚点不校验（报告里显式写明），`geometry` 在别的帧 sha 上是 `skip`（未证明）而非失配，`--strict-geometry` 才判失败。
  - 关键坑：`anchors._pixels()` 用 `int()` 截断而不是四舍五入，所以按框算出的 roi 可能比模板**少一个像素**（表现为 `roi smaller than the template`）——采集时把 roi 远端各 pad 1 px 并在条目里另存精确的 `box`，自检的漂移就以 `box` 为准。
  - 测试：新增 `tests/test_capture_anchors.py`（8 条）与 `tests/test_verify_anchors_frame.py`（5 条）；全量 **281 passed**；`tools/verify_anchors.py` 仍是 **22 page(s), 0 broken**。
- 实机仍停在「floor 3 地图不接受节点点击」的状态（上一段记录），本轮**没有再对设备发任何输入**。

## Prior continuation: 2026-10-06 11:30 local
- 实机（MuMu / ADB 127.0.0.1:16416）在 floor 3 地图（`Exploring Floor 3` / `Repressed Wrath`）停住：
  **地图可以拖动、HUD 按钮可以点，但地图节点层不接受任何点击**（点节点后 `page_after` 仍是 MAP，无 NODE_PANEL）。
- 已排除的三种解释：坐标空间（`adb shell wm size` = `Physical size: 720x1280`、density 240 ⇒ 横屏 1280×720，
  而 Maa/证据帧是 1920×1080，正好 1.5×）、输入通道（同一页点右上「?」(1233,207) 能打开 Active Effects 弹窗，
  `--swipe` 能平移地图）、结算窗口太短（`--rounds 4 --interval 5` ≈ 20 s）。
- 实测无效：左发光节点中心与四边、玩家节点自身、大路径箭头、双击、900 ms 长按、Enter 键；
  实测有效：地图平移、`?`/`i` 弹窗、队伍按钮（打开队伍页）、入口页 ▶/◀/圆点、
  **入口页左上返回箭头 `--click-box 112,46,40,40` → `page_after=MAP`**（⇒ 那一局并没有结束，只是 Mirror Dungeon
  菜单页叠在地图之上）。
- 对照 LALC（本机 `D:\Program Files (x86)\lalc` 与 `D:\scripts\lalc`）：同类症状有专门兜底 `mirror_enter_last_week`
  （模板 `previous_session_expired`，文案 "The previous session has expired. Please claim your rewards."）→ 直接报错
  「请手动结算上周的镜牢再启动 | Please finish your Dungeon and restart」；其 `exec_mirror_select_next_node` 也是
  点节点 → 等 connecting 消失 → `node_press("enter")`，失败就回初始页。
- **按硬约束不再触碰该局**（不重启游戏、不点 `Halt Exploration`、不买/不兑换），已请用户处置；
  脚本侧维持 `no_candidate_node_observed` 停机，绝不盲点。
- 新增诊断开关 `tools/window_step.py --swipe x1,y1,x2,y2[,duration_ms]`（一次手势，与 `--click-box` 共用 before/after
  记录，`goal = 0 if (boxes or swipes)`），用于证明「地图能拖」；全量 **269 passed**。
- **联网核查（本轮补做，回答「为什么之前遗漏」）**：
  - 之前只参考了 LALC（PC 端 Python 应用），**漏掉了 Maa 官方的原生 Limbus 项目**：
    [MaaXYZ/MAALimbusCompany](https://github.com/MaaXYZ/MAALimbusCompany)（66★，最后推送 2024-08-11；`assets/interface.json`、
    `assets/resource/base/pipeline/{startup,combat,awards,daily,psychube,wilderness}.json`）——它**没有镜牢**管线（2024 年版本），
    但 `interface.json` 是 ProjectInterface V2 的原生写法，做 Windows 包（MXU/PI）时应作为格式基准。
  - 官方公告（Steam 新闻 API `ISteamNews/GetNewsForApp?appid=1973530`）核查到两条与本情况相关的：
    「Ver. 1.115.0 Known Issues Hotfix & **Save Restoration** Added」（2026-09-24）——Project Moon 为 **Canto X 的软锁**加了
    「设置 → Sisyphe 标签页底部 Restore Save」的兜底，但**只覆盖主线任务软锁，镜牢不在其列**；
    同公告还修了「某些楼层在较窄宽高比下地图被裁切」——与我们「地图能拖、节点不响应」不是同一现象。
    「Known Issues After the Oct. 1st, 2026 Scheduled Update」列出「(The Shadowed) 战斗中进度无法推进」。
  - 结论不变：镜牢卡死属 LALC 也要求人工处置的一类（`mirror_enter_last_week` → “Please finish your Dungeon and restart”），
    脚本侧继续只做「识别 + 停机」，不做任何猜测性补救。

## Prior continuation: 2026-10-06 04:35 local
- 新页面落地：**遭遇奖励卡**（`Select Encounter Reward Card`）。清掉一个节点后游戏交回一张
  「选 1 张」的奖励卡（`Selectable 0/1`），确认前必须先在卡面上点一下。这一页同时带 `X Cancel`，
  所以它必须先于通用 UNKNOWN_DIALOG 被命名，否则整页会被当成「未知弹窗只观察」而卡死——
  实机 `evidence/runtime/window-20261006-034714/frame-0022.json` 就是这样停下来的。
  - `assets/resource/en/locale.json`：`encounter_reward` = `^Select Encounter Reward Card$`、
    `selectable` = `^Selectable(?:\s*\d{1,2}\s*/\s*\d{1,2})?$`。
  - `src/maalimbus/vision.py`：`REWARD_CARD` 分支（标题 + `Selectable` + `Confirm` 三证据）放在
    通用 dialog 否决**之前**。
  - `assets/resource/base/anchors.json`：新页 `reward_card`（identity 三条 + controls 两张卡框、
    `Confirm` [1128,764,168,49]、`X Cancel` [688,768,154,45]）。`tools/verify_anchors.py` → **11 页 0 broken**。
  - `src/maalimbus/window.py`：`REWARD_CARD` 计划读计数——没选满就点第一张卡（`advance=True`，
    只有像素变化能证明选中），选满才点 `Confirm`；`reward_card.cancel_button` 进 `FORBIDDEN_CONTROLS`
    （拒绝已到手的奖励是禁止输入，登记它只为让页面可被识别）。
  - `src/maalimbus/reward_vision.py`（新，纯函数）：`counter_state(record)` 从帧的 OCR token 里读
    `chosen/required`。**关键坑**：未选卡时 OCR 给两个 token（`Selectable` + `0/1`），选中后会并成一个
    `Selectable 1/1`（`evidence/runtime/window-20261006-035257/frame-0002.json`），第一版严格匹配
    因此掉进 UNKNOWN_DIALOG；现在在右上波段内搜索计数，`tests/test_reward_vision.py` 4 个用例钉住两种写法。
  - 循环守卫加豁免 `LOOP_GUARD_EXEMPT = ('TUTORIAL', 'BATTLE_HUD')`：一场战斗本来就会反复
    「Win Rate → START」，否则 3 回合就被误判成循环。
- 实机推进（`build/window-reward2.json`，4 步全 passed）：`REWARD_CARD`（点 `Confirm`）→
  `REWARD_CARD`（再点 `Confirm`，第一次点击落在奖励卡出场动画上被吃掉，第二次生效）→ `MAP`
  → `NODE_PANEL` → `PRE_BATTLE_TEAM`。**全程没有点过 `Cancel`，也没有重复领奖**。
- 全量 **228 passed**。

## Prior continuation: 2026-10-06 04:15 local
- 这一轮全是「窗口自己在实机里被带偏」之后修掉的真实缺陷，每条都有实机帧 + 回归测试：
  - **浮层身份收窄**：`overlay_vision.triangle_box` 现在要求金色连通域「又紧凑又尖」
    （`MIN_FILL=0.28`/`MAX_FILL=0.72` 填充率 + `MIN_LEAN=1.8` 左右四分之一列像素比）。
    实机根因：出战前队伍页右侧的暖色 **Details 按钮**（47×41、填充均匀）被判成教学书的 ▶，
    窗口在 `evidence/runtime/window-20261006-034009/` 里连点 12 次，把「E.G.O Resource Overview」
    详情面板开了又开。`window_step.overlay_hit` 也**不再把三角当身份**，只用「轮播圆点」＋
    「书自己的 ▶ 模板」，三角只用来给浮层计划定位要点的控件。
  - **analyze 事件没有 `ocr`/`size`**：`map_observed`/`battle_observed` 只带语义字段
    （scene/floor/pack/各 box），所以 `overlay_hit` 的圆点判据与 `team_state` 的徽章读取**在实机里一直是死代码**
    （`team` 恒为 `null`）。`window_step.observe` 现在从最新 `frame-*.json` 补齐 `size` 与 `ocr`。
  - **循环守卫**：新增 `--loop-guard`（默认 3）。让 `successor_ok` 容忍 TUTORIAL 治好了「误判即停机」，
    但也藏起了循环——实机 `build/window-run4` 用同一对动作（TUTORIAL 点 ▶ → 队伍页点 To Battle!）
    跑了 12 个来回且每一步都 `passed`。现在同一 `(page, action, node/target)` 计划重复到阈值即停机
    （教学书除外，它本来就该一张张翻）。
  - **`--unknown-rounds` 默认 6 → 12**：胜利横幅本身就把画面占住约 25 秒
    （`evidence/runtime/window-20261006-033014/`），6 轮 × 5 秒不够，窗口会在战斗刚结束时报
    `page_unreadable_after_waiting`。
- 实机进展（`build/window-run5.json`）：`PRE_BATTLE_TEAM`（**12/12 已满**，战绩 `Backup Deployed 5/5`）
  → `To Battle!` → `BATTLE_HUD` → `Win Rate` 自动指派 → `START` 提交回合 → 回合结算（UNKNOWN）
  → 再观测已回到 `BATTLE_HUD`，窗口可以继续推进同一场战斗。
- 全量测试 **222 passed**；`tools/verify_anchors.py` 10 页 0 broken。

## Prior continuation: 2026-10-06 03:45 local
- **实机：窗口第一次自己把一局推进起来了**（`tools/window_step.py`，全部是被证明过的点击，零猜测坐标）：
  MAP → 点「离玩家最近的候选节点」→ **NODE_PANEL**（此前点远处的宝箱节点毫无反应，见下）→ 点 `Enter` → 过场 →
  教学书浮层（连点 ▶）→ 出战前队伍页（12 张卡逐张入队，0/12 的 Battle! 是暗的）→ `To Battle!` → 战斗 HUD
  （`Win Rate` 自动指派 → `START` 提交回合）→ **VICTORY**（`evidence/runtime/window-20261006-033014/`）→ 回到 MAP。
- 这一路上修掉的真实缺陷（每条都有实机帧与回归测试）：
  - `map_vision.map_header`：实机把抬头拆成 `Exploring` ＋ `Floor` 两个 token，风格化层数数字常常没有被 OCR 读到 →
    新增 `HEADER_LABEL_PATTERN`/`HEADER_FLOOR_PATTERN`，**只有 label 也认**（下面仍必须命中主题包行），层数允许 `None`。
  - `overlay_vision`：`triangle_box` 原来返回「带内全部金色像素的包围盒」，于是战斗 HUD 右侧 E.G.O 图标列（x≈.95、y .35–.49）
    被当成教学书的 ▶，窗口把整个战斗页误判成浮层并连点图标列 8 次；改成 `connectedComponentsWithStats` 只取**紧凑连通域**
    （面积 200–4000、宽高比 .5–1.7、边长 ≤9% 帧宽），并新增 `carousel_dots`（书的轮播圆点行）作为主身份。
  - `battle_vision`：第三种 Win Rate/Damage/START 布局（x 比旧的两套右移约 290px）落在波段外 → 波段放宽到 `.95`。
  - `window_step`：MAP 候选改为「按到玩家节点的距离排序」，并加 `--map-tries`：不可达节点会吞掉点击（页面仍是 MAP），
    于是跳过它试下一个，而不是直接停机。
  - 教学书的**出口**：最后一页只剩左侧 ◀（没有前进控件），此前直接停机；现在新增锚点 `tutorial.book_close`
    （书自己的抬头 ⟵，实机点它得到 `PRE_BATTLE_TEAM`，不消耗资源），有 `previous`、无前进控件时改点它。
  - 教学书会在**任意**操作之后压上来（实机 `build/window-run3.json` step1：点 `To Battle!` 后书盖住了战斗页），
    旧逻辑会记 `unexpected_successor` 停机；现在 `successor_ok` 把「后继页面是 TUTORIAL」一律视为可接受，
    由下一步把浮层点掉。浮层自己的计划不受影响（仍要求点完浮层消失）。
- 全量测试 **221 passed**；`tools/verify_anchors.py` 10 页 0 broken。
- 下一步：把这局打到第 5 层并领奖（`pending` 里还缺：结算领奖、层礼赠、商店、事件、下一层、轮换再入场）。

## Prior continuation: 2026-10-06 04:05 local
- 按 Plan v1 先补两件「线上只读数值」的地基，全部离线（无设备、无点击、未改运行行为）：
- ① 社区数据管道：`tools/fetch_identity_catalog.py`（`GitHubState` ETag/限流缓存 + 按 pinned commit 取 raw 与 commit 日期）
  → `src/maalimbus/identity_catalog.py`（纯函数合并）→ `assets/resource/base/identity-catalog.json`：
  **128 人格 / 122 带关键词**，关键词由技能里的 `buffKeyword` 反推（`Burst`=破裂、`Breath`=呼吸法、
  `Bleeding`/`Laceration`=流血、`Vibration*`=震颤、`Sinking`=沉沦、`Charge`=充能）；抽查吻合（剑契组杀手=Poise、
  Seven 南部 6 科=Rupture、多裂纹事务所收尾人=Charge、脑叶 E.G.O 赤瞳=Bleed）。**覆盖率限制**：
  `flaglow/LimbusStaticData` 停在 2025-01-23（LLC 中文包活跃），catalog 只是离线事实快照，**不能**当作
  「玩家现有的全部人格」，线上仍以游戏内 filter 为权威。提交 `74f53fb`。
- ② 锚点注册表 + 自检：`assets/resource/base/anchors.json` + `tools/verify_anchors.py` + `src/maalimbus/anchors.py`
  （8 个单测）。三类锚点 `ocr` / `template`(1280 基准，验证时按帧宽等比放大) / `geometry`
  （`verified_on{frame,sha256,box,source}`，**只在自己那一帧算已证明**，换帧即 `stale`，绝不静默沿用旧坐标）。
  注册表带 `pending` 清单，显式列出尚未证明的页面：人格 filter、结算领奖、层礼赠、商店、事件、下一层、轮换再入场。
  离线回放 5 个已验证页面全绿（模板锚点实测在 1920 帧上 1.5× 命中 `image/battle/win_rate.png`），
  报告写 `build/anchors-report.json`。全量测试 **180 passed**。
- 下一步＝**验证窗口**（用户 m01490 的选择）：把 `pending` 里的页面在一次连续实机里一次看完并钉进注册表，
  之后线上只读「验证过的数值接口」。

## Prior continuation: 2026-10-06 02:17 local
- 用户要求（m01490）：写脚本前先参考 LALC，再参考 Limbus 中文 wiki/攻略摸清机制，然后**先 plan 一个最聪明的脚本模式**；
  「把需要图片验证的部分尽量压缩到一个时间段去做，其他地方在线上保留一个验证后的数值接口就好，而不是走一步看一步」。
  框架 MaaFramework、实现参考 MaaEnd、原型/机制参考 LALC。
- 产出 `docs/script-mode-plan.md`（Plan v1，只读设计，未连设备、未点击、未改运行行为）：四份「数字/契约」文件
  （`anchors.json` / `floor-graph.json` / `inventory.json` / `run-ledger.json`）、三个感知窗口（开轮前标定 / 每层一次整图解析 /
  战斗与结算）、分层锚点 + 锚点注册表 + `verify_anchors.py` 自检 + `capture_anchors.py` 一次点击采集、自动配队四条路径
  （成队码/已存队槽 → 排序法 → 一次扫描 → 人工导入）、镜牢机制基线（5 层、Boss 前必有商店、领奖耗 5 Enkephalin、周加成 3 档、
  星光是 +层数/Hard +4×层数、融合点数与 60/90/99% 命中、关键词内名 `Burst`=破裂）、照抄清单、P0–P4 路线与验收。
- 四个只读调研（子代理）要点：**MaaEnd 不是边狱巴士项目**（是《终末地》，只作 MaaFramework 工程范本：`"task":[]`+`"import"`、
  `Interface/` vs `__` 节点、`SceneManager`+`[JumpBack]`、ExpressionRecognition、ImageCropper「文件名即 ROI」、CI schema 校验、
  MirrorChyan OTA、已弃用后台 Win32 截图）；真正的 MFW 边狱项目 `MaaXYZ/MAALimbusCompany` 66★ **2024-08 已弃坑**，
  是反面教材（只点自带 WinRate/推荐阵容、无地图数据层 → 遇镜牢即崩）；LALC 硬编码 1280×720、缺图即 `raise KeyError`、
  整包覆盖更新、AGPL-3.0；人格数据源 = `LocalizeLimbusCompany`（中文名/关键词/礼物，活跃）＋`flaglow/LimbusStaticData`
  （rank/抗性/被动，2025-01 停更），**id 对齐**；中文 wiki（huijiwiki/fandom）实测 Cloudflare 403，改 `wiki.biligame.com`。
- 待用户拍板项见该文档 §13（许可、游戏内 filter 能否多选、是否自建数据镜像、AALC 框架归属未核实）。

## Prior continuation: 2026-10-06 01:40 local
- First real combat from the stopped231221 session, using the discovery-based binding
  (MuMu 自带 adb、EmulatorExtras 截图、AdbShell|MinitouchAndAdbKey|Maatouch 输入) and one
  bounded click per step: START 点击把战斗从 turn1 推到 turn2，随后回合结算出现胜利演出
  "…have dealt a fatal blow to your enemies"、`Gain Corpus Ingredient`、`Sloth DMG Up +1`、
  `TOTAL 132`（evidence/runtime/battle-step-20261006-013320/frame-0001.png）。全程无按键输入。
- 关键几何：`START` 文字只是横幅，真正的按钮是横幅下方的暖色圆钮——
  `battle_vision.warm_control()` 读该控件，钉住 label(1060,738,66,30) vs control(1038,771,121,133)；
  Win Rate/Damage 按钮会随棋盘横向移动（x1300-1362），自动分配波段加宽到 .58-.74 / .58-.75，
  两种布局都有测试。提交 82863aa、17101be。
- 阻塞并已停下：胜利演出后 HUD 显示 `TURN 3`、有 Win Rate/Damage 但**始终没有 START**；
  连续 8 次 auto_assign 点击无任何状态变化 → 已停止点击，并在 tools/battle_step.py 增加
  `auto_assign_had_no_effect` 标记（pass=False）以免再盲重复。是"该回合要手动点技能/需要别的控件"
  还是"战斗已处于结束态"尚无定论；未再发输入。未声称通关、领奖、轮换或再入场。

## Prior continuation: 2026-10-06 01:20 local
- ADB binding corrected to the documented path. Manual
  `docs/zh_cn/2.4-控制方式说明.md` (and the official Python sample `sample/python/demo1.py`)
  require an ADB controller's screencap/input methods to come from
  `MaaToolkitAdbDeviceFind`, never a hand-picked combination. New
  `src/maalimbus/adb_device.py` (`discover`/`input_policy`/`pin_input`/`build`) and
  `tools/adb_discover.py` implement it; every live tool plus `tools/run_native.py`
  now discovers the device first. Read-only discovery reports MuMu as
  `MuMu安卓设备-1-MuMuPlayer v5+` (127.0.0.1:16416, MuMu's own
  `D:\Program Files\Netease\MuMu\nx_main\adb.exe`, `screencap EmulatorExtras=64`,
  `input AdbShell|MinitouchAndAdbKey|Maatouch` with `extras.mumu.enable=true`), i.e.
  EmulatorExtras screencap is available while EmulatorExtras input is not.
- The previous binding hardcoded platform-tools adb with `Encode` + `Maatouch`,
  which bypassed MuMu's native channel; that is the change the user flagged
  (paraphrased m00950: the clicking interfered with their mouse). No input has been
  sent since; 166 tests pass, including new pure offline contracts for the policy.

## Prior continuation: 2026-10-06 01:05 local
- The real entry chain is now established by three authorized single clicks on MuMu:
  map node click -> **node info panel** (`Clear Rewards` + `Enter`, scene `NODE_PANEL`)
  -> `Enter` -> **pre-battle team page** (`Preset #1 / Zilu/Zigong`, `2/12`,
  `To Battle!`, scene `PRE_BATTLE_TEAM`) -> `Battle!` -> **combat HUD** (`WAVE`/`TURN`
  corner + `Win Rate`/`Damage`, scene `BATTLE_HUD`).
- The user authorized pressing `Battle!` exactly as the page showed. Evidence:
  `evidence/runtime/map-probe-20261006-000748/`,
  `evidence/runtime/map-panel-enter-20261006-000900/`,
  `evidence/runtime/map-settle-20261006-000930/`,
  `evidence/runtime/team-page-battle-20261006-010230/`. Each step used the gated probe
  (nonce in `build/map-probe-authorization.json`), one click, no key, foreground
  unchanged.
- New/updated: `map_vision.pre_battle_team_page()`+`battle_target()`,
  `battle_vision.battle_hud()`, scenes `PRE_BATTLE_TEAM`/`BATTLE_HUD`,
  `tools/team_page_battle.py`; 157 tests pass. Not claimed: any turn, skill, damage,
  victory, floor clear, reward or rotation. Android touch battle control is still not
  implemented and the Windows `P`-key path stays forbidden on Android, so the battle
  is parked for a decision.

## Prior continuation: 2026-10-06 00:20 local
- Two user-authorized bounded clicks on MuMu established the real entry flow.
  (1) One click at sampled target (997,452) inside the node requested at (1005,465)
  opened the **node info panel** (`Clear Rewards`, `85` reward icon, `Enter`), not a
  battle: `evidence/runtime/map-probe-20261006-000748/`. `map_vision.node_panel()` /
  `enter_target()` now identify that page (exactly one `Clear Rewards` plus exactly
  one `Enter` in their own bands) and the agent promotes it to scene `NODE_PANEL`.
  (2) One click on that panel's `Enter` (enter_box 1668,780,124,63; sampled target
  1705,815; delay712ms) reached the **pre-battle team / identity selection page**, not
  a battle: `Preset #1 / Zilu/Zigong`, twelve identity cards with two `SELECTED`,
  `Total Participants 2/12`, `To Battle!` —
  `evidence/runtime/map-settle-20261006-000930/`. The production classifier reported
  `TEAM_LIBRARY` for that page, so its scene identity is still open. Both clicks used
  the gated probe (nonce in `build/map-probe-authorization.json`), one click each, no
  key, foreground unchanged; 156 tests pass.
- Open and deliberately untouched: the team page's preset-to-saved-team mapping and
  the rotation ledger's `index2` (0-based, the fifth team) continuation. No preset was
  changed and `To Battle!` / `Clear Selection` were never pressed. No floor clear,
  battle, reward or rotation is claimed.

## Prior continuation: 2026-10-06 00:05 local
- Live MuMu verification of the map identity, read-only first and then through the
  real pipeline. The game is still on `Exploring Floor 1 / To be Cleaved` (7548
  Starlight, 600 Enkephalin). Actual Maa OCR on a fresh MuMu capture and on the
  retained `231221/terminal.png` both give scene MAP, floor1 and pack `To be
  Cleaved`, with the header box scaling exactly1.5x between1280x720 and1920x1080:
  `build/map-live-crosscheck-verification.json`. `tools/map_live_observe.py` ran the
  new `MapObserve` pipeline node (DirectHit + `limbus_map_observe`, registered in
  `tools/run_native.py`) through an `Maa AdbController` with `Null` input and
  recorded route `current_position_not_proven`, `next_node` null, zero input:
  `evidence/runtime/map-live-20261006-000159/result.json`.
- Offline replay of that same node passes on the map frame and fails closed on the
  pack page with no input: `build/map-observe-replay-verification.json`. Node
  identity, current-position proof, floor routing, battle, floor clear, reward and
  rotation remain unproven; route stays an explicit refusal until a live frame
  proves a current position and an unvisited node. No previous input was repeated
  and no pack was dragged again.

## Prior continuation: 2026-10-05 23:45 local

- Map recognition repaired offline as required after231221. `src/maalimbus/map_vision.py`
  identifies the map page from the `Exploring|Before Entry Floor 1-5` header plus its
  pack line only; `agent/recognition.py` promotes that to scene MAP and
  `ThemeObservation` now records `theme_map_postcondition`, selected true only when the
  fresh header names the pack this run planned. Actual Maa OCR replay over the retained
  `evidence/runtime/live-20261005-231221/terminal.png` identifies MAP (pack page stays
  THEME_PACKS) and the replay controller sent zero input:
  `build/map-frame-replay-verification.json`. 153 Python tests pass (145 before).
- Route reading is deliberately an explicit refusal: the retained floor1 frame has no
  provable unvisited node, so `route_decision` returns `current_position_not_proven`
  and records no target. Node identity, floor routing, live continuation from the stopped
  session, floor clear, reward, rotation and re-entry all remain unproven. No device
  input was sent in this continuation and no previous input was repeated.

## Prior continuation: 2026-10-05 23:13 local
- Actual native downward Swipe selected To be Cleaved and reached the floor1 map.
  `evidence/runtime/live-20261005-231221/terminal.png` visibly shows Exploring
  Floor1 / To be Cleaved, party portraits and connected route nodes. Process60476
  stoppedconfirmed. Scene UNKNOWN triggered the bounded boundary; no further input.
- `tools/verify_real_theme_drag.py` now intercepts native Maa Swipe over the retained
  230455/frame-0001.png: real case1 downward drag, missing mode/header/Refresh and
  changed-cover OCR uncertainty0 drags. Unchanged post-frame never proves selection.
  `build/real-theme-drag-verification.json` retains the report. Terminal frame mode
  OCR was below threshold; do not lower thresholds to force it. Local mode OCR
  robustness and native map/routes must be repaired offline before next live input.
- Next implement floor1 map recognition/routing on231221 retained frame. No floor
  clear, battle, final reward, rotation or reentry evidence. Preserve all progress.

## Prior continuation: 2026-10-05 23:05 local
- Current authoritative frame: `evidence/runtime/live-20261005-230455/terminal.png`.
  Fresh native read-only proof confirms HARD floor1 theme packs; task stopped.
  Both free initial gifts are owned, validated by Owned labels plus catalog icons
  in224916. Extra gift search was refused without purchase (225222/225439).
  Mode switched once from Normal to Hard in230146; fresh230455 resolved pending.
- Pack selection has not happened. User confirms the card must be dragged downward.
  Existing native Swipe uses an inset randomized start/end and480–680ms duration;
  next validate its geometry on this actual1920x1080 frame before bounded input.
  Current cards: To be Cleaved, Faith & Erosion, The Forgotten. All three local
  Lix configured weights are10; no pack preference has been invented.
-145 Python tests pass. Actual/derived replay evidence is distinguished. Android
  battle input rejects Windows P-key action until a verified touch target exists.
  No floor clear, final reward, rotation or next entry is proven. Module budget0
  remains pending. Do not repeat previous grace/gift/search/mode transactions.

## Prior continuation: 2026-10-05 22:36 local
- Read-only current MuMu capture222911 revalidated the gift page and target package.
  Native223048 opened Bleed category. Native223230 selected Wound Clerid; fresh
 223418 verified title, highlighted row1 and1/2. Native223506 selected Little and
  To-be-Naughty Plushie; fresh same-session row/title/count proof verified2/2.
  Native223639 submitted the exact two selections and reached the first
  `E.G.O Gift GET!` modal (Wound Clerid), confirmed stopped. Latest actual frame:
  `evidence/runtime/live-20261005-223639/terminal.png`.
- Next: acknowledge each explicit free gift receipt with retained name/postcondition,
  verify actual Hard difficulty and floor1 entry. Do not repeat initial Commit:
  private `initial-gift-progress.json` retains selected1,2 and commit_pending.
  `GIFT_GET` blocks the underlying gift page; incomplete receipt modal is unknown.
- Maa group/pick/proof/commit replays include changed icons and missing counter,
  foreground/profile/title/selection negative cases; no device input in replay.
  Full suite143 passed before receipt veto; latest12 vision/callback tests and real
  Maa retained receipt observation pass. No floor, battle or final reward evidence.
- Private grace/gift progress JSON is excluded from Git as well as packaging.

## Star stage: 2026-10-05 22:27 local
- MuMu Maa-native entry/team-confirm/level-warning -> star selection -> initial
  E.G.O Gift page verified with retained actual captures. Current stopping point:
  `evidence/runtime/live-20261005-222652/terminal.png`, 0/2 gifts selected.
- User's final Lix zero-based grace choice is 1,3,4,6, no Enhance. Actual Maa
  selections showed available107 ->97 ->77 ->47 ->7. Base costs10+20+30+40=100.
  Extra remaining-starlight conversion was explicitly disabled and visually proved
  (unchecked box, converted Cost0). Confirmation entered the gift page. Owned
  starlight was7541 in the confirmation; no final resource settlement claim.
- Imported seven whitelisted team profiles from user's local Lix configuration;
  rotation5,4,1,6,2,7,3 and deployment orders preserved. Highest-level keyword
  identity selection policy exists with tests; native filter/paging/selection and
  MXU controls are still pending. Never substitute the policy test for live proof.
- Full Python suite143 passed; actual Maa star-selection/entry/checkbox/confirm
  replays passed including zero-input negative cases. Last task confirmed stopped;
  no floor, battle, reward, rotation or repeat-run success yet.
- Next: native initial gift selection with real postconditions, five-floor flow,
  reward budget (modules remain0/pending), native automatic formation and MXU,
  cached Windows packaging, and FGO error options/Release without reopening FGO.

## Development contract
- Read this file and docs/design.md before changes. Preserve existing work.
- Maa owns screenshot/input and bounded Pipeline scheduling. Pure Python ranks choices;
  Agent returns recognition boxes and state updates. Do not import LALC's controller/runtime.
- Crop stable text/edges; record normalized ROI, locale, source commit and frame provenance.
  Dungeon artwork, season number, currency amount and full-screen background are not anchors.
- Stop on unknown, defeat, expired session or unconfigured resource consumption; save evidence.
  Configurable error behavior defaults to leaving the game open. Never infer completion from task status.
- One controller, bounded session, finite node hits; random timing stays within configured limits.
- Retain source/license notices. No credentials, account screenshots or private configuration in releases.
- Do not claim five-floor success without each floor, reward and rotated-team postcondition.

## Acceptance
See docs/acceptance.md. No live dungeon completion has been verified yet.

## History
- 2026-10-05: User switched priority to MuMu after cancelled Windows UAC.
  Added bounded Maa AdbController CLI and shared lease/read-only probe. Actual
  Maatouch navigated HOME to Drive to mirror entry; tutorial overlay blocks entry.
  Source home and outlined-menu OCR replays pass original/changed-art/negative;
  128 Python tests pass before tutorial guard. No floors/rewards/spending/rotation.
  Latest live sessions/evidence: live-20261005-214739, live-20261005-215020 and
  adb-probe-20261005-215059. Both tasks stopped confirmed. No FGO launch or UAC.
- 2026-10-01: Switched idle native MXU to d14d119 after the old GUI exited.
  Actually displayed twelve deployment choices, changed positions1/3 and verified
  persistence after normal restart. Actual saved options resolved against installed
  PI passed frozen-Agent IPC derived deployment, retaining another team/preferences.
  One unchecked task, disconnected, auto-run false; no game input/UAC or clear.
- 2026-10-01: Added twelve PI deployment choices with atomic complete/unique
  saving. Native derived replay exposed a Python exception escaping the Maa C
  callback and continuing old-order clicks; all app callbacks now return explicit
  failure and latch the Agent closed. 125 tests and 17 deployment replays pass,
  including six callback faults with zero input. Clean d14d119 package has 622
  hashes/self-test, nine frozen deployment IPC cases and four battle IPC
  regressions passing. Old GUI remains 08c2adc; no game input or clear proof.
- 2026-10-01: Matched MaaEnd window/background/front Win32 profiles and added
  generated Don Quixote native icon plus Chinese UI. 114 tests, clean 08c2adc
  622-file package/self-test and four frozen-Agent IPC regressions pass. Actually
  opened MXU and verified icon/controller/task labels in native screenshots,
  retaining logs. Game remains minimized 0x0 and HIGH; no game input/UAC or clear.
- 2026-10-01: Added experimental native one-shot battle planning using pinned
  small English UI/damage glyphs and Maa ClickKey P. Fresh frame/risk text is
  diagnostic only; no Enter/EGO, retry or victory claim. 112 tests, seven actual
  Maa derived battle cases and three retained-frame navigation regressions pass.
  Live planning, turn submission, JP and full five-floor integration remain pending.
- 2026-10-01: Added isolated GitHub update staging with checksum/manifest checks,
  persisted download rate-limit backoff and partial cleanup. Shared Windows ZIP
  prevalidation rejects reserved names, streams and file/directory collisions.
  103 tests and full offline staging of the retained 612-file development ZIP pass.
  No installation/execution, MXU update button or public-release download proof.
- 2026-10-01: Added experimental native deployment preparation with saved order,
  explicit standard-order preset, adaptive observed count and per-click local
  ordinal verification. Ten actual Maa derived graph cases and 79 tests pass.
  Stuck/unconfirmed choices are not clicked twice; battle start remains pending.
- 2026-10-01: Added fixed-glyph/title theme-pack recognition, saved team weights,
  PI preference choices and bounded native drag. Seven actual Maa derived
  production-graph replays pass; 68 unit tests pass. Corrected OCR edge padding
  and independent custom-parameter option nodes. No live theme/map proof; no UAC.
- 2026-10-01: Built first local Windows development package with unmodified MXU,
  Maa and frozen Agent/Runner; fixed installed roots/import-time native library
  paths. 57 tests and actual packaged Agent IPC reference/unknown replays passed.
  Manifest/privacy checks passed; no live game input or new UAC. Full dungeon,
  desktop UI and release audit remain pending.
- 2026-10-01: Reworked Chinese/English README against pinned MaaFramework
  structure, added direct build/interface references and truthful feature scope.
  Distinguished the project's existing AGPL choice from MaaFramework LGPL;
  retained third-party licenses, added the incorporated GPL v3 text and documented
  unresolved artwork distribution rights. No change of third-party licensing.
- 2026-10-01: Audited MaaEnd permission-required Win32 and LALC RunAs startup;
  corrected PI permission flag and added ordinary UAC/bounded CLI launcher with
  separate logs. Actual UAC request was cancelled; no new controller/input proof.
  Added current-thread 30-minute usage-recovery heartbeat, preserving full goal.
- 2026-10-01: Imported 332 pinned public gift icons/keyword groups with file hashes
  and source paths; added local floor-gift ownership/candidate recognition and
  Maa ranking targets. Five actual Maa derived OCR/Click replays pass, including
  paid/blocked zero-input cases; 48 tests plus 3 navigation/6 team regressions pass.
  No live acquisition/quota/next-floor claim. FGO error option is locally installed
  with all nine configs preserved; GUI exit and public release remain pending.
- 2026-10-01: Replaced unbounded live connection/resource/stop waits with finite
  public Maa job polling and a monotonic whole-session deadline. Timeout and
  interruption stop once; failed stops remain unconfirmed and retain the lease
  until process exit. Technical completion never marks a dungeon clear. 43 tests
  pass. Read-only identity refresh still shows HIGH game / MEDIUM controller;
  no live input attempted.
- 2026-10-01: Native entry OCR replay corrected for the retained `Mirro` reading;
  changed covers and unknown frames passed actual Maa replay. Identified supplied
  team frame as Sinners library, implemented bounded native selection and fresh
  header/row verification, with six replay cases (derived switch, no live deployment).
  Atomic profiles/ordered five-floor reward checkpoints and GitHub metadata/cache
  recovery implemented; 39 tests pass, including cross-process controller exclusion.
  Win32 screenshot works; live input is blocked
  by HIGH game / MEDIUM controller integrity. CLI and GUI task entries now reject
  mismatched privileges. Full hard dungeon and desktop packaging remain unverified.
- 2026-10-01: Recovered empty repository and running Windows game. Pinned/read MaaFramework
  cc5fef6 and LALC 431b432; inspected four user reference frames. Native design and evidence gates started.
