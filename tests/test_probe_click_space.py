"""点击空间探针：只做一次点击，差异要能被读出来。"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'probe_click_space', REPO / 'tools' / 'probe_click_space.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_same_picture_has_no_difference(tmp_path):
    import cv2
    tool = _tool()
    frame = np.zeros((40, 60, 3), np.uint8)
    first, second = tmp_path / 'a.png', tmp_path / 'b.png'
    cv2.imwrite(str(first), frame)
    cv2.imwrite(str(second), frame)
    assert tool._diff(first, second) == 0.0


def test_a_changed_picture_has_a_difference(tmp_path):
    import cv2
    tool = _tool()
    first, second = tmp_path / 'a.png', tmp_path / 'b.png'
    cv2.imwrite(str(first), np.zeros((40, 60, 3), np.uint8))
    cv2.imwrite(str(second), np.full((40, 60, 3), 200, np.uint8))
    assert tool._diff(first, second) > 10


def test_a_missing_file_is_not_a_zero():
    tool = _tool()
    assert tool._diff(REPO / 'build' / 'nope-a.png', REPO / 'build' / 'nope-b.png') is None
