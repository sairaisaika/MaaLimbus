# 0 索引

[English](../en_us/index.md) · [Wiki 入口](../README.md)

本 wiki 是 MaaLimbus 的叙述性文档层。事实源仍是 `PROJECT.md`、`docs/design.md`、`docs/acceptance.md`——wiki 只负责导航与解释，不替代它们（同 `AGENTS.md:5-11` 的必读清单）。

## 全站导航

| 页码 | 中文标题 | English title | 这一页回答什么问题 |
| --- | --- | --- | --- |
| 0 | 索引（本页） | Index | 站点地图、阅读顺序与本轮交付范围 |
| 1 | [概览与术语](1-overview.md) | [Overview and Glossary](../en_us/1-overview.md) | 这是什么、六个主任务各做什么、完成度到哪、术语怎么读、依赖与许可边界 |
| 2 | [架构](2-architecture.md) | [Architecture](../en_us/2-architecture.md) | 模块如何分层、模块地图、关键设计决策 |
| 3 | [运行时](3-runtime.md) | [Runtime](../en_us/3-runtime.md) | 一次运行从启动到结束发生了什么、runner 主循环与控制器/识别时序 |
| 4 | [业务流程](4-business-flows.md) | [Business Flows](../en_us/4-business-flows.md) | 六个主任务各自端到端怎么走、在哪停、留什么证据 |
| 5 | [状态与数据](5-state-and-data.md) | [State and Data](../en_us/5-state-and-data.md) | 用户态私有状态、run ledger、事务与收据的数据模型 |
| 6 | [部署与运维](6-deployment.md) | [Deployment and Operations](../en_us/6-deployment.md) | 打包、安装、更新、日志与证据归档 |
| 7 | [质量与验收](7-quality.md) | [Quality and Acceptance](../en_us/7-quality.md) | 测试与验收口径：到底什么才算通过 |
| 8 | [Agent 规则层](8-agent-rules.md) | [Agent Rules Layer](../en_us/8-agent-rules.md) | 在这个仓库里干活时遵守什么：票据与规格、triage 标签、领域词汇、结论沉淀 |

各章主页面在两种语言下同名同结构（`zh_cn/<page>` 对应 `en_us/<page>`）。部分章节可能另有子页；子页只由该章自己的主页面链接，本表不列子页。

第 8 章是元章节：它讲的是「在这个仓库里干活时遵守什么」，不是产品行为，所以不参与上面几条阅读路径——需要建票、打标签、查词汇或沉淀结论时单独翻它。

## 第 4 章的状态

编号 4 的主题是「业务流程 / Business Flows」，**已交付**：`4-business-flows.md` 逐条讲六个主任务的端到端链路、三类终止与证据产物。前置是第 3 章（运行时）；读完可以直接进第 5 章看状态落在哪些文件。

## 建议阅读顺序

### 新读者路径
**1 → 2 → 3 → 4 → 5**：先知道目标链路和六个主任务，再看模块怎么分层，再看一次运行怎么走，再看六个任务各自的端到端链路，最后看状态落在哪些文件。

### 维护者路径
**0 → 2 → 5 → 7**：先拿到模块地图，再读状态与数据模型，最后用第 7 章的验收口径判断一次改动是否算通过。第 4 章（业务流程）在第 3 章与第 5 章之间。

### 开发者路径（要改代码的人）
**0 → 2 → 3 → 5 → 7 → 2.2**：本页（0）先做分流；再读第 2 章的模块地图与关键决策；再读第 3 章一次运行从启动到结束的时序；再读第 5 章状态与数据模型；最后用第 7 章的验收口径判断一次改动是否算通过。真正动手写某个模块时回到 2.2 的模块地图。**要改代码就必须走这条路径，第 6 章与此无关**——第 6 章讲的是便携包、安装与更新，是给终端用户的。（文档层面另有第 4 章（业务流程）与第 1 章（术语表）可随时查阅。）

**环境要求**：Windows + Python 3.11+。版本要求写在 `pyproject.toml:9`（`requires-python = ">=3.11"`），本机实测解释器为 3.13.1；MaaFramework 原生库版本被 `pyproject.toml:10` 钉在 `maafw==5.12.2`。

**装依赖与跑测试**（命令原文见 `README.md:34-41`，英文版同样在 `README_en.md:34-41`）：

```powershell
git clone https://github.com/sairaisaika/MaaLimbus.git
cd MaaLimbus
python -m pip install -e '.[dev]'
python -m pytest -q
```

pytest 的路径配置在 `pyproject.toml:20-22`（`pythonpath = ["src"]`、`testpaths = ["tests"]`）：**开了 `pythonpath`，所以不必手工设 `PYTHONPATH`，不必先安装包也能在仓库根跑测试**。`dev` extra 只含 `pytest>=8` 与 `pyinstaller>=6`（`pyproject.toml:13-14`）；训练相关依赖另在 `learning` extra（`pyproject.toml:15`），日常开发不需要。

**改 wiki 时另跑一道守卫**：`python tools/check_wiki.py` 与 `python -m pytest tests/test_wiki.py -q`，两者都必须通过（用法与失败示例见 `docs/wiki/README.md:74-80`）。守卫只读，退出非零即列出问题。

**延伸阅读**：wiki 各页只引用了 `docs/` 下的一部分专题；其余专题按主题分组列在 [docs/ 专题地图](../README.md#docs-专题地图--docs-topic-map) 一节。

### 终端用户路径（只想把它跑起来的人）
**6 → 1.1 → 7**：先按部署与运维装包跑起来；再读 1.1 的完成度表，知道哪些能力真的有可核验证据；最后读第 7 章，理解本仓库的口径——「进程启动、任务返回成功、离线测试通过」都不等于镜牢通关（`README.md:31-32`）。这条路只用已打包的程序，不碰 Python 环境；**要改代码请看上面的开发者路径**。

## 阅读约定

- 每个技术断言绑定可核验锚点：`相对路径:行号`、测试名，或 `evidence/runtime/...` 路径。
- 核验不到的显式写「未验收 / 待核实」，不把计划当既成事实。
- 中文页为主文，术语首次出现给中文并保留英文原名；`en_us/` 是逐节镜像，不是摘要。
- 图一律用 Mermaid 围栏，不引入图片文件或额外构建步骤。
