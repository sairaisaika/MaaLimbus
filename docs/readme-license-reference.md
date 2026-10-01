# README 与许可参考对照

本记录核对 goal 中明确指定的 MaaFramework README、LICENSE.md、构建指南和标准化接口设计。参考版本为 `cc5fef675f42ca899e12bc4932ff37ac1278853c`；核对的是实际文件，不将框架文档自动视为本应用的实现证明。

## README 结构

| MaaFramework 的组织方式 | MaaLimbus 对应内容 |
| --- | --- |
| 居中项目标题、介绍、技术/平台/许可徽章 | 中英文 README 的标题区域；只标记实际 Python、Windows、Maa 版本与项目许可 |
| 语言入口 | `README.md` / `README_en.md` 互链；游戏语言资源仍为 EN/JP |
| 简介与即刻开始 | 用途、真实开发状态、依赖、可运行开发命令 |
| 声明与许可：开源许可、分发、使用说明 | 分开主项目和第三方许可；记录素材权利与发布缺口 |
| 开发：构建指南、接口设计 | 链接到指定版本；区分编译 Maa 本身和开发本应用 |
| 鸣谢与沟通交流 | 实际依赖/参考及本项目 Issues |

不复制框架的社区项目列表、赞助账号或平台能力。本项目没有成熟 Windows 包，也没有五层通关证据，不能用下载或“已完成”徽章表示已有这些结果。

## 许可范围

| 材料 | 本地文本/记录 | 实际依据 |
| --- | --- | --- |
| MaaLimbus 自有代码 | 根 `LICENSE`，`pyproject.toml` | 当前项目声明 AGPL-3.0-or-later；此前由开发时自行选择，goal 没有指定 AGPL |
| MaaFramework | `THIRD_PARTY_NOTICES/MaaFramework-LGPL-3.0.md` | 上游 `LICENSE.md` 是 LGPL-3.0；本地文本保留原文 |
| LGPL 引用的 GPL 条款 | `THIRD_PARTY_NOTICES/GPL-3.0.txt` | GNU 官方 GPL v3 全文，https://www.gnu.org/licenses/gpl-3.0.txt |
| Lix 参考/导入材料 | `THIRD_PARTY_NOTICES/LALC-AGPL-3.0.txt` | 上游根许可证 AGPL v3；不据此自行推断所有第三方素材权利 |
| Lix 礼物图标与目录 | `assets/resource/base/gift-catalog.json` | 记录来源提交、每张图路径和 SHA-256，导入工具固定版本 |
| MaaCommonAssets / PaddleOCR | 对应 MIT / Apache-2.0 文本及模型 README | 保留组件的来源和原许可 |

MaaFramework 使用 LGPL 不表示所有调用它的应用必须使用 LGPL。其 LICENSE 的 Application/Combined Work 定义与第 4 节单独处理应用及组合发布的条件。根 AGPL 与依赖 LGPL 不是同一个声明。当前保留根 AGPL，明确它是本项目的选择，避免无依据地把已导入的 Lix 材料改标为 LGPL。

根声明中的 `or-later` 仅适用于本项目自行许可的部分；未据此给 Lix 或其他第三方内容增加“或后续版本”授权。游戏素材的实际权利人及再分发授权仍需核对。此清单是来源记录，不是已完成的发布合规结论。

## 构建和接口设计落实范围

- [4.1 构建指南](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/4.1-构建指南.md)说明如何编译框架本身；MaaLimbus 当前通过 `maafw==5.12.2` 与公开原生库集成。桌面打包仍在验收表中标为未完成。
- [4.2 标准化接口设计](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/4.2-标准化接口设计.md)是语言绑定的 OOP/Job/回调与引用管理指导，不能与 ProjectInterface 的任务选项格式混为一谈。
- `tools/run_native.py` 使用官方 `Win32Controller`、`Resource`、`Tasker` 对象，异步工作由 `src/maalimbus/jobs.py` 有时限地等待。`agent/main.py` 注册官方 CustomRecognition/CustomAction。PI v2 在 `assets/interface.json`，Pipeline 在资源目录，决策策略在 `src/maalimbus/`。
- 上述是现有集成方式；完整镜牢、出战配置、领奖循环和 MXU 打包没有因文档对照而变成已完成。

## 原始参考

- [MaaFramework README](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/README.md)
- [MaaFramework LICENSE](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/LICENSE.md)
- [Lix LICENSE](https://github.com/HSLix/LixAssistantLimbusCompany/blob/431b432e22f0b0da08b95d7c478fa213be20b3e8/LICENSE)
