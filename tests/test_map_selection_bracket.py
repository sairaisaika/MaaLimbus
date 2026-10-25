"""The bracket names a node type; it never reorders the candidates (D205, corrected)."""
import sys
import pathlib
import json

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

import maalimbus.runner as runner  # noqa: E402


def _record(scene='MAP'):
    return {'scene': scene}


def _wire(monkeypatch, boxes, bracket):
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (np.zeros((1080, 1920, 3), np.uint8), 'frame-0001.png'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, template=None: [{'box': list(b), 'kind': 'lit_icon'} for b in boxes])
    monkeypatch.setattr(runner, 'header_chrome', lambda record: None)
    # D280: the party must read on a node before any candidate is offered; the fixtures
    # below put nodes at (600,500) and (700,500), 40 px a side.
    monkeypatch.setattr(runner, 'party_point', lambda image: (620, 520))
    monkeypatch.setattr(runner, 'adjacent_to', lambda party, boxes: [list(b) for b in boxes])
    monkeypatch.setattr(runner, 'order_candidates', lambda boxes, kinds: [list(b) for b in boxes])
    monkeypatch.setattr(runner.map_vision, 'selection_bracket', lambda image: bracket)


def test_a_bracketed_box_is_recorded_as_a_hard_node(monkeypatch):
    boxes = [(600, 500, 40, 40), (700, 500, 40, 40)]
    _wire(monkeypatch, boxes, (690, 495, 60, 50))
    record = _record()
    _name, ordered = runner.candidates_of('/tmp/x', record)
    assert ordered == [[600, 500, 40, 40], [700, 500, 40, 40]]
    assert record['map_hard_node'] == [700, 500, 40, 40]


def test_a_bracket_on_no_adjacent_box_is_ignored(monkeypatch):
    boxes = [(600, 500, 40, 40)]
    _wire(monkeypatch, boxes, (900, 200, 60, 50))
    record = _record()
    _name, ordered = runner.candidates_of('/tmp/x', record)
    assert ordered == [[600, 500, 40, 40]]
    assert record['map_hard_node'] is None


def test_no_bracket_leaves_the_order_alone(monkeypatch):
    boxes = [(600, 500, 40, 40), (700, 500, 40, 40)]
    _wire(monkeypatch, boxes, None)
    record = _record()
    _name, ordered = runner.candidates_of('/tmp/x', record)
    assert ordered == [[600, 500, 40, 40], [700, 500, 40, 40]]
    assert record['map_hard_node'] is None


def test_the_record_stays_json_serialisable(monkeypatch):
    boxes = [(600, 500, 40, 40)]
    _wire(monkeypatch, boxes, (595, 495, 60, 50))
    record = _record()
    runner.candidates_of('/tmp/x', record)
    json.dumps(record['map_hard_node'])


def test_a_non_map_page_offers_nothing(monkeypatch):
    _wire(monkeypatch, [(600, 500, 40, 40)], (595, 495, 60, 50))
    assert runner.candidates_of('/tmp/x', _record('SHOP')) == (None, None)
