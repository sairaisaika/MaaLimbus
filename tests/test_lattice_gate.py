"""我方必须在游戏画的格阵内，而不是在屏幕的某个比例带里。"""
from __future__ import annotations

import pathlib

import cv2
import pytest

import maalimbus.map_vision as vision

FRAME = (pathlib.Path(__file__).resolve().parents[1]
         / 'tests/fixtures/frames/map-20261031-165116/frame-0001.png')


def _boxes():
    image = cv2.imread(str(FRAME))
    assert image is not None, 'fixture frame missing'
    return [item['box'] for item in (vision.map_clicks(image) or [])]


def test_the_lattice_box_grows_by_half_a_step():
    assert vision.lattice_box([[100, 100, 190, 190]]) == (5.0, 5.0, 385.0, 385.0)
    assert vision.lattice_box([]) is None


def test_the_real_frame_puts_the_party_inside_and_the_decoration_outside():
    boxes = _boxes()
    assert boxes, 'the fixture frame has no nodes'
    assert vision.inside_lattice((862, 552), boxes) is True   # 真值：我方
    assert vision.inside_lattice((860, 209), boxes) is False  # glow_point 读到的灰装饰


def test_no_boxes_accepts_everything():
    assert vision.inside_lattice((10, 10), []) is True
    assert vision.inside_lattice(None, [[0, 0, 10, 10]]) is True
