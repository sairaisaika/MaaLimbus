"""六边形中心在节点框中心上方，按框高的比例抬升。"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus import map_vision as mv


def test_the_measured_box_lands_on_the_hexagon():
    # `-135856/frame-0001`: box centre (671,264), hexagon about (671,230).
    assert mv.node_point([576, 169, 190, 190]) == (671, 230)


def test_the_lift_is_a_share_of_the_box_not_a_pixel_count():
    small = mv.node_point([0, 0, 100, 100])
    large = mv.node_point([0, 0, 200, 200])
    assert small == (50, 50 - 18)
    assert large == (100, 100 - 36)


def test_a_square_box_is_where_its_centre_says():
    assert mv.node_point([10, 20, 40, 40]) == (30, 40 - 7)
