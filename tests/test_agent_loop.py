"""The `limbus_mirror_loop` action: what it reads, where it writes, what it reports.

The action drives `maalimbus.runner` from inside a Maa task, so these tests hand it the
same things the PI hands it -- a controller that only posts jobs, and a context whose
`run_task` is the pipeline -- and then read the run directory it leaves behind. The
pipeline is replayed from archived pages, so no device, no game, and no ADB is involved.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent'))

import recognition
from recognition import (AgentTasker, Journal, LimbusRecognition, MirrorLoopAction,
                         loop_budget, loop_directory, loop_parameters, loop_store)
from maalimbus import runner

#: A real archived page: the run summary that only needs its claim clicked, and the page
#: the run reads back afterwards to see what that click did.
CLAIM_FRAME = ROOT / 'evidence/runtime/window-20261007-021150/frame-0001.json'
CLAIM_SUCCESSOR = ROOT / 'evidence/runtime/window-20261007-021150/frame-0002.json'
#: A real archived battle page, which sends the observer on to the battle pipeline too.
BATTLE_FRAME = ROOT / 'evidence/runtime/battle-auto-assign-20261006-011029/frame-0001.json'


class FakeJob:
    """A Maa job that has already finished, the way a post is finished when it returns."""

    def __init__(self, done=True, succeeded=True):
        self.done = done
        self.succeeded = succeeded


class FakeController:
    """Only what the loop reaches for: input, the screenshot size, the screenshot target."""

    def __init__(self):
        self.clicks = []
        self.swipes = []
        self.long_side = None
        self.cached_image = None

    def set_screenshot_target_long_side(self, value):
        self.long_side = value

    def post_screencap(self):
        return FakeJob()

    def post_click(self, x, y):
        self.clicks.append((x, y))
        return FakeJob()

    def post_swipe(self, *args):
        self.swipes.append(args)
        return FakeJob()


class BrokenController(FakeController):
    """A controller that is gone by the time the run starts."""

    def set_screenshot_target_long_side(self, value):
        raise RuntimeError('the controller is gone')


class HangingController(FakeController):
    """A controller whose input job never finishes, so only the deadline can end the run."""

    def post_click(self, x, y):
        self.clicks.append((x, y))
        return FakeJob(done=False, succeeded=False)


class FakeContext:
    """The context a mirror loop needs: a controller, and `run_task` as the pipeline.

    The real observation nodes read the screen and journal one record; this replays an
    archived page through the same `events.jsonl` and frame files the runner reads, so a
    whole run can be driven offline from recorded evidence.
    """

    def __init__(self, directory, *, controller=None, frames=()):
        self.tasker = SimpleNamespace(controller=controller or FakeController())
        self.directory = Path(directory)
        self.frames = [Path(frame) for frame in frames]
        self.opened = []
        self.entries = []

    def run_task(self, entry, pipeline_override=None):
        self.entries.append(entry)
        observed = {'WindowMapObserve': 'map_observed',
                    'WindowBattleObserve': 'battle_observed'}
        if entry in observed:
            Journal(self.directory).record(observed[entry], **self.page())
        return SimpleNamespace(status=SimpleNamespace(succeeded=True))

    def page(self):
        """Copy the next archived page into the run directory as its newest frame."""
        source = self.frames[len(self.opened)]
        self.opened.append(source)
        name = 'frame-%04d' % len(self.opened)
        for suffix in ('.json', '.png'):
            (self.directory / (name + suffix)).write_bytes(
                source.with_suffix(suffix).read_bytes())
        record = json.loads(source.read_text(encoding='utf-8'))
        return dict(record, frame=name, input_sent=False)


@pytest.fixture(autouse=True)
def clean_loop_environment(monkeypatch):
    """The loop is aimed through the environment; a stray setting must not reach a test."""
    for name in runner.settings().as_dict():
        monkeypatch.delenv('MAALIMBUS_LOOP_' + name.upper(), raising=False)
    monkeypatch.delenv('MAALIMBUS_LOOP_BUDGET', raising=False)
    monkeypatch.delenv('MAALIMBUS_RUN_DIR', raising=False)


def run_loop(tmp_path, params, *, frames=(CLAIM_FRAME, CLAIM_SUCCESSOR), controller=None):
    """Run one action over archived pages and hand back everything it left behind."""
    directory = tmp_path / 'run'
    # The node always aims the run at a directory; a test that left it out would let the
    # action write a stamp into the repository's own evidence tree.
    params = dict({'directory': str(directory)}, **params)
    context = FakeContext(directory, controller=controller or FakeController(), frames=frames)
    reader = LimbusRecognition('en', Journal(directory))
    action = MirrorLoopAction(reader)
    argv = SimpleNamespace(custom_action_param=json.dumps(params), node_name='MirrorLoop')
    returned = action.run(context, argv)
    return SimpleNamespace(context=context, directory=directory, recognition=reader,
                           action=action, returned=returned)


def read_result(directory):
    return json.loads((Path(directory) / 'agent-result.json').read_text(encoding='utf-8'))


def test_the_node_defaults_to_a_whole_run():
    settings, ignored = loop_parameters({})
    assert settings.steps == 400
    assert settings.run_store == 'config/user-run-ledger.json'
    assert settings.observe_only is False
    assert ignored == []


def test_a_node_parameter_wins_and_a_stranger_is_reported():
    settings, ignored = loop_parameters({'steps': 12, 'team': 2, 'typo': 1})
    assert (settings.steps, settings.team) == (12, 2)
    assert ignored == ['typo']


def test_the_environment_aims_a_run_without_editing_the_pipeline(monkeypatch):
    monkeypatch.setenv('MAALIMBUS_LOOP_STEPS', '7')
    monkeypatch.setenv('MAALIMBUS_LOOP_OBSERVE_ONLY', 'yes')
    monkeypatch.setenv('MAALIMBUS_LOOP_INTERVAL', '0.5')
    settings, _ = loop_parameters({})
    assert (settings.steps, settings.observe_only, settings.interval) == (7, True, 0.5)


def test_a_node_parameter_beats_the_environment(monkeypatch):
    monkeypatch.setenv('MAALIMBUS_LOOP_STEPS', '7')
    settings, _ = loop_parameters({'steps': 9})
    assert settings.steps == 9


def test_the_directory_follows_the_node_then_the_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(recognition, 'ROOT', tmp_path)
    chosen = loop_directory({'directory': str(tmp_path / 'node')})
    assert chosen == tmp_path / 'node' and chosen.is_dir()
    monkeypatch.setenv('MAALIMBUS_RUN_DIR', 'evidence/runtime/marked')
    assert loop_directory({}) == tmp_path / 'evidence' / 'runtime' / 'marked'
    monkeypatch.delenv('MAALIMBUS_RUN_DIR')
    stamped = loop_directory({})
    assert stamped.parent == tmp_path / 'evidence' / 'runtime'
    assert stamped.name.startswith('pi-') and stamped.is_dir()


def test_the_budget_is_bounded(monkeypatch):
    assert loop_budget({}) == 5400.0
    assert loop_budget({'budget': 0}) == 1.0
    assert loop_budget({'budget': 3}) == 3.0
    monkeypatch.setenv('MAALIMBUS_LOOP_BUDGET', '12')
    assert loop_budget({}) == 12.0


def test_a_ledger_written_for_another_rotation_is_skipped_not_overwritten(tmp_path):
    ledger = tmp_path / 'ledger.json'
    written = {'version': 1, 'team_slots': [3, 5], 'rotation': 9,
               'completed_runs': 2, 'active': None, 'receipts': []}
    ledger.write_text(json.dumps(written), encoding='utf-8')
    settings, _ = loop_parameters({'run_store': str(ledger)})
    assert (loop_store(settings, Journal(tmp_path))) == (None, None)
    skipped, = runner.events(tmp_path, 'mirror_loop_store_skipped')
    assert 'rotation' in skipped['error']
    assert json.loads(ledger.read_text(encoding='utf-8')) == written


def test_a_ledger_decides_which_team_enters(tmp_path):
    ledger = tmp_path / 'ledger.json'
    ledger.write_text(json.dumps({'version': 1, 'team_slots': [3, 5], 'rotation': 1,
                                  'completed_runs': 0, 'active': None, 'receipts': []}),
                      encoding='utf-8')
    settings, _ = loop_parameters({'run_store': str(ledger), 'team': 5})
    store, run_id = loop_store(settings, Journal(tmp_path))
    assert store is not None and run_id
    assert settings.team == 5 and store.team_slot == 5


def test_the_observation_proxy_runs_nodes_here_and_has_nothing_to_stop(tmp_path):
    context = FakeContext(tmp_path, frames=(CLAIM_FRAME,))
    tasker = AgentTasker(context)
    assert tasker.tasker is tasker
    job = tasker.post_task('WindowMapObserve')
    assert (job.done, job.succeeded) == (True, True)
    assert tasker.post_stop().done is True
    assert context.entries == ['WindowMapObserve']


def test_the_loop_drives_a_run_and_reports_it(tmp_path):
    controller = FakeController()
    ran = run_loop(tmp_path, {'steps': 1, 'interval': 0.0,
                              'run_store': str(tmp_path / 'ledger.json')},
                   controller=controller)
    assert ran.returned is True
    assert ran.recognition.callback_failure is None
    result = read_result(ran.directory)
    assert result['reason'] == 'window_steps_passed'
    assert result['passed'] is True
    assert result['controller'] == 'Maa AgentServer'
    assert (result['clicks_sent'], len(result['steps'])) == (1, 1)
    assert result['run_ledger']['team'] == 5
    # One step reads the page, clicks its claim, then reads the page again.
    assert ran.context.entries == ['WindowMapObserve', 'WindowMapObserve']
    assert controller.long_side == 1920
    assert len(controller.clicks) == 1
    start, = runner.events(ran.directory, 'mirror_loop_start')
    assert start['directory'] == str(ran.directory)
    assert start['steps'] == 1
    stopped, = runner.events(ran.directory, 'mirror_loop_stopped')
    assert stopped['reason'] == 'window_steps_passed'
    assert (stopped['steps'], stopped['clicks_sent'], stopped['passed']) == (1, 1, True)


def test_a_battle_page_also_runs_the_battle_pipeline(tmp_path):
    ran = run_loop(tmp_path, {'steps': 1, 'interval': 0.0, 'run_store': ''},
                   frames=(BATTLE_FRAME, BATTLE_FRAME))
    assert ran.returned is True
    assert ran.context.entries == ['WindowMapObserve', 'WindowBattleObserve']
    assert runner.events(ran.directory, 'battle_observed')
    assert runner.events(ran.directory, 'mirror_loop_stopped')


def test_a_broken_controller_is_journalled_and_returns_false(tmp_path):
    ran = run_loop(tmp_path, {'steps': 1, 'interval': 0.0, 'run_store': ''},
                   controller=BrokenController())
    assert ran.returned is False
    assert ran.recognition.callback_failure is None
    error, = runner.events(ran.directory, 'mirror_loop_error')
    assert error['error_type'] == 'RuntimeError'
    assert 'RuntimeError' in error['traceback']
    assert runner.events(ran.directory, 'mirror_loop_stopped') == []
    result = read_result(ran.directory)
    assert (result['reason'], result['error_type']) == ('mirror_loop_failed', 'RuntimeError')


def test_a_run_out_of_budget_stops_bounded(tmp_path):
    ran = run_loop(tmp_path, {'steps': 1, 'interval': 0.0, 'budget': 0.5, 'run_store': ''},
                   controller=HangingController())
    assert ran.returned is True
    stopped, = runner.events(ran.directory, 'mirror_loop_stopped')
    assert stopped['reason'] == 'loop_deadline_exceeded'
    assert read_result(ran.directory)['reason'] == 'loop_deadline_exceeded'
