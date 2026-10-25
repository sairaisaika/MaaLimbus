"""Two readers locate the party; a missing anchor must not empty the board (D284)."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import map_vision  # noqa: E402

FRAME = ROOT / 'evidence/runtime/packaged-mirror-20261025-083025/frame-0001.png'
needs_frame = pytest.mark.skipif(not FRAME.exists(), reason='retained live frame is not present')


def _frame():
    import cv2
    return cv2.imread(str(FRAME))


def _stub(monkeypatch, pair, marker, ring=(1017, 614)):
    monkeypatch.setattr(map_vision, '_bgr_party_point', lambda image: pair)
    calls = []
    monkeypatch.setattr(map_vision, 'player_marker',
                        lambda image: (calls.append(1), marker)[1])
    monkeypatch.setattr(map_vision, 'player_by_ring', lambda image: ring)
    return calls


@needs_frame
def test_the_live_board_the_pair_missed_still_reads_a_party(monkeypatch):
    _stub(monkeypatch, None, (1012, 595))
    assert map_vision.party_point(_frame()) == (1012, 595)


@needs_frame
def test_a_marker_in_the_hud_is_not_the_party(monkeypatch):
    _stub(monkeypatch, None, (1700, 60))
    assert map_vision.party_point(_frame()) is None


@needs_frame
def test_a_marker_in_the_right_chrome_is_not_the_party(monkeypatch):
    _stub(monkeypatch, None, (1900, 600))
    assert map_vision.party_point(_frame()) is None


@needs_frame
def test_two_readers_that_disagree_are_not_the_party(monkeypatch):
    _stub(monkeypatch, None, (48, 273), ring=(1795, 834))
    assert map_vision.party_point(_frame()) is None


def test_the_pair_still_wins_and_the_fallback_is_not_consulted(monkeypatch):
    calls = _stub(monkeypatch, (830, 450), (1012, 595))
    assert map_vision.party_point(_frame()) == (830, 450)
    assert calls == []


@needs_frame
def test_the_real_frame_reads_a_party_now():
    point = map_vision.party_point(_frame())
    assert point is not None, 'the frame the loop stopped on must name its party'
    x, y = point
    assert 0 <= x < 1824 and 108 <= y < 929
