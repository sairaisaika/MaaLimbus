"""车头图标 + ×2：用户提的“下一格 = P + 2(A - P)”，在真实帧上验证。"""
from __future__ import annotations

import json
import pathlib
import sys

import cv2
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import map_vision  # noqa: E402

FIXTURE = ROOT / 'tests' / 'fixtures' / 'frames' / 'map-20261031-154323'


def _frame():
    path = FIXTURE / 'frame-0001.png'
    if not path.is_file():
        pytest.skip('真实地图帧 fixture 不在仓库里')
    return cv2.imread(str(path))


def test_the_train_icon_gives_the_next_tile():
    image = _frame()
    party = map_vision.party_point(image)
    assert party is not None
    nxt = map_vision.train_next_point(image, party)
    assert nxt is not None, '这一帧有车头图标，必须给出下一格'
    # 目视下一格 (1247,255)；公式 (1252,287) 差 32 px，用半格(95) 做容差
    assert abs(nxt[0] - 1247) <= 95 and abs(nxt[1] - 255) <= 95, nxt
    # 方向必须是“我方的右侧”，否则等于把队伍往回带
    assert nxt[0] > party[0]


def test_no_party_means_no_next_tile():
    assert map_vision.train_next_point(_frame(), None) is None


def test_a_band_without_an_icon_answers_none():
    image = _frame()
    party = map_vision.party_point(image)
    # 把右侧整条带涂黑，模拟“这一帧没有车头图标可选”
    blanked = image.copy()
    blanked[:, party[0] + 40:] = 0
    assert map_vision.train_next_point(blanked, party) is None
