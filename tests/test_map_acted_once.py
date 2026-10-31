"""被接受过的地图点击，就是这局在地图上的行动权。"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_an_accepted_click_writes_the_action_right():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    index = source.index("if fields.get('outcome') == 'rejected':")
    block = source[index:index + 900]
    assert "fields.get('outcome') == 'accepted'" in block
    assert "self.state['map_acted_once'] = True" in block


def test_the_header_ending_still_reads_the_flag():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    index = source.index('>= 6 or waited >= 20.0')
    block = source[index:index + 400]
    assert "state.get('map_acted_once')" in block
