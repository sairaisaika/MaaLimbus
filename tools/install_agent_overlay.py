"""把仓库里的 `src/maalimbus` 覆盖到冻结 agent 的 `_internal/` 上。

背景（D383）：`build/refreeze_agent.py` 只是把一份**已打包好**的目录搬进 `dist`，它不重建
exe；真正的打包器 `tools/build_windows_package.py` 需要三份上游 zip，本机没有。于是改
`src/maalimbus/*.py` 之后实机跑的一直是 exe 里的旧代码——识别层的修改（`party_point`、
`train_next` 等）从来没生效过。

PyInstaller 的 onedir 布局把 `_internal/` 放进 `sys.path`，文件系统上的同名包优先于 PYZ，
所以把 `src/maalimbus/*.py` 复制进 `_internal/maalimbus/` 就能让 agent 用仓库源码。这是一条
**开发期覆盖**通道：正式发布仍然必须走 `build_windows_package.py`。

用法：
    python tools/install_agent_overlay.py            # 覆盖
    python tools/install_agent_overlay.py --check     # 只报告是否已覆盖
"""
from __future__ import annotations

import argparse
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src' / 'maalimbus'
TARGET = ROOT / 'dist' / 'MaaLimbus' / 'agent' / '_internal' / 'maalimbus'


def overlay(source=SOURCE, target=TARGET):
    """复制模块文件，返回写入的文件名列表。"""
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for path in sorted(source.glob('*.py')):
        shutil.copy2(path, target / path.name)
        written.append(path.name)
    return written


def covered(source=SOURCE, target=TARGET):
    """哪些文件在覆盖区里还是旧内容。"""
    stale = []
    for path in sorted(source.glob('*.py')):
        other = target / path.name
        if not other.is_file() or other.read_bytes() != path.read_bytes():
            stale.append(path.name)
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只检查，不写文件')
    args = parser.parse_args(argv)
    if args.check:
        stale = covered()
        print('overlay stale: %d file(s)' % len(stale))
        for name in stale[:10]:
            print('  ', name)
        return 0 if not stale else 1
    written = overlay()
    print('overlay written: %d file(s) -> %s' % (len(written), TARGET))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
