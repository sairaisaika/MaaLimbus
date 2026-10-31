"""记住的格心必须本帧还有节点撑着（D412）。"""
from __future__ import annotations

from maalimbus import map_vision


def _boxes(*centres, side=190):
    half = side // 2
    return [[cx - half, cy - half, side, side] for cx, cy in centres]


def test_a_centre_with_no_node_under_it_is_not_kept():
    """锁在 (860,248)，而本帧的框在别处：必须重新吸附，不能沿用。"""
    boxes = _boxes((1439, 189), (1249, 284))
    point, confirmed = map_vision.lock_party_to_node((861, 249), boxes, previous=(860, 248))
    # 该点不在任何节点上，所以不能被“确认”成格心；它退回本帧自己的读数而不是沿用旧锁。
    assert confirmed != (860, 248)


def test_a_centre_that_still_has_a_node_is_kept():
    boxes = _boxes((860, 248), (1052, 248))
    point, confirmed = map_vision.lock_party_to_node((866, 250), boxes, previous=(860, 248))
    assert point == (860, 248)
    assert confirmed == (860, 248)


def test_no_boxes_keeps_the_old_behaviour():
    point, confirmed = map_vision.lock_party_to_node((860, 248), [], previous=(860, 248))
    assert point == (860, 248)
