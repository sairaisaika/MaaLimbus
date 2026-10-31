"""一次点击就是一个承诺（D424）。"""
import pathlib

SOURCE = (pathlib.Path(__file__).resolve().parents[1]
          / 'src' / 'maalimbus' / 'runner.py')


def test_the_commitment_is_written_when_the_click_goes_out():
    source = SOURCE.read_text(encoding='utf-8')
    assert "state['map_committed'] = list(plan['target'])" in source


def test_a_committed_target_is_held_against_a_new_vote():
    source = SOURCE.read_text(encoding='utf-8')
    assert "self.note('map_commitment_held'" in source
    assert "candidates = [committed] + [box for box in candidates" in source


def test_the_hold_is_bounded_by_the_same_retry_budget():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'map_tries' in source
    assert 'map_committed' in source
