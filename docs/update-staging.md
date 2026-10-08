# GitHub 更新暂存

`tools/check_update.py --stage` 在持久化的 GitHub 检查/限流状态之上增加下载与检查。
没有 Release、请求失败或仍在限流等待时不下载。每次下载创建独立目录，失败保存
简短原因并删除本次未完成的 `.part` 文件，不将 URL、代理密码或原始异常写进结果。

稳定 Release 必须提供唯一的 `MaaLimbus-win-x64.zip` 或
`MaaLimbus-win-x64-<tag>.zip`，以及唯一的 `SHA256SUMS` 或 `<zip名称>.sha256`。
tag 使用 `v0.1.0` / `0.1.0` 形式；checksum 行格式为 SHA-256、空格、精确文件名。
只接受对应仓库/tag 的 HTTPS 下载地址，重定向限于 GitHub 的公开 Release 资产域名。
若 GitHub 元数据提供资产 digest，也须一致。开发包文件名不会被当作稳定更新资产。

下载有大小上限、有限网络超时及阶段截止检查。ZIP 全部成员检查通过后才解压到
新目录：拒绝路径越界、Windows 设备名/数据流、符号链接、加密、重复、文件目录冲突
和超出体积/文件数量限制。包内逐文件 manifest 必须完整，私有 config/evidence/logs
不能混入，根目录之外的安装不受影响。哈希校验保证内容一致，**不是发布者签名**。

`stage-result.json` 的 `staged` 仅表示下载与包校验通过；`installed`、`executed`
始终为 false。失败后的完整下载或解压内容保留在该次隔离目录供检查，结果仍为 failed。
安装由独立的 `tools/install_update.py --stage <暂存目录> --install <安装目录>` 完成。
它重新校验 manifest、PI 项目/版本，拒绝源码目录、链接、降级与未结束的旧安装事务。
CIM 核实安装目录进程已退出，并持有安装目录外的控制器锁；不会结束进程或绕过 UAC。
同父目录候选/备份保留全部 config/evidence/logs/build，逐文件比较私有数据哈希。
替换后复核公有文件、PI 版本与实际 Agent 自检/资源目录；验证失败恢复原目录，保留失败目录。
断电或回滚失败时保留 journal/backup 并拒绝重试，需核对证据后人工恢复。
尚未接入 MXU 更新按钮，不能把暂存或 Agent 自检解释为完整 GUI 自动更新验收。

```powershell
python tools/check_update.py --stage --timeout 120
python tools/verify_update_stage.py --package-record build/windows-package-latest.json
python tools/verify_update_install.py
```

第二个命令使用已有开发 ZIP 和派生的稳定 Release 元数据，通过离线传输完整校验
真实包；不联网、不执行包、不修改安装、不创建游戏控制器。证据保存到
`build/update-stage-verification.json`。公开 Release 下载及实际更新界面仍待验证。
第三个命令只在新建隔离目录用保留开发包实测目录替换、实际 Agent 自检和注入失败回滚，
保留 `build/update-install-verification.json`，不替换桌面安装、不联网、不发送游戏输入。
