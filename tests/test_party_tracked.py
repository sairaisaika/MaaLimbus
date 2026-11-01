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
    _stub(monkeypatch, party_point=(900, 900), flame_point=None, player_marker=(140, 110))
    point, source = vision.party_tracked(object(), (120, 100))
    assert point == (140, 110) and source == 'tracked'


def test_a_reader_beyond_the_limit_is_ignored(monkeypatch):
    _stub(monkeypatch, party_point=(900, 900), flame_point=None, player_marker=(100, 100))
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


def test_the_flame_outranks_continuity(monkeypatch):
    """D434: the flame is the party's own mark, so it wins over "nearest to last frame"."""
    import maalimbus.map_vision as mv

    monkeypatch.setattr(mv, 'party_point', lambda image: (1055, 190))
    monkeypatch.setattr(mv, '_bgr_party_point', lambda image: None)
    monkeypatch.setattr(mv, 'glow_point', lambda image: (575, 335))
    monkeypatch.setattr(mv, 'flame_point', lambda image: (1055, 190))
    monkeypatch.setattr(mv, 'player_marker', lambda image: (1249, 259))
    point, source = mv.party_tracked(object(), previous=(1249, 259))
    assert point == (1055, 190) and source == 'flame'


def test_continuity_still_decides_when_no_flame_is_read(monkeypatch):
    import maalimbus.map_vision as mv

    monkeypatch.setattr(mv, 'party_point', lambda image: (1055, 190))
    monkeypatch.setattr(mv, '_bgr_party_point', lambda image: None)
    monkeypatch.setattr(mv, 'glow_point', lambda image: (575, 335))
    monkeypatch.setattr(mv, 'flame_point', lambda image: None)
    monkeypatch.setattr(mv, 'player_marker', lambda image: (1249, 259))
    point, source = mv.party_tracked(object(), previous=(1249, 259))
    assert point == (1249, 259) and source == 'tracked'


def test_every_reader_out_of_reach_carries_the_last_point(monkeypatch):
    """D437: nothing near last frame means every reader guessed; carry the point."""
    _stub(monkeypatch, party_point=(60, 60), flame_point=None,
          glow_point=(3000, 3000), player_marker=(20, 900))
    point, source = vision.party_tracked(object(), (900, 900), limit=50)
    assert point == (900, 900) and source == 'carried'
