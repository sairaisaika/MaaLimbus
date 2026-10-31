"""箭头判据按 1080p 帧重标定（D414）。"""
from __future__ import annotations

import pathlib

import cv2
import numpy as np
import pytest

from maalimbus import map_vision

FRAME = (pathlib.Path(__file__).resolve().parents[1]
         / 'evidence' / 'runtime' / 'packaged-mirror-20261031-181831' / 'frame-0002.png')


@pytest.mark.skipif(not FRAME.is_file(), reason='运行目录已被工作区预算回收')
def test_the_arrow_this_frame_draws_is_read():
    image = cv2.imread(str(FRAME))
    got = map_vision.chevron_glyph_pairs(image)
    assert got, 'the 1920x1080 frame draws a chevron at about (953,255)'
    assert abs(got[0][0] - 953) <= 30 and abs(got[0][1] - 255) <= 30


def test_an_empty_frame_has_no_arrow():
    blank = np.zeros((1080, 1920, 3), np.uint8)
    assert map_vision.chevron_glyph_pairs(blank) == []


def test_the_band_admits_the_measured_value():
    low, high = map_vision.CHEVRON_VALUE_BAND
    assert low <= 203 <= high, 'the arrow measured V=203 on the live frame'
