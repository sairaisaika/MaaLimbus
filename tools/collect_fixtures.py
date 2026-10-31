"""把跑得起来的关键帧从运行产物搬进 `tests/fixtures/`。

测试输入不该住在 `evidence/runtime/`：那是运行产物，会被工作区预算清掉（D355），
清完 13 条用例就从"红"变成"永久跳过"（D357）。这个工具让 fixture 可以被**攒**：
每跑一次实机，把需要的页面类型各留一帧进仓库，测试优先读 fixture、其次读归档。

用法：
    python tools/collect_fixtures.py --run evidence/runtime/packaged-mirror-XXXX
    python tools/collect_fixtures.py --from-runtime --pages MAP BATTLE_HUD
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'frames'
DEFAULT_PAGES = ('MAP', 'BATTLE_HUD', 'RESUME_DIALOG', 'HOME', 'SHOP')


def collect(run, *, pages=DEFAULT_PAGES, target=None) -> dict:
    """从一次运行里按页面类型各取一帧，返回 {page: 目标路径}。"""
    run = pathlib.Path(run)
    target = pathlib.Path(target or FIXTURES)
    taken = {}
    for record_path in sorted(run.glob('frame-*.json')):
        try:
            record = json.loads(record_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        page = record.get('scene')
        if page not in pages or page in taken:
            continue
        png = record_path.with_suffix('.png')
        if not png.is_file():
            continue
        folder = target / run.name
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(record_path, folder / record_path.name)
        shutil.copy2(png, folder / png.name)
        taken[page] = folder / record_path.name
    return taken


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='把关键帧搬进 tests/fixtures')
    parser.add_argument('--run', default=None, help='一次运行的 evidence 目录')
    parser.add_argument('--from-runtime', action='store_true', help='扫描 evidence/runtime 最近几次')
    parser.add_argument('--pages', nargs='*', default=list(DEFAULT_PAGES))
    args = parser.parse_args(argv)
    runs = []
    if args.run:
        runs = [pathlib.Path(args.run)]
    elif args.from_runtime:
        runtime = ROOT / 'evidence' / 'runtime'
        runs = sorted((p for p in runtime.glob('*') if p.is_dir()), key=lambda p: p.stat().st_mtime)[-5:]
    if not runs:
        print('没有可采集的运行目录（用 --run 指定）')
        return 2
    total = 0
    for run in runs:
        taken = collect(run, pages=tuple(args.pages))
        total += len(taken)
        print('%-46s %s' % (run.name, ', '.join(sorted(taken)) or '（没有目标页面）'))
    print('\n共采集 %d 帧到 %s' % (total, FIXTURES.relative_to(ROOT)))
    return 0 if total else 2


if __name__ == '__main__':
    raise SystemExit(main())
