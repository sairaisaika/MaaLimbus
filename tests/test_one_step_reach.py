"""只能走一格：超过一格的候选不进列表。"""
from __future__ import annotations

import pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]


def test_the_reach_is_one_and_a_quarter_steps():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    index = source.index('map_step_reach')
    block = source[max(0, index - 1200):index]
    assert '1.25 * _step' in block
    assert "record['map_step_reach']" in source
