"""箭头画的方向：只有它指的这一侧才算“下一步”。"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus.runner import _on_axis


def _box(cx, cy, side=190):
    return [cx - side // 2, cy - side // 2, side, side]


def test_a_tile_in_front_is_on_the_axis():
    assert _on_axis(_box(1240, 190), (1050, 190), (1.0, 0.0)) is True


def test_a_tile_behind_the_party_is_not():
    assert _on_axis(_box(860, 190), (1050, 190), (1.0, 0.0)) is False


def test_a_diagonal_tile_within_the_cone_is_kept():
    assert _on_axis(_box(1180, 300), (1050, 190), (1.0, 0.0), share=0.5) is True


def test_a_tile_that_is_exactly_across_is_dropped():
    assert _on_axis(_box(1050, 360), (1050, 190), (1.0, 0.0)) is False


def test_a_party_sitting_on_the_tile_is_not_diverted():
    assert _on_axis(_box(1050, 190), (1050, 190), (0.0, 1.0)) is True
