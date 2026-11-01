"""外推点不许落在刚离开的格子上（D426）。"""
import pathlib

SOURCE = (pathlib.Path(__file__).resolve().parents[1]
          / 'src' / 'maalimbus' / 'map_vision.py')


def test_the_extrapolation_refuses_the_tile_it_came_from():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'def _backwards(point):' in source
    assert 'previous is None or side is None' in source
    assert 'return (dx * dx + dy * dy) ** 0.5 < float(side) * 0.5' in source


def test_the_runner_hands_the_previous_party_over():
    runner = (pathlib.Path(__file__).resolve().parents[1]
              / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    assert 'previous=_previous_party' in runner
    assert '_previous_party = previous_party' in runner
