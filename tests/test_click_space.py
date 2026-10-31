"""识别帧坐标 → 设备坐标：不知道就不动。"""
from __future__ import annotations

from maalimbus.click_space import scale_box, scale_point


def test_a_1920_point_becomes_a_1280_point():
    assert scale_point([960, 540], (1920, 1080), (1280, 720)) == [640, 360]


def test_a_fractional_result_is_rounded_not_truncated():
    # 1247 * 2/3 = 831.33…，截断会给 831，四舍五入给 831；用 1249 区分：1249*2/3=832.67
    assert scale_point([1249, 264], (1920, 1080), (1280, 720)) == [833, 176]


def test_the_same_size_changes_nothing():
    point = [960, 540]
    assert scale_point(point, (1920, 1080), (1920, 1080)) == point


def test_an_unknown_size_leaves_the_point_alone():
    point = [960, 540]
    assert scale_point(point, None, (1280, 720)) == point
    assert scale_point(point, (1920, 1080), None) == point
    assert scale_point(point, (0, 0), (1280, 720)) == point
    assert scale_point(point, (1920, 1080), (1280, 0)) == point


def test_a_box_keeps_its_meaning():
    box = scale_box([1152, 169, 190, 190], (1920, 1080), (1280, 720))
    assert box == [768, 113, 127, 126]
