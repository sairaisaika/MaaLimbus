"""The lit path is the game's own answer, so it is offered first -- not last.

`path_node` is the cyan step the page lights between the party and the next node (measured on
`evidence/runtime/window-20261007-174525/frame-0002.png`: hue 94, saturation 161, fully lit),
while `lit_ring` and `lattice_step` are the guesses that never produced an accepted click.
"""
import pathlib

import pytest

from maalimbus import runner

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_the_path_is_ranked_before_every_node_kind():
    order = runner.CLICK_KIND_ORDER
    assert order[0] == 'path_node'
    for kind in ('lit_icon', 'gold_badge_node', 'lit_node', 'badge_mark'):
        assert order.index('path_node') < order.index(kind)


def test_the_path_may_be_clicked_and_the_guesses_may_not():
    assert 'path_node' not in runner.CLICK_KINDS_WITHOUT_EVIDENCE
    assert set(runner.CLICK_KINDS_WITHOUT_EVIDENCE) == {'lit_ring', 'lattice_step'}


def test_the_order_covers_every_kind_the_reader_can_emit():
    from maalimbus import map_vision
    assert set(runner.CLICK_KIND_ORDER) >= {
        'path_node', 'lit_icon', 'bright_lit_icon', 'gold_badge_node', 'lit_node',
        'relaxed_node', 'badge_mark', 'neutral_outline_candidate',
        'node_away_from_player', 'lit_ring', 'lattice_step'}
