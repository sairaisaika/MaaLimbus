"""连续性读数：给出上一帧位置时，选离它最近、且在限内的那个读数。"""
from __future__ import annotations

import maalimbus.map_vision as vision


def _stub(monkeypatch, **points):
    for name, point in points.items():
        monkeypatch.setattr(vision, name, lambda image, _p=point: _p)


def test_without_previous_the_primary_reader_answers(monkeypatch):
    _stub(monkeypatch, party_point=(100, 100), glow_point=(900, 900))
    assert vision.party_tracked(object()) == ((100, 100), 'primary')


def test_a_near_reader_wins_over_the_primary(monkeypatch):
    _stub(monkeypatch, party_point=(900, 900), flame_point=(140, 110))
    point, source = vision.party_tracked(object(), (120, 100))
    assert point == (140, 110) and source == 'tracked'


def test_a_reader_beyond_the_limit_is_ignored(monkeypatch):
    _stub(monkeypatch, party_point=(900, 900), flame_point=(100, 100))
    point, source = vision.party_tracked(object(), (900, 900), limit=50)
    assert point == (900, 900) and source == 'tracked'
    point, source = vision.party_tracked(object(), (100, 100), limit=50)
    assert point == (100, 100) and source == 'tracked'


def test_a_reader_that_raises_is_skipped(monkeypatch):
    def boom(image):
        raise RuntimeError('unreadable')
    monkeypatch.setattr(vision, 'party_point', lambda image: (500, 500))
    monkeypatch.setattr(vision, 'glow_point', boom)
    assert vision.party_tracked(object(), (510, 500)) == ((500, 500), 'tracked')
