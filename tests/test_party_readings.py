"""我方读不到时，要说清是哪个读取器空手而归（D294）。"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
import numpy as np
from maalimbus import map_vision

REAL = pathlib.Path('evidence/runtime/packaged-mirror-20261025-085426/frame-0003.png')


def _real():
    import cv2
    image = cv2.imread(str(REAL))
    assert image is not None, 'the retained frame is the fixture'
    return image


def test_every_reader_answers_so_a_null_party_can_be_explained(monkeypatch):
    monkeypatch.setattr(map_vision, '_bgr_party_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'player_marker', lambda image: (10, 20))
    monkeypatch.setattr(map_vision, 'player_by_ring', lambda image: (900, 700))
    monkeypatch.setattr(map_vision, 'party_point', lambda image: None)
    built = map_vision.party_readings(None)
    assert built['pair'] is None and built['marker'] == (10, 20)
    assert built['ring'] == (900, 700) and built['chosen'] is None
    assert built['why'] == 'none'


def test_the_agreed_answer_says_it_came_from_two_readers(monkeypatch):
    monkeypatch.setattr(map_vision, '_bgr_party_point', lambda image: None)
    monkeypatch.setattr(map_vision, 'player_marker', lambda image: (100, 200))
    monkeypatch.setattr(map_vision, 'player_by_ring', lambda image: (110, 205))
    monkeypatch.setattr(map_vision, 'party_point', lambda image: (105, 202))
    built = map_vision.party_readings(None)
    assert built['chosen'] == (105, 202) and built['why'] == 'two_readers_agreed'


def test_the_pair_reader_still_wins_when_it_answers():
    image = _real()
    built = map_vision.party_readings(image)
    assert set(built) == {'pair', 'marker', 'ring', 'chosen', 'why'}
    if built['pair'] is not None:
        assert built['why'] == 'pair'
