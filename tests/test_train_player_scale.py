"""The locomotive thresholds are 1080p pixels, so they scale with the frame.

The flame is 271 px on a 1920x1080 capture (the reading the thresholds were measured on)
and 45 px on `evidence/runtime/lattice-probe/zoomed2.png` (1280x720), where `min_area=60`
discarded it and `train_player` answered None -- which is why 720p runs had no party point.
"""
import pathlib

import pytest

from maalimbus import map_vision

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relative):
    import cv2

    path = ROOT / relative
    if not path.exists():
        pytest.skip('retained frame is not present')
    return cv2.imread(str(path))


def test_a_720p_torch_is_found_after_scaling():
    image = _read('evidence/runtime/lattice-probe/zoomed2.png')
    assert image.shape[1] == 1280
    point = map_vision.train_player(image)
    assert point is not None
    x, y = point
    assert 680 <= x <= 730 and 300 <= y <= 350


def test_a_1080p_torch_is_still_found():
    image = _read('evidence/runtime/packaged-mirror-20261025-061838/frame-0001.png')
    assert image.shape[1] == 1920
    point = map_vision.train_player(image)
    assert point is not None
    x, y = point
    assert 1030 <= x <= 1080 and 440 <= y <= 520


def test_a_blank_frame_has_no_locomotive():
    import numpy as np

    blank = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert map_vision.train_player(blank) is None
