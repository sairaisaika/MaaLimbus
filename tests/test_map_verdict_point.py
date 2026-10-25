"""A verdict says where the click went inside the box it names (D203)."""
import sys
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus import runner  # noqa: E402


def _loop(state=None):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.state = dict(state or {})
    loop.artifacts = {'steps': []}
    loop.journal = None
    loop.notes = []
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    return loop


def test_the_verdict_records_the_centre_of_the_box():
    loop = _loop()
    loop._map_verdict(outcome='accepted', target=[545, 239, 190, 190], reason='x')
    _name, fields = loop.notes[-1]
    assert fields['point'] == [640, 334]


def test_a_verdict_that_already_knows_its_point_keeps_it():
    loop = _loop()
    loop._map_verdict(outcome='rejected', target=[0, 0, 40, 40], point=[1, 2], reason='x')
    assert loop.notes[-1][1]['point'] == [1, 2]


def test_a_verdict_without_a_target_gains_no_point():
    loop = _loop()
    loop._map_verdict(outcome='superseded', reason='x')
    assert 'point' not in loop.notes[-1][1]
