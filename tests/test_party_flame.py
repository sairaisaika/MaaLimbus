"""我方标记按灰度几何找：竖直细长高亮块 + 其下方有节点（D281）。

颜色不参与判定：主题包背景色变化不影响（m18524 的批评）。正例来自一次真实运行帧，
反例证明“没有节点框就没有我方”。
"""
import pathlib

import cv2
import pytest

from maalimbus import map_vision

FRAME = pathlib.Path('evidence/runtime/packaged-mirror-20261025-075711/frame-0002.png')


def test_no_boxes_is_no_party():
    assert map_vision.party_from_flame(None, []) is None
    assert map_vision.party_from_flame(None, [[0, 0, 190, 190]]) is None


def test_an_empty_box_list_cannot_anchor_a_party():
    image = cv2.imread(str(FRAME)) if FRAME.exists() else None
    if image is None:
        pytest.skip('retained frame not available')
    assert map_vision.party_from_flame(image, []) is None


def test_the_retained_frame_finds_the_flame_above_a_node():
    image = cv2.imread(str(FRAME))
    if image is None:
        pytest.skip('retained frame not available')
    boxes = [item['box'] for item in map_vision.map_clicks(image)]
    assert boxes, 'the reader found no node on the retained frame'
    point = map_vision.party_from_flame(image, boxes)
    assert point is not None, 'the flame was not found above any node'
    # 实测真值 (663,452)，本函数给出 (670,468)；容差按节点尺寸比例给，不写死像素
    side = max(max(box[2], box[3]) for box in boxes)
    assert abs(point[0] - 663) <= 0.25 * side
    assert abs(point[1] - 452) <= 0.25 * side
