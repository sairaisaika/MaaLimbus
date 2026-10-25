"""D296: the tile the game marks is a structural reading of where the party stands.

`map_clicks` finds `lit_node` in the same scan that finds the destinations, so a frame can
name the party by its own mark even when every colour and shape reader answers nothing --
and a colour reading more than one card away from the mark is not the party.
"""

import pathlib
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus import runner  # noqa: E402


def _clicks(with_lit=True):
    clicks = [
        {'box': (193, 169, 190, 190), 'kind': 'gold_badge_node', 'point': (288, 264)},
        {'box': (576, 169, 190, 190), 'kind': 'gold_badge_node', 'point': (671, 264)},
    ]
    if with_lit:
        clicks.append({'box': (480, 224, 40, 40), 'kind': 'lit_node', 'point': (500, 244)})
    return clicks


def _run(monkeypatch, *, party):
    image = np.zeros((1080, 1920, 3), np.uint8)
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (image, 'frame-0001'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, **kw: _clicks())
    monkeypatch.setattr(runner, 'party_point', lambda image: party)
    record = {'scene': 'MAP'}
    name, boxes = runner.candidates_of('/tmp/does-not-matter', record)
    return record, boxes


def test_an_unread_party_is_the_tile_the_game_marks(monkeypatch):
    record, boxes = _run(monkeypatch, party=None)
    assert record['map_party'] == [500, 244]
    assert record['map_party_source'] == 'lit_node'
    assert boxes, 'the marked tile anchors the adjacency, so candidates must survive'


def test_a_reading_on_the_mark_is_refined_to_it(monkeypatch):
    record, _boxes = _run(monkeypatch, party=(508, 242))
    assert record['map_party'] == [500, 244]
    assert record['map_party_source'] == 'lit_node_refined'


def test_a_reading_far_from_the_mark_is_not_the_party(monkeypatch):
    # (671,264) is a real node centre, so it survives `party_on_a_node`; it is 191 px from
    # the mark, i.e. more than a card, so it must not be treated as the marked tile.
    record, _boxes = _run(monkeypatch, party=(671, 264))
    assert record['map_party'] == [671, 264]
    assert record['map_party_source'] == 'read'


def test_without_a_mark_nothing_changes(monkeypatch):
    image = np.zeros((1080, 1920, 3), np.uint8)
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (image, 'frame-0001'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, **kw: _clicks(with_lit=False))
    monkeypatch.setattr(runner, 'party_point', lambda image: None)
    record = {'scene': 'MAP'}
    _name, boxes = runner.candidates_of('/tmp/does-not-matter', record)
    assert record['map_party'] is None
    assert boxes == []
