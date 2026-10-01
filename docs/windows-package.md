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
```

此工具使用 Maa CustomController 和保存的画面，经过真实 Maa AgentClient/打包 Agent 的进程通信执行生产识别及 Pipeline。它不创建 Win32 游戏控制器、不发送游戏输入。

已验证参考导航两次回放点击并在队伍库边界停止，以及未知画面零点击；终态明确保留 `verified_clear: false`。Agent 自检还验证了实际包内的 EN/JP 与礼物目录，Runner 的帮助入口可运行。这些不构成日语实机、MXU 桌面操作或镜牢通关证据。

开发包构建不会发起 UAC。实机权限条件满足且没有旧控制器后，才可另行启动有时限任务；仍须保存每层、领奖和轮换的真实证据。
