"""一键跑一次镜牢：找设备、找 maafw、跑窗口、给一句人话摘要。

爸爸的诉求是「我也能简单操作来运行脚本」：双击仓库根目录的 `运行镜牢.bat` 就够。
这个脚本只做三件事，不引入第二套控制逻辑 —— 真正的循环仍由 `tools/selfrun_inproc.py`
在本进程里跑（同样的 journal、同样的设置、同样的 evidence 目录）：

1. 找 maafw 二进制与在线模拟器（找不到就直说，不猜）；
2. 以给定秒数跑一次，把摘要行收回来；
3. 打印一段中文摘要，并写 `build/last-run.json` 供下次对照。

`--observe-only` 可以只看不动（不发输入）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
BINARY = ROOT / 'build' / 'mxu-probe-271' / 'maafw'
RECORD = ROOT / 'build' / 'last-run.json'


def devices() -> list[str]:
    try:
        done = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    out = []
    for line in (done.stdout or '').splitlines()[1:]:
        if '\tdevice' in line:
            out.append(line.split('\t')[0].strip())
    return out


def pick_device(preferred: str | None = None) -> str | None:
    if preferred:
        return preferred
    found = devices()
    for name in found:
        if name.startswith('127.0.0.1:') or name.startswith('emulator-'):
            return name
    return found[0] if found else None


def summarise(result: dict, directory: str | None) -> str:
    if not result:
        return '没有拿到摘要行：看 build/run-once.log 的最后几行。'
    passed = bool(result.get('passed'))
    floors = result.get('floors') or []
    stop = result.get('stop') or result.get('reason') or '(没有停止原因)'
    lines = [
        f'结果：{"通过" if passed else "未通过"}',
        f'事件：{result.get("events", 0)}    楼层：{floors if floors else "没进楼层"}',
        f'停止原因：{stop}',
    ]
    if directory:
        lines.append(f'证据目录：{directory}')
    if result.get('error'):
        lines.append(f'错误：{result["error"]}')
    return '\n'.join(lines)


def run(seconds: float, observe_only: bool, address: str | None, log: pathlib.Path) -> tuple[int, dict, str | None]:
    device = pick_device(address)
    if device is None:
        print('没有在线的模拟器。先在 MuMu 里把游戏开到主界面，再双击这个脚本。')
        return 2, {}, None
    if not BINARY.exists():
        print(f'找不到 maafw：{BINARY}')
        return 2, {}, None
    command = [
        sys.executable, str(ROOT / 'tools' / 'selfrun_inproc.py'),
        '--binary', str(BINARY), '--address', device, '--seconds', str(seconds),
    ]
    if observe_only:
        command.append('--observe-only')
    print(f'设备 {device}，跑 {seconds:.0f} 秒{"（只看不动）" if observe_only else ""}…')
    with log.open('w', encoding='utf-8') as handle:
        done = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT)
    result = {}
    directory = None
    try:
        for line in reversed(log.read_text(encoding='utf-8', errors='replace').splitlines()):
            line = line.strip()
            if line.startswith('{') and 'events' in line:
                result = json.loads(line)
                break
    except Exception:
        result = {}
    directory = result.get('directory')
    return (0 if result.get('passed') else 1), result, directory


def agent_is_stale(head_time, agent_time, *, slack=0.0):
    """Is the frozen agent older than the commit it is being asked to prove?

    Recognition runs inside `dist/MaaLimbus/agent`, not in `src/`, so a run started after
    editing `src/` proves the *old* copy unless it was refrozen.  Five rounds of live
    measurements were read as "the fix did nothing" for exactly this reason, so the check
    is a gate and not a comment.
    """
    if head_time is None or agent_time is None:
        return False
    return float(agent_time) + float(slack) < float(head_time)

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='跑一次镜牢')
    parser.add_argument('--seconds', type=float, default=600.0)
    parser.add_argument('--observe-only', action='store_true')
    parser.add_argument('--address', default=None)
    parser.add_argument('--allow-stale', action='store_true')
    args = parser.parse_args(argv)
    try:
        import subprocess as _sp
        _head = float(_sp.check_output(['git', 'log', '-1', '--format=%ct'],
                                       cwd=str(ROOT)).strip() or 0)
        _agent = os.path.getmtime(ROOT / 'dist' / 'MaaLimbus' / 'agent')
        if agent_is_stale(_head, _agent) and not args.allow_stale:
            print('agent 副本比 HEAD 旧：识别跑在冻结副本里，这一跑证明的是旧代码。')
            print('先 python build/refreeze_agent.py，或加 --allow-stale 明确接受。')
            return 2
    except Exception as error:
        print('agent 陈旧检查失败（不阻断）：%s' % error)
    log = ROOT / 'build' / 'run-once.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    code, result, directory = run(args.seconds, args.observe_only, args.address, log)
    print()
    print(summarise(result, directory))
    try:
        RECORD.write_text(json.dumps({'result': result, 'directory': directory,
                                      'seconds': args.seconds}, ensure_ascii=False, indent=2),
                          encoding='utf-8')
    except Exception:
        pass
    # 每次跑完先把关键帧攒进仓库（D358）：测试输入不能只住在会被清理的运行目录里。
    try:
        from collect_fixtures import collect as _collect
        _dir = directory or (result or {}).get('directory')
        _taken = _collect(_dir) if _dir else {}
        if not _dir:
            print('fixture：这次没有运行目录，跳过')
        if _taken:
            print('fixture：攒了 %d 帧（%s）' % (len(_taken), ', '.join(sorted(_taken))))
    except Exception as error:
        print('fixture 采集跳过（不阻断）：%s' % error)
    # 每跑一次都会写几百张帧、留一次 agent 备份；预算 2 GiB（D355），收尾自动收回。
    try:
        from maalimbus.workspace import prune as _prune
        _out = _prune(ROOT)
        if _out['freed']:
            print('工作区：收回 %.2f GiB（现在 %.2f GiB）'
                  % (_out['freed'] / 2**30, _out['after'] / 2**30))
    except Exception as error:
        print('工作区清理跳过（不阻断）：%s' % error)
    return code


if __name__ == '__main__':
    sys.exit(main())
