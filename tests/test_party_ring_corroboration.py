"""A ring reading that lands on a ring the page drew is a second opinion, not noise.

`-143225/frame-0001` (live, 2026-10-25) has eight candidates on the map, `player_marker`
None, `_bgr_party_point` None, `flame_point` None and `glow_point` None, yet
`player_by_ring` answers (1091,252) while `lit_rings` puts a ring at (1056,246) -- 35 px
apart on a 192 px lattice.  Before this rule `party_point` answered None and the run
offered no node at all (`no_candidate_node_observed`), so the map was unreadable for a
reason that had nothing to do with the map.
"""

import pathlib

import cv2
import pytest

from maalimbus import map_vision

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME = ROOT / 'evidence' / 'runtime' / 'packaged-mirror-20261025-143225' / 'frame-0002.png'


def test_a_ring_that_agrees_with_a_drawn_ring_is_the_party():
    if not FRAME.is_file():
        pytest.skip('the retained frame is not in this checkout')
    image = cv2.imread(str(FRAME))
    assert map_vision.player_marker(image) is None
    assert map_vision.party_point(image) is not None


def test_a_ring_far_from_every_drawn_ring_is_not_the_party(monkeypatch):
    image = cv2.imread(str(FRAME)) if FRAME.is_file() else None
    if image is None:
        pytest.skip('the retained frame is not in this checkout')
    monkeypatch.setattr(map_vision, 'player_marker', lambda image: None)
    monkeypatch.setattr(map_vision, '_bgr_party_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'glow_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'lit_rings', lambda image, **kw: [(1400, 900)])
    assert map_vision.party_point(image) is None


def test_a_marker_that_agrees_still_answers_first(monkeypatch):
    image = cv2.imread(str(FRAME)) if FRAME.is_file() else None
    if image is None:
        pytest.skip('the retained frame is not in this checkout')
    monkeypatch.setattr(map_vision, 'player_marker', lambda image: (1091, 252))
    monkeypatch.setattr(map_vision, '_bgr_party_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'glow_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'lit_rings', lambda image, **kw: [])
    assert map_vision.party_point(image) == (1091, 252)
