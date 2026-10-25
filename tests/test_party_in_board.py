"""A party reading outside the board, or in the HUD band, is not the party."""
import numpy as np

from maalimbus import runner


def _frame(w=1920, h=1080):
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_a_board_reading_is_returned(monkeypatch):
    monkeypatch.setattr(runner, 'party_point', lambda image, board=runner.BOARD: (960, 540))
    assert runner.party_in_board(_frame()) == (960, 540)


def test_a_reading_in_the_bottom_hud_band_is_refused(monkeypatch):
    monkeypatch.setattr(runner, 'party_point', lambda image, board=runner.BOARD: (960, 1000))
    assert runner.party_in_board(_frame()) is None


def test_a_reading_outside_the_board_is_refused(monkeypatch):
    monkeypatch.setattr(runner, 'party_point', lambda image, board=runner.BOARD: (1850, 300))
    assert runner.party_in_board(_frame()) is None


def test_no_reading_stays_no_reading(monkeypatch):
    monkeypatch.setattr(runner, 'party_point', lambda image, board=runner.BOARD: None)
    assert runner.party_in_board(_frame()) is None
