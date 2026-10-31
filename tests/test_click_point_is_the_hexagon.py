"""候选的点击点必须是六边形，不是框中心。"""
from __future__ import annotations

import sys
import pathlib

import cv2
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus import map_vision as mv

FRAME = pathlib.Path('evidence/runtime/packaged-mirror-20261031-135856/frame-0001.png')


@pytest.mark.skipif(not FRAME.is_file(), reason='retained frame missing')
def test_every_candidate_reports_its_hexagon_centre():
    image = cv2.imread(str(FRAME))
    clicks = mv.map_clicks(image)
    assert clicks
    for item in clicks:
        assert tuple(item['point']) == mv.node_point(item['box'])
