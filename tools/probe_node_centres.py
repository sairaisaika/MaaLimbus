"""量一帧地图上“节点中心”的候选，用来比较不同的中心检测器（只读，不发输入）。

用法::

    python tools/probe_node_centres.py <frame.png> [--mode ring|hex]

为什么要它：操作员给的规范是“只认六边形中心的标志，不看颜色、不看黄圈”（m18377），
而 2026-10-25 实测两种通用几何方法都不够用——

* `--mode hex`（Canny + approxPolyDP==6）：两帧分别只召回 0 与 1 个六边形，
  格线太暗、装饰太多；
* `--mode ring`（中心均值减环形均值，取高分峰）：召回 21–31 个峰，混进 HUD 与装饰，
  间距里看不出 192 px 的格子节距。

结论：这条路需要**模板库**（从标注帧学中心图标），而不是继续调几何阈值。
该工具留着是为了下次一天内复现这两个数字，而不必重写脚本。
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
import cv2
import numpy as np


def ring_peaks(image, *, percentile=99.3, floor=18.0, apart=60):
    g = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    score = cv2.blur(g, (15, 15)) - cv2.blur(g, (71, 71))
    h, w = g.shape
    band = np.zeros_like(score)
    band[int(.18 * h):int(.84 * h), int(.05 * w):int(.95 * w)] = 1.0
    score *= band
    cut = max(float(np.percentile(score[band > 0], percentile)), floor)
    ys, xs = np.where(score >= cut)
    kept = []
    for y, x in zip(ys, xs):
        if all((x - k[0]) ** 2 + (y - k[1]) ** 2 > apart ** 2 for k in kept):
            kept.append((int(x), int(y), round(float(score[y, x]), 1)))
    return sorted(kept, key=lambda item: -item[2]), cut


def hexes(image, *, min_share=4e-4, max_share=1e-2):
    g = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 40, 120)
    found, area = [], g.shape[0] * g.shape[1]
    for contour in cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
        size = cv2.contourArea(contour)
        if not (area * min_share <= size <= area * max_share):
            continue
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 6:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if not (0.7 <= w / max(h, 1) <= 1.4):
            continue
        if all(abs(x + w // 2 - k[0]) > 40 or abs(y + h // 2 - k[1]) > 40 for k in found):
            found.append((x + w // 2, y + h // 2, w, max(h, 1)))
    return sorted(found, key=lambda item: (item[1], item[0]))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print('usage: probe_node_centres.py <frame.png> [--mode ring|hex]')
        return 2
    path = pathlib.Path(args[0])
    mode = 'ring'
    if '--mode' in args:
        mode = args[args.index('--mode') + 1]
    image = cv2.imread(str(path))
    if image is None:
        print('cannot read %s' % path)
        return 1
    h, w = image.shape[:2]
    if mode == 'hex':
        found = hexes(image)
        print('%s  size %dx%d  mode hex  hexagons %d' % (path.name, w, h, len(found)))
        for item in found[:16]:
            print('   ', item)
        return 0
    kept, cut = ring_peaks(image)
    print('%s  size %dx%d  mode ring  cut %.1f  peaks %d' % (path.name, w, h, cut, len(kept)))
    for item in kept[:16]:
        print('   ', item)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
