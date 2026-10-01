# 原生客户端与窗口控制

客户端使用 MaaEnd 同款 MXU 桌面界面，以 ProjectInterface 配置任务、队伍选项、
游戏语言和控制器。新增中文界面词条；游戏识别资源仍为英语和日语。
`assets/misc/Don-Quixote.png` 是本项目生成的小唐图标，通过 PI 的 `icon`
加载到窗口、标题栏、关于页和托盘，不修改 MXU 可执行文件。

## 参考实际实现

本次核对 MaaEnd 提交 `850e5fa026cd5daebe74ef73ddb265cdc7b55d21` 的
[PI 控制配置](https://github.com/MaaEnd/MaaEnd/blob/850e5fa026cd5daebe74ef73ddb265cdc7b55d21/assets/interface.json)：

| 本项目控制器 | Maa 截图 | Maa 鼠标 | Maa 键盘 |
| --- | --- | --- | --- |
| windows-window（默认） | Background | SendMessageWithCursorPos | PostMessage |
| windows-background | Background | SendMessageWithWindowPos | PostMessage |
| windows（保留旧名称） | ScreenDC | Seize | Seize |

三种组合与 MaaEnd 相同，保留已有 `windows` 配置名称；CLI 从同一 PI 文件
读取控制参数，不再硬编码前台方式。GUI 已由 MXU 读取这些设置。
Lix `431b432e22f0b0da08b95d7c478fa213be20b3e8` 的
`lalc_backend/input/input_handler.py` 默认后台状态，鼠标/键盘使用窗口消息；
`update_to.bat` 也包含标准 RunAs 启动。没有引入它的控制器或 BlockInput。

MaaEnd 三种 Win32 控制器均设置 `permission_required: true`。
MXU 在任务启动时处理正常的 Windows 管理员启动，不需要另外通过聊天选择题批准。
项目不会自动重试先前已取消的 UAC，也不绕过 Windows 的输入隔离。

## 实机证据边界

窗口消息是否被 Limbus 接受，必须以操作后的实际页面变化证明；不能由枚举解析
或后台方式的名称推断。最新只读检查记录在 `build/control-reference-preflight.json`：
游戏 PID 40196 / HIGH 12288，检查进程 MEDIUM 8192；游戏最小化且客户区 0×0。
FramePool/Background 原生截图失败，日志同时保留访问拒绝与零尺寸错误；
不单独把截图失败全部归因于权限。未发送游戏输入，未验证实机导航/战斗。

只读检查使用 Null 鼠标与键盘、单控制器锁和有限等待：

```powershell
python tools/probe_win32.py --binary <Maa目录> --capture Background
```

完整困难镜牢五层、领奖和换队循环尚未接通，不将本次界面配置或回放写作通关。
