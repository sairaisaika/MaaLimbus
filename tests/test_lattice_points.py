"""格阵外推：我方格子常常没被检出，但格子本身是规则网格。"""
from __future__ import annotations

import maalimbus.map_vision as vision

# 两列三行，间距 192，边长 190
BOXES = [[100, 100, 190, 190], [292, 100, 190, 190],
         [100, 292, 190, 190], [292, 292, 190, 190],
         [100, 484, 190, 190], [292, 484, 190, 190]]


def test_the_crossings_are_columns_by_rows():
    points = vision.lattice_points(BOXES)
    assert len(points) == 6
    assert (195.0, 195.0) in points and (387.0, 579.0) in points


def test_a_party_between_boxes_snaps_to_its_crossing():
    # 我方真实站位常常不在任何一个框里（火苗挡住了标记）
    assert vision.nearest_lattice_point((300, 300), BOXES) == (387, 387)


def test_a_party_far_off_the_lattice_is_refused():
    assert vision.nearest_lattice_point((900, 900), BOXES) is None


def test_no_boxes_has_no_lattice():
    assert vision.lattice_points([]) == []
    assert vision.nearest_lattice_point((10, 10), []) is None


def test_dict_items_are_accepted_like_boxes():
    items = [{'box': box, 'kind': 'gold_badge_node'} for box in BOXES]
    assert vision.lattice_points(items) == vision.lattice_points(BOXES)
