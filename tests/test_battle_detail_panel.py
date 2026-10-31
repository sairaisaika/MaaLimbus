"""战斗中的敌人详情面板：HUD 被盖住时，面板自己就是战斗的证据。

live `packaged-mirror-20261031-125442`：Resume 之后进到一场还在打的战斗，敌人详情面板
盖住了左上角的 WAVE/TURN，34 条 OCR 里没有 WAVE/TURN/START/Win/Rate/Damage，页面被判成
UNKNOWN；18 次读全部落空，`page_unreadable_after_waiting` 结束了那次 600 秒。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

from maalimbus.battle_vision import battle_hud  # noqa: E402
from maalimbus.vision import Text  # noqa: E402

RUN = REPO / 'evidence' / 'runtime' / 'packaged-mirror-20261031-125442'


def _records(path):
    frame = json.loads(path.read_text(encoding='utf-8'))
    rows = [Text(text=row.get('text') or '', box=tuple(row.get('box') or (0, 0, 0, 0)),
                 score=float(row.get('score') or 0.0)) for row in (frame.get('ocr') or [])]
    return rows, frame.get('size')


def test_the_detail_panel_is_a_battle_screen():
    if not (RUN / 'frame-0007.json').is_file():
        pytest.skip('retained frame not in this checkout')
    rows, size = _records(RUN / 'frame-0007.json')
    hud = battle_hud(rows, size)
    assert hud is not None
    assert hud.get('detail_panel') is True
    assert hud.get('wave') is None and hud.get('turn') is None
    assert 'no wave/turn is claimed' in hud.get('scope', '')


def test_a_menu_frame_is_not_a_battle_screen():
    if not (RUN / 'frame-0001.json').is_file():
        pytest.skip('retained frame not in this checkout')
    rows, size = _records(RUN / 'frame-0001.json')
    assert battle_hud(rows, size) is None


def test_one_panel_title_alone_is_not_enough():
    rows = [Text(text='Resistances', box=(480, 813, 120, 24), score=0.99)]
    assert battle_hud(rows, (1920, 1080)) is None


def test_both_titles_far_from_their_band_are_not_enough():
    rows = [Text(text='Resistances', box=(480, 100, 120, 24), score=0.99),
            Text(text='Fatal', box=(744, 140, 60, 32), score=0.99)]
    assert battle_hud(rows, (1920, 1080)) is None
