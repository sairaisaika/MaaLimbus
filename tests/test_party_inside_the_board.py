"""The party point must land on the board.

`map_vision.player_readings` scores readings against the flame and returns them best-first,
but a frame can hold only the HUD's yellow: two live frames prove it --
`evidence/runtime/packaged-mirror-20261025-061838/frame-0001.png` (1920x1080) and
`evidence/runtime/lattice-probe/zoomed2.png` (1280x720) each yield exactly one reading at
(1616,82) and (1077,54), i.e. the top-right panel, while the torch is drawn mid-page.  The
board gate then refused the frame and `candidates_of` refused every candidate with it.

The selection is therefore: walk the scored readings in order and keep the first one inside
the board; a frame whose only reading is the HUD still answers None.
"""
import types

from maalimbus import map_vision, runner


def _image(width=1920, height=1080):
    return types.SimpleNamespace(shape=(height, width, 3))


def test_a_board_reading_behind_a_hud_reading_is_the_party(monkeypatch):
    monkeypatch.setattr(map_vision, 'player_readings',
                        lambda image, markers: [(1616, 82), (694, 384)])
    assert runner.party_point(_image()) == (694, 384)


def test_a_frame_whose_only_reading_is_the_hud_answers_none(monkeypatch):
    monkeypatch.setattr(map_vision, 'player_readings', lambda image, markers: [(1616, 82)])
    monkeypatch.setattr(map_vision, 'party_point', lambda image: None)
    assert runner.party_point(_image()) is None


def test_the_board_edge_is_the_boundary(monkeypatch):
    left, top, right, bottom = runner.BOARD
    width, height = 1920, 1080
    inside = (int(right * width) - 1, int(top * height) + 1)
    outside = (int(right * width) + 1, int(top * height) + 1)
    monkeypatch.setattr(map_vision, 'player_readings', lambda image, markers: [outside, inside])
    monkeypatch.setattr(map_vision, 'party_point', lambda image: None)
    assert runner.party_point(_image()) == inside


def test_no_image_answers_none():
    assert runner.party_point(None) is None
