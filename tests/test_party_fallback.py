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
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'glow_point', lambda image: None)
    # The flame is a third, independent reading; this case is about the HUD marker, so
    # the shape reader is silenced instead of being allowed to answer something else.
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    _stub(monkeypatch, None, (1700, 60))
    assert map_vision.party_point(_frame()) is None


@needs_frame
def test_a_marker_in_the_right_chrome_is_not_the_party(monkeypatch):
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'glow_point', lambda image: None)
    _stub(monkeypatch, None, (1900, 600))
    assert map_vision.party_point(_frame()) is None


@needs_frame
def test_two_readers_that_disagree_are_not_the_party(monkeypatch):
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'glow_point', lambda image: None)
    _stub(monkeypatch, None, (48, 273), ring=(1795, 834))
    assert map_vision.party_point(_frame()) is None


def test_the_pair_still_wins_and_the_fallback_is_not_consulted(monkeypatch):
    # The pair is the strongest colour reading, but its own mask can pair two node rings on
    # the red theme, so the shape reader is the tie-breaker and must be silenced here for the
    # case to be about the pair alone (D293).
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: None)
    calls = _stub(monkeypatch, (830, 450), (1012, 595))
    assert map_vision.party_point(_frame()) == (830, 450)
    assert calls == []


@needs_frame
def test_the_real_frame_reads_a_party_now():
    point = map_vision.party_point(_frame())
    assert point is not None, 'the frame the loop stopped on must name its party'
    x, y = point
    assert 0 <= x < 1824 and 108 <= y < 929

def test_the_flame_answers_only_where_the_colour_readers_cannot(monkeypatch):
    """D293: shape, not brightness, is what separates the flame from a node's ring.

    On `packaged-mirror-20261025-075711` all three colour readers are empty and the flame
    is at about (670,467); on `...-101647` the same columns are empty as well and there is
    no flame, so the reader must answer None rather than pick up a gold ring at (498,221).
    """
    import cv2
    import pathlib as _pathlib
    root = _pathlib.Path(__file__).resolve().parents[1]
    flame = cv2.imread(str(root / 'evidence/runtime/packaged-mirror-20261025-075711/frame-0002.png'))
    empty = cv2.imread(str(root / 'evidence/runtime/packaged-mirror-20261025-101647/frame-0002.png'))
    if flame is None or empty is None:
        import pytest
        pytest.skip('archived frames are not available')
    found = map_vision.flame_point(flame)
    assert found is not None
    assert abs(found[0] - 670) <= 20 and abs(found[1] - 467) <= 20, found
    assert map_vision.flame_point(empty) is None

@needs_frame
def test_a_flame_that_disagrees_overrules_the_colour_pair(monkeypatch):
    """D293: live `-133918` anchored on (498,221) for nine clicks -- a node ring, not the party.

    A colour reading inside the board band is not automatically the party; when the flame's
    filled shape is answered far from it, the flame is the fact and the pair is the noise.
    """
    monkeypatch.setattr(map_vision, 'flame_point', lambda image: (900, 800))
    _stub(monkeypatch, (830, 450), None)
    assert map_vision.party_point(_frame()) == (900, 800)

@needs_frame
def test_the_tile_glow_is_a_reading_of_its_own():
    """D295: three live frames, three different answers from the same rule.

    `-134415` hides the flame behind the tile icon and still glows at (508,242); `-075711`
    shows the flame and no large glow; `-101647` glows at (508,242) -- which is also where the
    colour readers land, so the "gold ring" that earlier runs anchored on was the party's own
    tile.
    """
    import cv2
    import pathlib as _pathlib
    root = _pathlib.Path(__file__).resolve().parents[1]

    def frame(run):
        return cv2.imread(str(root / 'evidence/runtime' / run / 'frame-0002.png'))

    glowing, glowing2, flamed = (frame('packaged-mirror-20261025-134415'),
                                 frame('packaged-mirror-20261025-101647'),
                                 frame('packaged-mirror-20261025-075711'))
    if glowing is None or glowing2 is None or flamed is None:
        import pytest
        pytest.skip('archived frames are not available')
    for image in (glowing, glowing2):
        point = map_vision.glow_point(image)
        assert point is not None
        assert abs(point[0] - 508) <= 40 and abs(point[1] - 242) <= 40, point
    assert map_vision.glow_point(flamed) is None
