"""点击目标必须是节点尺寸，不能点在节点上的装饰上。"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus import runner


def test_a_node_sized_box_kept_and_an_ornament_dropped():
    clicks = [{'box': [768, 169, 190, 190]}, {'box': [743, 313, 40, 40]}]
    kept, info = runner.node_sized_boxes(clicks, width=1920)
    assert [item['box'] for item in kept] == [[768, 169, 190, 190]]
    assert info == {'min_side': 96, 'widest': 190, 'kept': 1, 'expanded': 0}


def test_small_boxes_only_are_grown_to_node_size_around_their_centre():
    clicks = [{'box': [743, 313, 40, 40], 'point': (763, 333)}]
    kept, info = runner.node_sized_boxes(clicks, width=1920)
    assert info['expanded'] == 1
    x, y, side, _ = kept[0]['box']
    assert side == 192 and (x + side // 2, y + side // 2) == (763, 333)
    assert kept[0]['point'] == (763, 333)


def test_the_floor_scales_with_the_frame():
    small = [{'box': [100, 100, 70, 70]}]
    kept_1920, info_1920 = runner.node_sized_boxes(small, width=1920)
    kept_720, info_720 = runner.node_sized_boxes(small, width=720)
    assert info_1920['min_side'] == 96 and info_1920['expanded'] == 1
    assert info_720['min_side'] == 48 and info_720['expanded'] == 0
    assert [item['box'] for item in kept_720] == [[100, 100, 70, 70]]


def test_an_empty_frame_stays_empty():
    kept, info = runner.node_sized_boxes([], width=1920)
    assert kept == [] and info['kept'] == 0 and info['expanded'] == 0
