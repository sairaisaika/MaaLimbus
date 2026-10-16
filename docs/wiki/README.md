# MaaLimbus Wiki

本仓库 wiki 的入口路由页。中文导航在前，English navigation 在后；两种语言的正文逐节镜像，文件名同名同结构。

This is the routing page for the repository wiki. Chinese navigation first, English navigation second; the two languages mirror section by section and share file names.

## Agent 快速入口 / Fast agent entry

**先定位当前问题，不用通读全站。** [短索引](agent-index.md) ·
[实施计划与完成矩阵](zh_cn/9-execution-plan.md) ·
[多agent wiki skill](../../skills/multi-agent-wiki/SKILL.md)。
这些入口节省定位成本，不增加文件锁、审批或固定流程；源码和当前实证优先于过期叙述。

```text
python tools/wiki_route.py "Grace purchase successor balance not proven"
python tools/wiki_route.py "GPU占用"
python tools/wiki_route.py "神经学习是否apply" --json
```

每次只返回相关功能的**当前代码符号 → 局部解释/图 → 窄范围验证 → 验收边界**。
函数行号随查询从源码重新定位，不依赖记忆猜路径；未实现功能明确指向设计。
没有匹配时再做一次有针对性的源码搜索并补路由，不让wiki挡住工作。

Start with the [quick routes](agent-index.md), [execution plan](en_us/9-execution-plan.md)
or portable [wiki skill](../../skills/multi-agent-wiki/SKILL.md). Read only the relevant
feature. Queries resolve current symbols and return local diagrams, narrow checks
and evidence boundaries. This is an efficient navigation aid, not a workflow lock
or a reason to override source/runtime facts.

## 中文导航

| 语言 | 索引入口 | 说明 |
| --- | --- | --- |
| 简体中文 | [`zh_cn/index.md`](zh_cn/index.md) | 中文为主文，术语保留英文原名并在首次出现时给中文 |
| English | [`en_us/index.md`](en_us/index.md) | 中文版的忠实镜像，逐节对应，不是摘要 |

章节一览（每页在两种语言下都存在，可直接点击）：

| 页码 | 中文标题 | English title |
| --- | --- | --- |
| 0 | [索引](zh_cn/index.md) | [Index](en_us/index.md) |
| 1 | [概览与术语](zh_cn/1-overview.md) | [Overview and Glossary](en_us/1-overview.md) |
| 2 | [架构](zh_cn/2-architecture.md) | [Architecture](en_us/2-architecture.md) |
| 3 | [运行时](zh_cn/3-runtime.md) | [Runtime](en_us/3-runtime.md) |
| 4 | [业务流程](zh_cn/4-business-flows.md) | [Business Flows](en_us/4-business-flows.md) |
| 5 | [状态与数据](zh_cn/5-state-and-data.md) | [State and Data](en_us/5-state-and-data.md) |
| 6 | [部署与运维](zh_cn/6-deployment.md) | [Deployment and Operations](en_us/6-deployment.md) |
| 7 | [质量与验收](zh_cn/7-quality.md) | [Quality and Acceptance](en_us/7-quality.md) |
| 8 | [Agent 规则层](zh_cn/8-agent-rules.md) | [Agent Rules Layer](en_us/8-agent-rules.md) |
| 9 | [实施计划与完成矩阵](zh_cn/9-execution-plan.md) | [Execution Plan and Acceptance Matrix](en_us/9-execution-plan.md) |

第 4 章已交付。第 8 章是元章节，讲怎么在这个仓库里干活，不讲产品行为。部分章节可能另有子页，子页只由该章自己的主页面链接。

本 wiki 是叙述性文档层，**不替代事实源**：当前进度看 `PROJECT.md`，设计约束看 `docs/design.md`，验收口径看 `docs/acceptance.md`（`AGENTS.md:5-11` 同样把这三个文件列为改代码前的必读）。

## English navigation

| Language | Index entry | Notes |
| --- | --- | --- |
| 简体中文 | [`zh_cn/index.md`](zh_cn/index.md) | Chinese is the main text; terms keep their English names with a Chinese gloss at first use |
| English | [`en_us/index.md`](en_us/index.md) | A faithful mirror of the Chinese text, section by section — not a summary |

All pages, both languages:

| Page | English title | 中文标题 |
| --- | --- | --- |
| 0 | [Index](en_us/index.md) | [索引](zh_cn/index.md) |
| 1 | [Overview and Glossary](en_us/1-overview.md) | [概览与术语](zh_cn/1-overview.md) |
| 2 | [Architecture](en_us/2-architecture.md) | [架构](zh_cn/2-architecture.md) |
| 3 | [Runtime](en_us/3-runtime.md) | [运行时](zh_cn/3-runtime.md) |
| 4 | [Business Flows](en_us/4-business-flows.md) | [业务流程](zh_cn/4-business-flows.md) |
| 5 | [State and Data](en_us/5-state-and-data.md) | [状态与数据](zh_cn/5-state-and-data.md) |
| 6 | [Deployment and Operations](en_us/6-deployment.md) | [部署与运维](zh_cn/6-deployment.md) |
| 7 | [Quality and Acceptance](en_us/7-quality.md) | [质量与验收](zh_cn/7-quality.md) |
| 8 | [Agent Rules Layer](en_us/8-agent-rules.md) | [Agent 规则层](zh_cn/8-agent-rules.md) |

Page 4 is delivered. Chapter 8 is a meta chapter about working in this repository rather than product behaviour. Some chapters may add sub-pages; a sub-page is only reachable from its own chapter's main page.

This wiki is the narrative documentation layer and does **not** replace the sources of truth: current progress lives in `PROJECT.md`, design constraints in `docs/design.md`, and the acceptance ledger in `docs/acceptance.md` (the same three files `AGENTS.md:5-11` lists as required reading before touching code).

## docs/ 专题地图 / docs/ topic map

wiki 各章只引用了 `PROJECT.md`、`docs/design.md`、`docs/acceptance.md` 和一部分专题；下表把**仍值得延伸阅读**的 `docs/` 专题按主题列出来，让它们从 wiki 可达。这里只给链接与一句话定位，事实以文档自身为准。**刻意不列**：验收流水账与进度记录、未落地的计划与实验、一次性会话记录（`DEEPSEEK_CONTINUATION.md`、`handover-*.md`）、经济审计、第三方许可正文、测试逐文件清单——这些要么已被 `PROJECT.md` / `docs/acceptance.md` 取代，要么会误导读者把计划当既成事实。

The wiki chapters cite `PROJECT.md`, `docs/design.md`, `docs/acceptance.md` and part of the topics; the table below groups the `docs/` topics that are **still worth reading further**, so they are reachable from the wiki. Links and one-line positioning only — the documents themselves remain the facts. **Deliberately excluded**: the acceptance ledger and progress records, plans and experiments that never landed, one-off session records (`DEEPSEEK_CONTINUATION.md`, `handover-*.md`), economy audits, third-party license text, and per-file test inventories — those are either superseded by `PROJECT.md` / `docs/acceptance.md` or would tempt a reader to mistake a plan for a fact.

| 主题 / Theme | 文档 / Document |
| --- | --- |
| 运行时与两条运行路径 / Runtime and the two run paths | [`docs/runner.md`](../runner.md) — runner 作为库（去掉屏幕与输入之后的镜牢循环）；[`docs/agent-loop.md`](../agent-loop.md) — 打包应用驱动整轮运行的 pipeline 接缝。 |
| 架构契约与决策 / Architecture contract and decisions | [`docs/post-battle-ownership.md`](../post-battle-ownership.md) — 战后路径归 pipeline 还是归 driver；**给奖励卡、层礼、商店、下一层或入场返回加节点之前先读**。 |
| 原生控制与 MXU 配置 / Native control and MXU configuration | [`docs/native-control.md`](../native-control.md) — 原生客户端与窗口控制、四种控制方式；[`docs/task-settings.md`](../task-settings.md) — 任务与已保存队伍的设置项；[`docs/theme-packs.md`](../theme-packs.md) — 主题包选择任务（尚未接通地图与五层循环）。 |
| 商店设置 / Shop settings | [`docs/shop-settings.md`](../shop-settings.md) — 决定一次商店访问如何被限界、携带上限与解析器的三项镜牢设置。 |
| 商店的死位复活 / The shop's revive of a dead key slot | [`docs/shop-revive.md`](../shop-revive.md) — `Heal Sinner` 三步弹窗（三选项 → 选中罪人 → 复活通告）各自的文字证明、弹窗右下角那颗换词按钮、以及「按币值差记账」的收据契约。 |
| 打包与分发 / Packaging and distribution | [`docs/windows-package.md`](../windows-package.md) — Windows 开发包的实际构成与它的未验收边界。 |
| 更新链 / Update chain | [`docs/update-staging.md`](../update-staging.md) — `tools/check_update.py --stage` 的下载与暂存语义；[`docs/startup-updater.md`](../startup-updater.md) — 桌面快捷方式启动器的自更新流程。 |
| 框架一致性 / Framework conformance | [`docs/maaframework-conformance.md`](../maaframework-conformance.md) — 与 MaaFramework 上游协议的逐项对照**及其缺口段**，是「哪些协议特性本项目根本没断言」的集中来源。 |
| 黑盒学习 / Black-box learning | [`docs/learning.md`](../learning.md) — 图像哈希、按真实运行分组的训练数据准备与当前样本不足的诚实结论。 |
| 许可与上游对照 / License and upstream cross-check | [`docs/readme-license-reference.md`](../readme-license-reference.md) — 针对指定上游提交核对 README、LICENSE、构建指南与标准接口设计。 |
| 协作流程（agent 专用）/ Collaboration process (agent-facing) | [`docs/agents/domain.md`](../agents/domain.md)、[`docs/agents/issue-tracker.md`](../agents/issue-tracker.md)、[`docs/agents/memory.md`](../agents/memory.md)、[`docs/agents/triage-labels.md`](../agents/triage-labels.md) — 多上下文域文档、issue 追踪、记忆回写与 triage 标签约定（`AGENTS.md` 已在入口指向它们）。 |

## 自检 / Self-check

wiki 有一道离线守卫。任何一页漂移——锚点指向不存在的文件、行号越界、导航行被改坏、只有一种语言加了小节、代码围栏没配对、图类型写错、双语篇幅失衡——它都会非零退出并列出问题：

```powershell
python tools/check_wiki.py
python -m pytest tests/test_wiki.py -q
```

离线守卫判断不了 Mermaid 正文能不能解析（它只认第一行的图类型关键字）。要验证渲染：

```powershell
python tools/make_wiki_mermaid_check.py
python -m http.server 8791 --bind 127.0.0.1
# 打开 http://127.0.0.1:8791/build/wiki-mermaid-check.html
```

必须走 HTTP：`file://` 页面不能 import mermaid 的 ES module，而且会**静默**失败——页面停在 "parsing" 不给结果。

The wiki has an offline guard. Any drift — a `path:line` anchor pointing at a file that does not exist, a line number past the end of the file, a broken navigation line, a section added to one language only, an unpaired code fence, a wrong diagram keyword, or a twin pair out of proportion — makes it exit non-zero and list what broke:

```powershell
python tools/check_wiki.py
python -m pytest tests/test_wiki.py -q
```

The offline guard cannot tell whether a mermaid body parses; it only reads the diagram keyword on the first line. To check rendering:

```powershell
python tools/make_wiki_mermaid_check.py
python -m http.server 8791 --bind 127.0.0.1
# open http://127.0.0.1:8791/build/wiki-mermaid-check.html
```

Serve over HTTP on purpose: a `file://` document cannot import the mermaid ES module, and it fails **silently** — the page sits on "parsing" with no result.


## 图的工程语义 / Engineering semantics of diagrams

| 图 / Diagram | 模型元素与连线语义 / Elements and relationships | wiki 落点 / Location |
| --- | --- | --- |
| 架构 / Architecture | 组件、责任边界、依赖和接口；不表达时间先后 / Components, responsibility boundaries, dependencies and interfaces; no timeline | 2-architecture.md |
| 流程 / Business process | 业务动作、判断、循环、完成与保留现场 / Activities, decisions, loops and outcomes | 4-business-flows.md |
| 时序 / Sequence | 参与者生命线、按时间的调用与响应；输入前记录意图、输入后核后继 / Lifelines, ordered calls and responses; intent before input, successor afterwards | 3-runtime.md |
| 数据模型 / Data model | 逻辑实体、属性、引用及基数；文件字段盘点另外标注，非数据库物理表 / Logical entities, attributes, references and cardinalities; JSON inventories are separate | 5-state-and-data.md |
| 部署 / Deployment | 主机、进程或运行环境、部署制品、通信协议；构建流程另图 / Hosts, processes/environments, artifacts and transport links; builds are separate | 6-deployment.md |
| 状态 / State machine | 状态、事件或守卫、迁移；pending 是状态，不是自动重试许可 / States, events/guards and transitions; pending is not retry permission | 5-state-and-data.md |

Mermaid 是绘图语法，不决定工程图类型。flowchart 语法可承载组件图或部署图，但必须按该图的模型元素与连线语义绘制。布局上下位置本身不表示设计层级或调用先后。

Mermaid is a drawing syntax, not the engineering model. A flowchart renderer can draw components or deployment nodes only when its elements and relationships follow that model. Vertical layout alone does not mean layering or temporal order.

## 分层图覆盖索引 / Feature diagram coverage

总架构与总流程用于导航，局部图用于解释具体守卫、交互、数据或失败恢复。以下链接不代表功能实机全验收；每段正文分别写明实现、保留帧验证与实机缺口。没有图的简单参数/纯函数按文字和源码索引解释，避免为画图而画图。

Overview diagrams are navigation; local diagrams explain specific guards, interactions, data and recovery. Links below do not claim complete live acceptance. Each section distinguishes implementation, retained evidence and live gaps. Simple parameters and pure functions need prose/source references rather than a diagram for every function.

| 功能 / Feature | 中文局部图 | English local view |
| --- | --- | --- |
| 识别、浮层与新观测 / Recognition, overlays and fresh observation | [3.1.5](zh_cn/3-runtime.md#feature-3-1-5) | [3.1.5](en_us/3-runtime.md#feature-3-1-5) |
| 未知页探索与待审标签 / Unknown-page exploration and proposed labels | [3.7](zh_cn/3-runtime.md#feature-3-7) | [3.7](en_us/3-runtime.md#feature-3-7) |
| 罪人模型、独立教师与上线边界 / Sinner model, independent teacher and promotion boundary | [3.8](zh_cn/3-runtime.md#feature-3-8) | [3.8](en_us/3-runtime.md#feature-3-8) |
| 购买价值学习与规则执行的分界 / Purchase-value learning versus rule execution | [3.9](zh_cn/3-runtime.md#feature-3-9) | [3.9](en_us/3-runtime.md#feature-3-9) |
| 启动意图与前台确认 / Launch intent and foreground confirmation | [4.2.1](zh_cn/4-business-flows.md#feature-4-2-1) | [4.2.1](en_us/4-business-flows.md#feature-4-2-1) |
| 入场与列表上下查找 / Entry and bidirectional team-list search | [4.3.2](zh_cn/4-business-flows.md#feature-4-3-2) | [4.3.2](en_us/4-business-flows.md#feature-4-3-2) |
| GUI Start原生适配链 / GUI Start native subtask adapter | [9.3.1](zh_cn/9-execution-plan.md#feature-9-3-1) | [9.3.1](en_us/9-execution-plan.md#feature-9-3-1) |
| 新版镜牢界面的适配计划 / Plan for adapting to the redesigned Mirror Dungeon | [9.3.2](zh_cn/9-execution-plan.md#feature-9-3-2) | [9.3.2](en_us/9-execution-plan.md#feature-9-3-2) |
| 旧局仍在跑时的 GUI Start 入口判定 / GUI Start entry decision while the old run is still playing | [9.3.3](zh_cn/9-execution-plan.md#feature-9-3-3) | [9.3.3](en_us/9-execution-plan.md#feature-9-3-3) |
| 参与者计数读不出时的入口与部署 / Entry and deployment when the participant counter cannot be read | [9.3.4](zh_cn/9-execution-plan.md#feature-9-3-4) | [9.3.4](en_us/9-execution-plan.md#feature-9-3-4) |
| 新版购买确认框的货币徽章 / The redesigned purchase dialog's currency badge | [9.3.5](zh_cn/9-execution-plan.md#feature-9-3-5) | [9.3.5](en_us/9-execution-plan.md#feature-9-3-5) |
| 按完成镜牢计数与藏品搜索开放 / Counting completed runs and opening the gift search | [9.3.6](zh_cn/9-execution-plan.md#feature-9-3-6) | [9.3.6](en_us/9-execution-plan.md#feature-9-3-6) |
| 奖励页两处误停：目录名错字与“价”的判据 / Two false stops on the reward page: a catalogue typo and what counts as a price | [9.3.7](zh_cn/9-execution-plan.md#feature-9-3-7) | [9.3.7](en_us/9-execution-plan.md#feature-9-3-7) |
| 视图读不动与识别卡死：视角恢复阶梯与停滞看门狗 / A page that cannot be read, and a recognition call that never returns: the viewport ladder and the stall watchdog | [9.3.8](zh_cn/9-execution-plan.md#feature-9-3-8) | [9.3.8](en_us/9-execution-plan.md#feature-9-3-8) |
| 每场部署：复用、修正与提交 / Encounter deployment: reuse, correction and submission | [4.3.3](zh_cn/4-business-flows.md#feature-4-3-3) | [4.3.3](en_us/4-business-flows.md#feature-4-3-3) |
| 楼层礼物选择、到账与恢复 / Floor gifts: selection, receipts and recovery | [4.3.4](zh_cn/4-business-flows.md#feature-4-3-4) | [4.3.4](en_us/4-business-flows.md#feature-4-3-4) |
| 初始礼物、搜索与楼层主题 / Initial gifts, search and floor themes | [4.3.5](zh_cn/4-business-flows.md#feature-4-3-5) | [4.3.5](en_us/4-business-flows.md#feature-4-3-5) |
| 战斗配卡与真实进度 / Battle assignment and actual progress | [4.3.6](zh_cn/4-business-flows.md#feature-4-3-6) | [4.3.6](en_us/4-business-flows.md#feature-4-3-6) |
| 路线与事件是不同决策 / Routes and events are different decisions | [4.3.7](zh_cn/4-business-flows.md#feature-4-3-7) | [4.3.7](en_us/4-business-flows.md#feature-4-3-7) |
| 经验与纺锤共享的菜单链 / Shared Experience and Thread menu chain | [4.4.1](zh_cn/4-business-flows.md#feature-4-4-1) | [4.4.1](en_us/4-business-flows.md#feature-4-4-1) |
| 领奖与只记账恢复 / Payout and bookkeeping-only recovery | [4.6.1](zh_cn/4-business-flows.md#feature-4-6-1) | [4.6.1](en_us/4-business-flows.md#feature-4-6-1) |
| 未完成任务的真实边界 / Actual boundaries of unfinished tasks | [4.7.1](zh_cn/4-business-flows.md#feature-4-7-1) | [4.7.1](en_us/4-business-flows.md#feature-4-7-1) |
| 轮换政策与手动跳过 / Rotation policy and manual skip | [4.10](zh_cn/4-business-flows.md#feature-4-10) | [4.10](en_us/4-business-flows.md#feature-4-10) |
| 更新事务与失败回滚 / Update transaction and failure rollback | [6.4.5](zh_cn/6-deployment.md#feature-6-4-5) | [6.4.5](en_us/6-deployment.md#feature-6-4-5) |
| 发布包证据与私有数据隔离 / Package provenance and private-data exclusion | [6.7](zh_cn/6-deployment.md#feature-6-7) | [6.7](en_us/6-deployment.md#feature-6-7) |
| 学习数据的引用与复核关系 / Learning data references and review relationships | [5.5](zh_cn/5-state-and-data.md#feature-5-5) | [5.5](en_us/5-state-and-data.md#feature-5-5) |
| 购物与刷新分别结算 / Purchase and refresh settle separately | [4.3.8](zh_cn/4-business-flows.md#feature-4-3-8) | [4.3.8](en_us/4-business-flows.md#feature-4-3-8) |
| 图鉴、账户 box 与自动编队 / Catalogue, account box and automatic formation | [4.3.9](zh_cn/4-business-flows.md#feature-4-3-9) | [4.3.9](en_us/4-business-flows.md#feature-4-3-9) |
| 基线、分工与事实源 / Baseline, ownership and sources of truth | [9.1](zh_cn/9-execution-plan.md#feature-9-1) | [9.1](en_us/9-execution-plan.md#feature-9-1) |
| 看板卡、依赖与阶段出口 / Board cards, dependencies and phase exits | [9.2](zh_cn/9-execution-plan.md#feature-9-2) | [9.2](en_us/9-execution-plan.md#feature-9-2) |
| 失败自动恢复与显式运行次数 / Automatic recovery and the explicit run count | [9.3](zh_cn/9-execution-plan.md#feature-9-3) | [9.3](en_us/9-execution-plan.md#feature-9-3) |
| 学习与策略的架构边界 / Architecture boundary between learning and policy | [9.4](zh_cn/9-execution-plan.md#feature-9-4) | [9.4](en_us/9-execution-plan.md#feature-9-4) |
| 标签、评分与证据的数据模型 / Labels, scores and evidence data model | [9.5](zh_cn/9-execution-plan.md#feature-9-5) | [9.5](en_us/9-execution-plan.md#feature-9-5) |
| 资源监控的部署与接口 / Resource monitoring deployment and interface | [9.6](zh_cn/9-execution-plan.md#feature-9-6) | [9.6](en_us/9-execution-plan.md#feature-9-6) |
| 验收矩阵与回写纪律 / Acceptance matrix and write-back discipline | [9.7](zh_cn/9-execution-plan.md#feature-9-7) | [9.7](en_us/9-execution-plan.md#feature-9-7) |

新增功能或修复改变状态/交互时，审查对应局部图及双语段落；不能只改总览。Mermaid 解析通过只证明语法，覆盖索引只证明可找到说明，二者都不等于游戏 pipeline 通关。

When a feature or fix changes interactions/states, review its local diagram and paired prose, not only the overview. Mermaid parsing verifies syntax and this map verifies discoverability; neither proves a complete gameplay pipeline.
