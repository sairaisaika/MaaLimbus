"""节点预览面板：点格子只会打开它，点 Enter 才真的进去（用户 2026-10-31 指出）。"""
from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import vision  # noqa: E402

SIZE = (1920, 1080)


def _records(*items):
    # `vision.find` 读的是属性而不是字典（ocr 记录在进程里是对象，落盘才变成 dict）
    return [types.SimpleNamespace(text=text, box=box, score=score)
            for text, box, score in items]


ENTER = ('Enter', (1660, 900, 120, 40), 0.95)
NAME = ('Thick Rumbling Hum', (820, 220, 520, 46), 0.93)
HEADER = ('Exploring Floor', (58, 127, 330, 51), 0.95)


def test_a_panel_with_its_own_enter_is_a_preview():
    found = vision.node_preview(_records(NAME, ENTER), SIZE)
    assert found is not None and 'enter' in found


def test_a_map_frame_that_also_reads_exploring_is_not_a_preview():
    # `-161115` 的 UNKNOWN 帧里有 'Exploring Floor'：那是地图本身缺 floor 数字，
    # 不是预览面板。这条守卫就是为此存在的。
    assert vision.node_preview(_records(HEADER, ENTER), SIZE) is None


def test_no_enter_means_no_preview():
    assert vision.node_preview(_records(NAME), SIZE) is None


def test_an_enter_outside_the_panel_zone_is_not_the_panels_enter():
    # 镜牢入口页也有一个 Enter，但它在画面中部偏下，不在预览面板的右下角。
    entry = ('Enter', (1100, 700, 120, 40), 0.95)
    assert vision.node_preview(_records(NAME, entry), SIZE) is None
