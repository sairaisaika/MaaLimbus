"""工作区预算：这个仓库最多占 2 GiB，超了就要能被自动收回来。

占用不是代码写的，是**没人负责删**：`refreeze_agent.py` 每次改名留一份 agent 备份、
launcher 每次启动复制自身、测试安装器每次在 `build/` 建一个 1.4 GiB 的候选目录、
每跑一次就写几百张 1080p 帧。2026-10-31 实测 345 GiB，其中 `dist` 136 / `build` 128 /
`evidence` 81。

这层的职责只有一句话：**在给定的字节预算下，决定哪些可以没有**（D355）。
规则是保守的：源码、资产、`.git`、`dist/MaaLimbus`（跑起来要用的）永远不动。
"""
from __future__ import annotations

import os
import pathlib
import shutil

BUDGET_BYTES = 2 * 2**30              # 2 GiB，爸爸给的硬上限
KEEP_BUILD_DIRS = ('mxu-probe-271',)   # 跑实机要用的 maafw 探针
KEEP_RUNS = 5                          # 保留最近几次运行，够定位就行
KEEP_RUN_FRAMES = 3                    # 每次运行只留三张帧
KEEP_AGENT_BACKUPS = 1                 # dist 里 agent 备份只留最新一份


def size(path) -> int:
    path = pathlib.Path(path)
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _remove(path) -> int:
    path = pathlib.Path(path)
    freed = size(path)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        try:
            path.unlink()
        except OSError:
            return 0
    return freed


def candidates(root=None) -> list:
    """按“最该先删”的顺序列出可回收的东西（不删，只列）。"""
    root = pathlib.Path(root or '.')
    found = []
    build = root / 'build'
    if build.is_dir():
        for child in build.iterdir():
            if child.is_dir() and child.name not in KEEP_BUILD_DIRS:
                found.append(child)
    dist = root / 'dist'
    if dist.is_dir():
        backups = sorted(p for p in dist.glob('MaaLimbus.backup-*'))
        found.extend(backups[:-KEEP_AGENT_BACKUPS] if len(backups) > KEEP_AGENT_BACKUPS else [])
        found.extend(sorted(dist.glob('*.staging-*')))
        for name in ('evidence', 'debug'):
            if (dist / 'MaaLimbus' / name).is_dir():
                found.append(dist / 'MaaLimbus' / name)
        agents = sorted((dist / 'MaaLimbus').glob('agent.backup-*'))
        found.extend(agents[:-KEEP_AGENT_BACKUPS] if len(agents) > KEEP_AGENT_BACKUPS else [])
    runtime = root / 'evidence' / 'runtime'
    if runtime.is_dir():
        runs = sorted(p for p in runtime.iterdir() if p.is_dir())
        found.extend(runs[:-KEEP_RUNS] if len(runs) > KEEP_RUNS else [])
    return found


def trim_runs(root=None, *, keep=KEEP_RUNS, frames=KEEP_RUN_FRAMES) -> int:
    """保留最近 keep 次运行，每次只留 frames 张帧；返回回收字节。"""
    runtime = pathlib.Path(root or '.') / 'evidence' / 'runtime'
    if not runtime.is_dir():
        return 0
    freed = 0
    runs = sorted(p for p in runtime.iterdir() if p.is_dir())
    for run in runs[-keep:]:
        shots = sorted(run.glob('frame-*.png'))
        for shot in shots[frames:]:
            freed += _remove(shot)
    return freed


def prune(root=None, *, budget=BUDGET_BYTES) -> dict:
    """在预算内尽量保留；返回 {before, after, freed, removed}。"""
    root = pathlib.Path(root or '.')
    before = size(root)
    freed = trim_runs(root)
    removed = []
    if before - freed > budget:
        for path in candidates(root):
            if before - freed <= budget:
                break
            freed += _remove(path)
            removed.append(str(path))
    after = size(root)
    return {'before': before, 'after': after, 'freed': freed, 'removed': removed}


def main(argv=None) -> int:
    """命令行：预演/执行。`--apply` 才真删。"""
    import argparse

    parser = argparse.ArgumentParser(description='把工作区收回到预算内（默认预演）')
    parser.add_argument('--apply', action='store_true', help='真的删（不给就是预演）')
    parser.add_argument('--budget-gib', type=float, default=BUDGET_BYTES / 2**30)
    args = parser.parse_args(argv)
    budget = int(args.budget_gib * 2**30)
    if args.apply:
        out = prune(budget=budget)
        print('清理前 %.2f GiB → 清理后 %.2f GiB（回收 %.2f GiB，删除 %d 项）'
              % (out['before'] / 2**30, out['after'] / 2**30,
                 out['freed'] / 2**30, len(out['removed'])))
        return 0
    before = size('.')
    would = sum(size(path) for path in candidates())
    runtime = pathlib.Path('evidence') / 'runtime'
    if runtime.is_dir():
        for run in sorted(p for p in runtime.iterdir() if p.is_dir())[-KEEP_RUNS:]:
            would += sum(size(p) for p in sorted(run.glob('frame-*.png'))[KEEP_RUN_FRAMES:])
    print('当前 %.2f GiB，预算 %.1f GiB，预演可回收 %.2f GiB（加 --apply 才删）'
          % (before / 2**30, args.budget_gib, would / 2**30))
    return 0
