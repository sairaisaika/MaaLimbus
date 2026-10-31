"""一格可达性：两格外的目标不能进入候选（D427）。"""
import pathlib

SOURCE = (pathlib.Path(__file__).resolve().parents[1]
          / 'src' / 'maalimbus' / 'runner.py')


def test_the_gate_exists_and_uses_the_frame_side_as_its_ruler():
    source = SOURCE.read_text(encoding='utf-8')
    assert "self.note('map_candidates_too_far'" in source
    assert '0.55 * _side_hint <= dist <= 1.75 * _side_hint' in source


def test_the_side_comes_from_the_candidates_not_a_constant():
    source = SOURCE.read_text(encoding='utf-8')
    assert '_side_hint = _sides[len(_sides) // 2]' in source
    assert 'int(box[2]) > 100' in source
