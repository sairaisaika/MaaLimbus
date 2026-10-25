"""A refusal names the reading that failed, and a known party is not a missing one.

The D260 guard used a retained frame as its negative sample; once the party reader was
fixed (D261/D262) that sample started reading a party, which made the guard unreachable.
These cases build the record instead, so the contract is pinned without depending on a
frame that keeps improving.
"""
import numpy as np
import pytest

from maalimbus import runner


BOXES = [{'box': (400, 300, 190, 190), 'kind': 'gold_badge_node'},
         {'box': (700, 300, 190, 190), 'kind': 'path_node'}]


def _record():
    return {'scene': 'MAP', 'frame': 'test', 'ocr': []}


def _stub(monkeypatch, party):
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (np.zeros((1080, 1920, 3), np.uint8), 'test'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, template=None: [dict(item) for item in BOXES])
    monkeypatch.setattr(runner, 'party_point', lambda image: party)
    monkeypatch.setattr(runner, 'node_badge_template', lambda: None)
    monkeypatch.setattr(runner, 'header_chrome', lambda record: None)


def test_an_unread_party_refuses_and_says_which_reading_failed(monkeypatch):
    _stub(monkeypatch, None)
    record = _record()
    name, boxes = runner.candidates_of('/', record)
    assert boxes == []
    assert record['map_candidates_refused'] == {'party': None, 'read': 2}


def test_a_known_party_is_used_instead_of_refusing(monkeypatch):
    _stub(monkeypatch, None)
    record = _record()
    name, boxes = runner.candidates_of('/', record, fallback_party=(420, 380))
    assert record['map_party_from_cache'] is True
    assert record['map_party'] == [420, 380]
    assert 'map_candidates_refused' not in record
    assert boxes and all(len(box) == 4 for box in boxes)


def test_a_readable_party_is_not_marked_as_cached(monkeypatch):
    _stub(monkeypatch, (420, 380))
    record = _record()
    name, boxes = runner.candidates_of('/', record)
    assert 'map_party_from_cache' not in record
    assert 'map_candidates_refused' not in record


def test_the_floor_cache_is_bounded_and_cleared_by_a_new_floor(monkeypatch):
    """The step hands the reader the last point of THIS floor, never one from another."""
    from maalimbus import runner as r
    import inspect
    body = inspect.getsource(r.MirrorRunner.step)
    assert 'MAP_PARTY_CACHE_SECONDS' in body
    assert "self.state.get('map_party_floor') == floor" in body
    assert 0 < r.MAP_PARTY_CACHE_SECONDS <= 120
