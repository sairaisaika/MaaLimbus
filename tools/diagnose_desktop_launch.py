"""诊断桌面端 MaaLimbus 打不开：一次跑完，逐项给结论。

2026-10-31 的现场：`dist/MaaLimbus/MaaLimbus.exe` 实为 MXU 2.7.1（未签名），
启动后会用 shell 再打开一次自身，Windows 对未签名 exe 弹「Unknown Publisher」，
点 Run 又重启 → 循环；而 MXU 2.8.0（MaaEnd.exe）能起进程却不写日志也不建窗口。
两次现场都指向「启动层」而不是游戏逻辑，所以把启动层的检查固定成一个工具：
下次再遇到「打不开」，先跑它，不要从页面识别开始猜。

只读：不启动进程、不改配置、不发输入。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist' / 'MaaLimbus'
EXE = DIST / 'MaaLimbus.exe'
LAUNCHER = DIST / 'launcher' / 'MaaLimbusLauncher.exe'
CONFIG = DIST / 'config'

OK = 'ok'
WARN = 'warn'
BLOCK = 'blocked'


def _ps(command: str) -> str:
    try:
        done = subprocess.run(
            ['powershell', '-NoProfile', '-Command', command],
            capture_output=True, text=True, timeout=60,
        )
        return (done.stdout or '').strip()
    except Exception as error:  # 诊断工具本身不许抛
        return f'probe_failed:{type(error).__name__}'


def check_exe() -> tuple[str, str, str]:
    if not EXE.is_file():
        return 'exe', BLOCK, f'{EXE} 不存在'
    info = _ps(
        f"$f='{EXE}'; $v=(Get-Item $f).VersionInfo; "
        "\"$($v.FileDescription)|$($v.FileVersion)|$((Get-AuthenticodeSignature $f).Status)\""
    )
    parts = info.split('|')
    if len(parts) < 3:
        return 'exe', WARN, f'版本信息读不出：{info}'
    desc, version, signature = parts[0], parts[1], parts[2]
    status = OK if signature.lower() == 'valid' else WARN
    return 'exe', status, f'{desc} {version}，签名={signature}'


def check_processes() -> tuple[str, str, str]:
    out = _ps("Get-Process MaaLimbus,MaaLimbusLauncher,MaaEnd -ErrorAction SilentlyContinue | "
              "ForEach-Object { \"$($_.ProcessName):$($_.Id)\" }")
    if not out:
        return 'processes', OK, '没有残留进程'
    return 'processes', WARN, f'残留：{out.replace(chr(10), ", ")}'


def check_security_dialog() -> tuple[str, str, str]:
    out = _ps(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$ids = @(Get-Process MaaLimbus -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id); "
        "if ($ids.Count -eq 0) { 'none'; exit }; "
        "'pending'"
    )
    if out == 'none':
        return 'security_dialog', OK, '没有 MaaLimbus 进程（不会有确认框）'
    return 'security_dialog', WARN, 'MaaLimbus 进程在，注意是否卡在「Unknown Publisher」确认框'


def check_config() -> tuple[str, str, str]:
    path = CONFIG / 'user-launch.json'
    if not path.is_file():
        return 'config', WARN, f'{path} 不存在'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as error:
        return 'config', BLOCK, f'{path} 读不出：{type(error).__name__}'
    update = data.get('update')
    stage = data.get('update_stage')
    return 'config', OK if update is False else WARN, f'update={update} update_stage={stage}'


def check_webview() -> tuple[str, str, str]:
    bs = chr(92)
    client = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    key = "HKLM:" + bs + "SOFTWARE" + bs + "WOW6432Node" + bs + "Microsoft" + bs + "EdgeUpdate" + bs + "Clients" + bs + client
    command = "(Get-ItemProperty '" + key + "' -ErrorAction SilentlyContinue).pv"
    out = _ps(command)
    if not out:
        return 'webview2', BLOCK, 'WebView2 运行时未安装（Tauri 无法建窗口）'
    return 'webview2', OK, f'WebView2 {out}'


def check_game() -> tuple[str, str, str]:
    """MuMu 上唯一在线的设备与前台页面。"""
    try:
        done = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=30)
    except Exception as error:
        return 'game', WARN, f'adb 不可用：{type(error).__name__}'
    devices = [line.split('\t')[0] for line in (done.stdout or '').splitlines()[1:]
               if '\tdevice' in line]
    emulators = [d for d in devices if d.startswith('emulator-') or d.startswith('127.0.0.1:')]
    if not emulators:
        return 'game', WARN, f'没有模拟器在线（设备：{devices or "无"}）'
    device = emulators[0]
    focus = _ps(f"adb -s {device} shell \"dumpsys window 2>/dev/null | grep -m1 mCurrentFocus\"")
    if 'LimbusCompany' not in focus:
        return 'game', WARN, f'{device} 前台不是 Limbus：{focus[:80]}'
    return 'game', OK, f'{device} 前台 LimbusCompany（页面状态需截图判断）'


CHECKS = (check_exe, check_processes, check_security_dialog, check_config, check_webview, check_game)


def report() -> list[tuple[str, str, str]]:
    return [check() for check in CHECKS]


def main(argv=None) -> int:
    rows = report()
    width = max(len(name) for name, _, _ in rows)
    for name, status, detail in rows:
        print(f'{name.ljust(width)}  {status:8}  {detail}')
    blockers = [row for row in rows if row[1] == BLOCK]
    print()
    if blockers:
        print(f'阻断项：{len(blockers)}（{", ".join(row[0] for row in blockers)}）')
        return 1
    print('没有阻断项；若仍打不开或跑不动，按 warn 项逐个看。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
