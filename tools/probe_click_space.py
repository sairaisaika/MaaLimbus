"""点一次地图节点，看画面是不是真的进了节点面板。

D368 的现场记录：识别帧是 1920×1080、设备截图是 1280×720。脚本把识别帧坐标直接发给
controller，于是每一次点击都偏了 1.5 倍——而**手动按设备坐标点同一格**会直接进
`NODE_PANEL`（`build/exp-after1.png`，`Thick Rumbling Hum` + `Enter`）。

这个探针把那条对照做成可重复的：截屏 → 点一次 → 再截屏 → 报画面差异与是否换页。
只点一次，不消费任何资源。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def _shot(serial, path):
    subprocess.run(['adb', '-s', serial, 'exec-out', 'screencap', '-p'],
                   stdout=open(path, 'wb'), check=False)


def _tap(serial, x, y):
    subprocess.run(['adb', '-s', serial, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   check=False)


def _diff(before, after):
    import cv2
    import numpy as np
    first = cv2.imread(str(before))
    second = cv2.imread(str(after))
    if first is None or second is None:
        return None
    return float(np.mean(cv2.absdiff(first, second)))


def probe(serial, x, y, *, out=ROOT / 'build') -> dict:
    """点一次 (x, y)（设备坐标），返回差异与两次截图的路径。"""
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    before, after = out / 'probe-before.png', out / 'probe-after.png'
    _shot(serial, before)
    _tap(serial, x, y)
    import time
    time.sleep(2.0)
    _shot(serial, after)
    return {'x': x, 'y': y, 'diff': _diff(before, after), 'before': str(before), 'after': str(after)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='点一次地图节点并报画面差异')
    parser.add_argument('--serial', default='127.0.0.1:16416')
    parser.add_argument('--x', type=int, required=True)
    parser.add_argument('--y', type=int, required=True)
    args = parser.parse_args(argv)
    out = probe(args.serial, args.x, args.y)
    print('点 (%d, %d) → 画面差异 %s' % (out['x'], out['y'],
                                        'None' if out['diff'] is None else '%.2f' % out['diff']))
    print('前：%s\n后：%s' % (out['before'], out['after']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
