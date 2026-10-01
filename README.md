<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# MaaLimbus

<img src="assets/misc/Don-Quixote.png" width="160" alt="MaaLimbus Don Quixote" />

基于图像识别的 Limbus Company Windows 原生自动化学习项目，由 MaaFramework 驱动。

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows_x64-blueviolet)
![MaaFramework](https://img.shields.io/badge/MaaFramework-5.12.2-blue)
![Pipeline](https://img.shields.io/badge/Pipeline-ProjectInterface_V2-876f69)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](LICENSE)
![Status](https://img.shields.io/badge/status-in_development-orange)

[English](README_en.md) | [简体中文](README.md)

</div>

## 简介

MaaLimbus 使用 MaaFramework 的 Win32 控制器、Pipeline 和 Python Agent，面向 Windows 原生客户端，提供英语和日语资源包。已构建使用 MXU 的本地 Windows 开发包；桌面界面与实机运行仍待验证。

首要目标是 **困难镜牢五层 → 确认领奖 → 切换已保存队伍 → 继续刷取**。完整循环尚未完成实现或实机验证，当前不能作为可用的镜牢挂机工具。

识别使用局部文字、稳定图标和位置，避开变化的镜牢封面。点击落在目标框内部，延迟在有限范围内随机；每次转场需要后续页面证据。

## 即刻开始

> [!IMPORTANT]
> 当前提供开发源码及本地开发包，尚无经完整实机验收的发布包。启动进程、任务返回成功和离线测试通过均不代表镜牢通关。

开发需要 Windows、Python 3.11+ 和 MaaFramework 5.12.2 原生库：

```powershell
git clone https://github.com/sairaisaika/MaaLimbus.git
cd MaaLimbus
python -m pip install -e '.[dev]'
python -m pytest -q
```

先阅读 [设计与任务选项](docs/design.md) 和 [验收记录](docs/acceptance.md)。

| 功能 | 已验证范围 | 未完成部分 |
| --- | --- | --- |
| Windows 控制 | 截图、进程身份、权限检查、单控制器锁 | 实机点击后的页面变化 |
| 镜牢入口 | 真实 Maa 解析与离线页面回放 | 入场后完整流程 |
| 已保存队伍 | 队伍库选择回放；[出战顺序](docs/deployment.md)人数/局部序号的派生回放 | 实机出战位置、排序编辑、战斗启动与换队 |
| 楼层 E.G.O 礼物 | 图标/文字候选、归属、队伍关键词排序回放 | 选择数量、领取确认、下一层衔接 |
| 主题包选择 | 稳定图标/标题、保存队伍权重、原生拖动回放；选项见[说明](docs/theme-packs.md) | 实机选包、日语标题与地图衔接 |
| 战斗规划 | 实验性原生一次 P 选招、保存新图与风险文本回放；见[说明](docs/battle-planning.md) | 全队选招/冲突、生存、E.G.O、回合执行及胜败实测 |
| 五层领奖与循环 | 完成证据及换队条件的存储逻辑 | 五层战斗、实际领奖与连续循环 |
| 体力兑换/补充 | 预算策略测试 | 游戏内操作与余额确认 |
| 邮件/每日奖励 | 设计与任务标签 | 原生流程及实测 |
| GitHub 更新 | 元数据缓存、持久限流等待、隔离下载与完整包校验 | MXU 更新按钮、安装与回滚、公开 Release 实测 |

一次有时限的开发任务：

```powershell
./tools/start_native.ps1 -Binary <Maa原生库目录> -Locale en -Seconds 180
```

启动器使用标准 Windows UAC 请求，不会替用户批准。拒绝时不启动控制器。任务最长一小时，游戏与 Maa 权限需一致。当前 Pipeline 会在未实现页面保存证据并停止。

启动记录在 `build/native-launch*.json`，日志在 `build/native-live.*.log`，运行证据在 `evidence/runtime/`。提交问题前请去除账号信息。

## 声明与许可

### 开源许可

MaaLimbus 自有代码当前声明为 [AGPL-3.0-or-later](LICENSE)。这是本项目此前选择的许可，**不是 MaaFramework 要求应用采用 AGPL**，也不是与 MaaFramework 相同的许可。

[MaaFramework 的许可](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/LICENSE.md)是 LGPL-3.0。本仓库保存其 [LGPL 文本](THIRD_PARTY_NOTICES/MaaFramework-LGPL-3.0.md)及 LGPL 引用的 [GPL-3.0 文本](THIRD_PARTY_NOTICES/GPL-3.0.txt)。Lix 来源的礼物图标、目录及参考材料保留其 AGPL-3.0 标注；根许可证不重新授权第三方材料。

详见 [来源与许可证清单](THIRD_PARTY_NOTICES/README.md) 和 [README/许可对照说明](docs/readme-license-reference.md)。不能通过替换根许可证将已有 Lix 材料声明为 LGPL。

### 分发说明

第三方组件保留各自许可和来源。后续 Windows 包需要附带许可文本、来源版本、构建说明及适用的对应源码；目前尚未发布该包。

游戏画面的版权归相应权利人。记录 Lix 来源不等于证明其有权重新授权游戏素材，公开分发前仍需核对素材授权范围。私人截图、配置和运行证据不纳入发布内容。

### 使用说明

本项目用于图像识别与界面自动化的学习开发，按许可证原样提供，不承诺运行结果。使用者应核对目标软件的服务条款和授权。程序不注入游戏、不读取游戏内存，也不绕过权限或安全机制。

## 开发

本项目使用官方 Python 对象接口和 Job 封装。Maa 管理截图、输入及 Pipeline 调度，Agent 提供识别和决策，纯 Python 策略可以离线验证。

- [快速开始](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/1.1-快速开始.md)
- [Pipeline 协议](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/3.1-任务流水线协议.md)
- [ProjectInterface V2](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/3.3-ProjectInterfaceV2协议.md)
- [标准化接口设计](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/4.2-标准化接口设计.md)
- [MaaFramework 构建指南](https://github.com/MaaXYZ/MaaFramework/blob/cc5fef675f42ca899e12bc4932ff37ac1278853c/docs/zh_cn/4.1-构建指南.md)：用于编译框架本身；当前应用使用公开原生库，无需复制框架的 CMake 构建流程。

真实 Maa 离线回放不创建游戏控制器：

```powershell
python tools/verify_native_replay.py --binary <Maa原生库目录> --references <参考截图目录>
python tools/verify_team_replay.py --binary <Maa原生库目录> --frame <队伍库截图>
python tools/verify_gift_replay.py --binary <Maa原生库目录>
python tools/verify_theme_replay.py --binary <Maa原生库目录>
python tools/verify_deployment_replay.py --binary <Maa原生库目录>
```

英语/日语资源包能被解析，不等于日语实机流程已验证。变换后的封面、标题等派生回放会单独标记。

Windows 开发包构建与打包 Agent 的 Maa 通信回放见 [打包说明](docs/windows-package.md)。构建器只创建新的本地目录，不启动桌面客户端、不请求 UAC、不替换旧安装，也不发布 Release。

## 鸣谢

- [MaaFramework](https://github.com/MaaXYZ/MaaFramework)：原生控制器、识别、Pipeline 与 Python 接口。
- [MXU](https://github.com/MistEO/MXU)：开发包中使用的未修改 ProjectInterface 桌面客户端；界面验收仍待完成。
- [LixAssistantLimbusCompany](https://github.com/HSLix/LixAssistantLimbusCompany)：镜牢流程、队伍/礼物选择参考及有来源记录的礼物素材；未嵌入其控制器。
- [MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets) 与 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)：OCR 模型及相关许可。

## 沟通交流

通过 [Issues](https://github.com/sairaisaika/MaaLimbus/issues) 提交问题，注明游戏语言、停留页面及脱敏终态日志。功能是否完成以验收记录中的实际证据为准。
