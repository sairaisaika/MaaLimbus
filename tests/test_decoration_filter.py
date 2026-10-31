"""装饰不是目的地：装饰 kind 要从候选里剔除。"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_the_decoration_kinds_are_named_once():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    assert 'DECORATION_KINDS = (' in source
    for kind in ('lattice_step', 'badge_mark', 'node_away_from_player',
                 'neutral_outline_candidate', 'relaxed_node'):
        assert "'%s'" % kind in source
