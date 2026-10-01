# Windows 开发包

本地包包含未修改的 MXU 2.5.1、MaaFramework 5.12.2、独立打包的 Agent/有时限 Runner、EN/JP 资源、许可文本和公开项目源码。它用于开发验证，尚未完成桌面界面及游戏实机验收，未发布 Release。

## 构建

使用已审核的本地归档；工具不自动联网下载、不覆盖旧安装，输入哈希不一致会拒绝。每次输出到新的 `build/windows-package-<唯一标识>` 目录。

```powershell
python tools/build_windows_package.py --mxu <MXU归档.zip> --maa <Maa归档.zip> --mxu-source <MXU对应源码归档.zip>
```

| 输入 | 审核版本/来源 | SHA-256 |
| --- | --- | --- |
| MXU 二进制 | 官方 v2.5.1 Windows x86_64 归档 | A2375C171EEB360B7D3E7762FB30CDFB452860D8485FBB5D542AE8A053BE8E7D |
| Maa 二进制 | 官方 v5.12.2 Windows x86_64 归档 | 55DCEE2306F95656949165237E781322F6858A1675A3B271BC045A50F43C41B7 |
| MXU 对应源码 | 已缓存的原始源码归档，提交 fb05f97fde0c112e3e07740a385072638a24ba48 | 9DBD168F01F6A74E28B79949E8FDC735BFB8DDE666C5EC8D6409D821A5519B6E |

源归档哈希标识本地已审核输入的精确内容，不声称是上游发布的校验签名。改版本必须先审核新的来源及对应源码，再修改固定输入。

输出记录在 `build/windows-package-latest.json`。包内 `build-info.json` 保存输入来源/哈希、代码版本/是否有未提交变更、明确的验收缺口；`package-manifest.json` 保存逐文件校验。

源码归档只取公开源码、资源、测试、工具与文档。账户配置、运行日志、截图证据和旧安装目录均不复制到开发 ZIP。MXU 对应源码单独随包保存，Maa 原生依赖的完整源码/许可分发审计仍待完成。

## 打包后路径

Agent 和 Runner 从自身可执行文件的安装位置定位包根目录，不使用当前工作目录或 PyInstaller 临时目录。打包 Agent 在导入 `maa.agent` 前指向相邻 `maafw`，避免该模块在导入时加载不存在的默认原生库。环境中遗留的其他应用资源路径不会覆盖打包根目录。

根 `interface.json` 只在构建副本中调整资源、语言、许可和 Agent 的相对路径；开发源码的 PI 入口保留原样。

## 离线验证

```powershell
python tools/verify_packaged_replay.py --app <开发包目录> --references <本地参考截图目录>
python tools/verify_packaged_theme_replay.py --app <开发包目录>
python tools/verify_packaged_deployment_replay.py --app <开发包目录>
python tools/verify_packaged_battle_replay.py --app <8b309b8开发包目录>
```

此工具使用 Maa CustomController 和保存的画面，经过真实 Maa AgentClient/打包 Agent 的进程通信执行生产识别及 Pipeline。它不创建 Win32 游戏控制器、不发送游戏输入。

已验证参考导航两次回放点击并在队伍库边界停止，以及未知画面零点击；终态明确保留 `verified_clear: false`。Agent 自检还验证了实际包内的 EN/JP 与礼物目录，Runner 的帮助入口可运行。这些不构成日语实机、MXU 桌面操作或镜牢通关证据。

`4178821` 开发包另验证了主题包的打包 Agent：经 Maa IPC 读取已保存的第二队，
更新一个权重而保留其他设置，执行一次原生拖动后保存画面并停在地图待验收边界；
资源弹窗零输入。611 个文件校验和隐私排除检查通过。主题包名称/权重的 PI 下拉项已打包，
实际 MXU 界面仍未打开验证。

`ded609b` 开发包另经冻结 Agent IPC 验证实验性出战顺序：依次选择、点击无效不重试、
资源弹窗零输入；保留第二队的名称、关键词和主题包权重。612 个文件校验通过。
这里使用派生人数/序号画面，未验证真实囚人身份、实机格子位置或开始战斗。

开发包构建不会发起 UAC。实机权限条件满足且没有旧控制器后，才可另行启动有时限任务；仍须保存每层、领奖和轮换的真实证据。

最新干净 `8b309b8` 开发包包含实验性战斗规划：619文件完整 manifest/私有根目录排除、
Agent 自检通过。冻结 Agent 经 Maa IPC 对派生正常/卡住画面各按一次 P，对资源弹窗/
未支持日语画面均零输入；正常派生新图的 Neutral 文本可读取，但不声明计划安全或胜利。
子进程退出后未发现运行的 Agent/Runner。证据 `build/battle-package-integrity.json`、
`build/packaged-battle-replay-verification.json`；原 `ded609b` 证明保留其历史范围。

新 ZIP 也通过 `tools/verify_update_stage.py` 的全包离线暂存校验，619文件/原 ZIP 哈希一致。
`build/update-stage-verification.json` 现在指向此新包；派生 Release 元数据不代表已经发布，
暂存不安装也不执行。此前612文件包的 stage-result 仍保留在独立旧暂存目录。
新包尚未打开 MXU 界面、未覆盖安装、未实机输入，也未完成分发审计/发布。
