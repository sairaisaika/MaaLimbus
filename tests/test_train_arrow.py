"""下一格 = P + 2(箭头 - P)（D414）。"""
from __future__ import annotations

import pathlib

import cv2
import pytest

from maalimbus import map_vision, runner

FRAME = (pathlib.Path(__file__).resolve().parents[1]
         / 'evidence' / 'runtime' / 'packaged-mirror-20261031-181831' / 'frame-0002.png')


@pytest.mark.skipif(not FRAME.is_file(), reason='运行目录已被工作区预算回收')
def test_the_arrow_gives_the_next_tile_and_not_the_boss():
    image = cv2.imread(str(FRAME))
    got = map_vision.train_next_point(image, (860, 248))
    assert got is not None
    assert abs(got[0] - 1046) <= 30 and abs(got[1] - 262) <= 30, got
    # 红 Boss 在 1251：外推不能再落在它身上
    assert abs(got[0] - 1251) > 100


def test_the_window_is_expressed_in_steps():
    low, high = runner.train_distance_bounds(190)
    assert (round(low), round(high)) == (152, 304)
    assert runner.train_distance_ok((1046, 262), (860, 248), 190)
