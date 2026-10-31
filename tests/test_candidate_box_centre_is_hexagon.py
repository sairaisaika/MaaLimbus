"""候选框的中心必须就是六边形中心（这样每个从 box 算点的调用点都自动正确）。"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus import map_vision as mv


def test_the_shifted_box_centre_equals_the_hexagon_point():
    for box in ([576, 361, 190, 190], [768, 169, 190, 190], [0, 0, 100, 100]):
        cx, cy = mv.node_point(box)
        shifted = [cx - box[2] // 2, cy - box[3] // 2, box[2], box[3]]
        assert (shifted[0] + shifted[2] // 2, shifted[1] + shifted[3] // 2) == (cx, cy)
