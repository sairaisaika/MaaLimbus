# MaaLimbus Wiki

本仓库 wiki 的入口路由页。中文导航在前，English navigation 在后；两种语言的正文逐节镜像，文件名同名同结构。

This is the routing page for the repository wiki. Chinese navigation first, English navigation second; the two languages mirror section by section and share file names.

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

第 4 章已交付。部分章节可能另有子页，子页只由该章自己的主页面链接。

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

Page 4 is delivered. Some chapters may add sub-pages; a sub-page is only reachable from its own chapter's main page.

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
