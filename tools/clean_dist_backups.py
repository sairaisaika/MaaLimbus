"""清理 dist 里的历史备份目录：默认只报告，加 --apply 才删。

2026-10-31 实测：`dist/MaaLimbus/agent.backup-*` 有 **249 份**，每份 149 MB（≈37 GB）；
`dist/.maalimbus-launcher-*` 有 **22 份**，每份约 20 MB。两个目录都只增不减：

- `build/refreeze_agent.py` 每次 refreeze 都把当前 agent 目录改名成 `agent.backup-<sha>`
  再放新的进去，从不清理；
- launcher 每次启动把自身复制到一个唯一兄弟目录（`docs/startup-updater.md` 写明的行为），
  也从不清理。

清理策略按时间保留最近几份（回滚只需要最近一份），其余删除并汇报可回收空间。
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
AGENT_GLOB = 'MaaLimbus/agent.backup-*'
LAUNCHER_GLOB = '.maalimbus-launcher-*'


def _size(path: pathlib.Path) -> int:
    total = 0
    for child in path.rglob('*'):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def plan(paths: list[pathlib.Path], keep: int) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """按修改时间从新到旧，前 keep 个留下，其余删除。"""
    ordered = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    return ordered[:keep], ordered[keep:]


def survey(keep_agent: int = 3, keep_launcher: int = 2) -> list[dict]:
    rows = []
    for label, pattern, keep in (('agent.backup', AGENT_GLOB, keep_agent),
                                 ('launcher', LAUNCHER_GLOB, keep_launcher)):
        found = sorted(DIST.glob(pattern)) if DIST.is_dir() else []
        found = [p for p in found if p.is_dir()]
        kept, doomed = plan(found, keep)
        rows.append({'label': label, 'keep': [p.name for p in kept],
                     'delete': [p.name for p in doomed],
                     'reclaim': sum(_size(p) for p in doomed),
                     'total': len(found)})
    return rows


def report(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        lines.append(f'[{row["label"]}] 共 {row["total"]} 个，保留 {len(row["keep"])}，'
                     f'可删 {len(row["delete"])}，可回收 {row["reclaim"] / 2**30:.1f} GiB')
        for name in row['delete'][:6]:
            lines.append(f'    - {name}')
        if len(row['delete']) > 6:
            lines.append(f'    … 还有 {len(row["delete"]) - 6} 个')
    total = sum(row['reclaim'] for row in rows)
    lines.append(f'合计可回收 {total / 2**30:.1f} GiB')
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='清理 dist 历史备份')
    parser.add_argument('--apply', action='store_true', help='真的删除（默认只报告）')
    parser.add_argument('--keep-agent', type=int, default=3)
    parser.add_argument('--keep-launcher', type=int, default=2)
    args = parser.parse_args(argv)
    rows = survey(args.keep_agent, args.keep_launcher)
    print(report(rows))
    if not args.apply:
        print('\n这是预演。加 --apply 才真的删除。')
        return 0
    removed = 0
    for row, (label, pattern) in zip(rows, (('agent.backup', AGENT_GLOB),
                                            ('launcher', LAUNCHER_GLOB))):
        for name in row['delete']:
            target = DIST / name if label == 'launcher' else DIST / 'MaaLimbus' / name
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                removed += 1
    print(f'\n已删除 {removed} 个目录。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
