"""一帧之内队伍走不了两格（D416）。"""
from __future__ import annotations

import inspect

from maalimbus import runner


def test_the_jump_guard_reads_the_previous_centre():
    body = inspect.getsource(runner.candidates_of)
    assert "record.get('party_node')" in body
    assert "party_jumped" in body
    # 限制由帧宽推出，不是写死的像素
    assert "0.12 * image.shape[1]" in body


def test_the_guard_sits_before_the_candidates_are_read():
    body = inspect.getsource(runner.candidates_of)
    guard = body.index('party_jumped')
    read = body.index('map_clicks(image, template=node_badge_template(), player=party)')
    assert guard < read, 'the guard must run before the party is handed to map_clicks'
