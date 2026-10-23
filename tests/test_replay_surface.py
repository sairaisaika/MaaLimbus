"""One replay surface: frames in, refusals out, and only one implementation.

The promise of an offline replay is one sentence, and this file is where it is
tested instead of restated. Two halves:

* behaviour, on `ReplayFrames` (the half that needs no Maa library): input is
  refused unless the scenario declares the input it expects, an accepted input is
  recorded, and `screencap` hands out a copy so a tool cannot mutate the fixture;
* the population, over `tools/verify_*_replay.py`: no tool may re-implement the
  mechanical surface or skip the shared base, because that is how the promise
  drifted ten ways before `maalimbus.replay` existed.

The counter-examples matter as much as the passing cases: a synthetic tool that
defines its own `connect` must be reported, and an `expects` callable that says no
must still refuse.
"""
import ast
import importlib.util
import pathlib

import numpy as np
import pytest

from maalimbus.replay import OFFLINE_UUID, ReplayFrames, ReplayInputRefused

ROOT = pathlib.Path(__file__).resolve().parents[1]
INVENTORY = ROOT / 'tools' / 'replay_inventory.py'


def _frame(value=0, size=(12, 16)):
    return np.full((size[0], size[1], 3), value, dtype='uint8')


def _inventory_module():
    spec = importlib.util.spec_from_file_location('replay_inventory', INVENTORY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- behaviour ---------------------------------------------------------------


def test_a_replay_that_declares_nothing_refuses_every_input():
    replay = ReplayFrames(_frame())
    for kind, call in (('click', lambda: replay.click(1, 2)),
                       ('swipe', lambda: replay.swipe(1, 2, 3, 4, 600)),
                       ('touch_down', lambda: replay.touch_down(0, 1, 2, 1.0)),
                       ('touch_move', lambda: replay.touch_move(0, 1, 2, 1.0)),
                       ('touch_up', lambda: replay.touch_up(0)),
                       ('key', lambda: replay.key(80)),
                       ('key_down', lambda: replay.key_down(80)),
                       ('key_up', lambda: replay.key_up(80)),
                       ('press_key', lambda: replay.press_key(80))):
        with pytest.raises(ReplayInputRefused) as raised:
            call()
        assert kind in str(raised.value)
    assert replay.inputs == []
    assert len(replay.attempts) == 9


def test_an_expected_input_is_recorded_and_everything_else_is_refused():
    seen = []

    def expects(kind, position, *args):
        seen.append((kind, position, args))
        return kind == 'click' and position == 0

    replay = ReplayFrames(_frame(), expects=expects)
    assert replay.click(10, 20) is True
    assert replay.inputs == [('click', 10, 20)]
    assert seen == [('click', 0, (10, 20))]
    with pytest.raises(ReplayInputRefused):
        replay.swipe(1, 2, 3, 4, 600)
    assert replay.inputs == [('click', 10, 20)]


def test_the_screen_hands_out_a_copy_and_the_fixture_stays_clean():
    fixture = _frame(value=7)
    replay = ReplayFrames(fixture)
    shown = replay.screencap()
    shown[0, 0] = 0
    assert fixture[0, 0].tolist() == [7, 7, 7]
    assert replay.screencap().shape == fixture.shape


def test_a_replay_with_no_frame_says_so_instead_of_crashing():
    replay = ReplayFrames()
    with pytest.raises(ReplayInputRefused, match='no frame'):
        replay.screencap()


def test_the_mechanical_answers_are_the_layer_s():
    replay = ReplayFrames(_frame())
    assert replay.connect() is True
    assert replay.disconnect() is True
    assert replay.get_features() == 0
    assert replay.request_uuid() == OFFLINE_UUID
    assert ReplayFrames(_frame(), uuid='a-scenario').request_uuid() == 'a-scenario'


def test_the_attempt_log_keeps_the_name_the_map_tool_used():
    replay = ReplayFrames(_frame())
    with pytest.raises(ReplayInputRefused):
        replay.click(3, 4)
    assert replay.input_attempts is replay.attempts
    assert replay.input_attempts == [('click', 3, 4)]


# -- the population ----------------------------------------------------------


def test_no_replay_tool_re_implements_the_mechanical_surface():
    data = _inventory_module().report()
    assert data['problems'] == []
    assert data['owning_a_controller'] == 16


def test_every_owning_tool_inherits_the_shared_layer():
    data = _inventory_module().report()
    for row in data['rows']:
        for controller in row['controllers']:
            assert controller['shared'], (row['tool'], controller)


REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool_module(name):
    """Load a tool by filename, so its own scene expectation can be asked a question."""
    import sys

    for path in (REPO / 'tools', REPO / 'src'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(name, REPO / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_neighbour_imports_are_reported_and_only_shrink():
    """Five tools still take a controller from a tool that owns a real scene.

    It was 46 until D54 flattened the 32 that imported a body of "store this frame",
    then 12 until D55 gave the layer the two capabilities seven of them existed for
    (a screen that advances when the input is accepted, and a click log). What is
    left is one scene replay reused by another tool of the same scene -- deployment
    twice, battle, native, theme -- which is a dependency, not a duplicate. The
    number may fall but not grow, and the sources are named so a new one cannot
    arrive unnoticed.
    """
    data = _inventory_module().report()
    assert data['importing_a_controller_from_a_tool'] == 5
    sources = {edge[0] for edges in data['controller_imports'].values() for edge in edges}
    assert sources == {'verify_theme_replay', 'verify_deployment_replay',
                       'verify_native_replay', 'verify_battle_plan_replay'}, sources


def test_the_counter_example_a_neighbour_import_is_named(tmp_path):
    source = tmp_path / 'verify_source_replay.py'
    source.write_text('from maalimbus.replay import ReplayController\n'
                      'class Replay(ReplayController):\n    pass\n', encoding='utf-8')
    borrower = tmp_path / 'verify_borrower_replay.py'
    borrower.write_text('from verify_source_replay import Replay\n', encoding='utf-8')
    data = _inventory_module().report(tmp_path)
    assert data['importing_a_controller_from_a_tool'] == 1
    assert data['controller_imports']['verify_borrower_replay.py'] == [['verify_source_replay', 'Replay']]


def test_the_counter_example_a_tool_with_its_own_connect_is_reported(tmp_path):
    tool = tmp_path / 'verify_own_replay.py'
    tool.write_text(
        'from maa.controller import CustomController\n'
        'class Replay(CustomController):\n'
        '    def connect(self):\n'
        '        return True\n', encoding='utf-8')
    data = _inventory_module().report(tmp_path)
    assert data['problems']
    assert any('re-implements connect' in problem for problem in data['problems'])
    assert any('does not inherit' in problem for problem in data['problems'])


def test_the_counter_example_a_tool_that_skips_the_layer_is_reported(tmp_path):
    tool = tmp_path / 'verify_skips_replay.py'
    tool.write_text(
        'from maa.controller import CustomController\n'
        'class Replay(CustomController):\n'
        '    def click(self, x, y):\n'
        '        return True\n', encoding='utf-8')
    data = _inventory_module().report(tmp_path)
    assert [p for p in data['problems'] if 'does not inherit' in p]


def test_request_uuid_has_exactly_one_implementation_in_the_repository():
    owners = []
    for path in list((ROOT / 'tools').glob('*.py')) + list((ROOT / 'src' / 'maalimbus').glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.FunctionDef) and member.name == 'request_uuid':
                        owners.append('%s:%s' % (path.name, node.name))
    assert owners == ['replay.py:ReplayFrames'], owners


def test_the_inventory_tool_runs_clean(capsys):
    module = _inventory_module()
    assert module.main([]) == 0
    out = capsys.readouterr().out
    assert 'inheriting the shared layer: 16' in out
    assert 'problems: none' in out


def test_an_accepted_input_moves_the_screen_on_and_a_refused_one_does_not():
    """The frame swap seven tools wrote inside their own `click` is the layer's job.

    Before D55 each of them carried `if self.after is not None: self.frame = ...`,
    so the capability existed seven times and nowhere a stranger could find it.
    """
    import numpy as np

    frames = [np.zeros((4, 4, 3), np.uint8), np.full((4, 4, 3), 9, np.uint8)]
    yes = ReplayFrames(frames, expects=lambda kind, position, *args: True, advance=True)
    assert yes.screencap()[0, 0, 0] == 0
    yes.click(3, 3)
    assert yes.screencap()[0, 0, 0] == 9, 'an accepted input shows the next frame'
    yes.click(3, 3)
    assert yes.screencap()[0, 0, 0] == 9, 'the last frame stays the last frame'
    assert yes.clicks == [[3, 3], [3, 3]]

    no = ReplayFrames(frames, expects=lambda kind, position, *args: False, advance=True)
    with pytest.raises(ReplayInputRefused):
        no.click(3, 3)
    assert no.screencap()[0, 0, 0] == 0, 'a refused input never moves the screen'
    assert no.clicks == []


def test_a_scene_expectation_built_from_flags_still_refuses_the_other_box():
    """The migration kept each tool's own box, and the boxes still say no."""
    expects = _tool_module('verify_hard_toggle_replay').expects_toggle
    assert expects('click', 0, 1380, 70) is True
    assert expects('click', 0, 900, 500) is False
    assert expects('swipe', 0, 1, 2, 3, 4) is False
