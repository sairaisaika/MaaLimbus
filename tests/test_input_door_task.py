"""An input needs a task that owns the controller (D84).

Live `packaged-mirror-20261024-014706`: the entry task ended *successfully* on MAP at
05:49:20 (D83 working), and the click the loop sent at 05:49:27 was answered
`controller not found [controller_id=""]`; the Python side then blocked inside the native
call until the harness killed the wrapper.  D82 closed the door for a *torn down* task;
this file pins the door for the general case: no running task, no input.
"""
import json
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import pages, runner  # noqa: E402

BOX = [880, 520, 160, 48]


class _Journal:
    def __init__(self, directory):
        self.directory = pathlib.Path(directory)
        self.rows = []
        self.directory.mkdir(parents=True, exist_ok=True)

    def record(self, event, **details):
        row = dict(details, event=event)
        self.rows.append(row)
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row) + '\n')


class _Task:
    """A tasker stub that answers `running` the way the framework does."""

    def __init__(self, running):
        self.running = running
        self.id = 'controller-1'  # the id stays set even when the route is gone


def _runner(tmp_path, *, tasker=_Task(True), **settings):
    device = runner.FakeDevice()
    device.tasker = tasker
    return runner.MirrorRunner(
        device, settings={'rounds': 1, 'interval': 0, 'steps': 1, **settings},
        directory=tmp_path, journal=_Journal(tmp_path))


def _plan(**over):
    # A page that sends one click and carries no map bookkeeping: the door is what is
    # under test, not the map's candidate list.
    plan = {'page': 'HOME', 'action': 'click', 'target': list(BOX), 'node': None,
            'expect': ('DRIVE', 'HOME', 'UNKNOWN'), 'advance': False,
            'reason': 'drive_nav_is_the_proven_way_back_to_the_mirror_menu'}
    plan.update(over)
    return plan


def _run(loop, monkeypatch, *, scene='HOME'):
    plan = _plan()
    monkeypatch.setattr(runner, 'plan_step', lambda *a, **k: dict(plan))
    monkeypatch.setattr(runner, 'observe', lambda observer, deadline=None: {
        'scene': scene, 'image_sha256': 'same', 'size': [1920, 1080], 'ocr': []})
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    return loop.run(steps=1, interval=0, round_limit=1)


def test_input_is_withheld_when_no_task_is_running(tmp_path, monkeypatch):
    loop = _runner(tmp_path, tasker=_Task(False))
    result = _run(loop, monkeypatch)
    assert loop.device.clicks == [], 'an input went out with no task owning the controller'
    rows = [r for r in loop.journal.rows if r['event'] == 'input_withheld']
    assert len(rows) == 1, rows
    assert rows[0]['detail'] == runner.INPUT_NEEDS_A_TASK
    assert result['passed'] is False
    assert loop.state['session_ended'] == runner.INPUT_NEEDS_A_TASK


def test_input_is_sent_while_a_task_is_running(tmp_path, monkeypatch):
    loop = _runner(tmp_path, tasker=_Task(True))
    _run(loop, monkeypatch)
    assert loop.device.clicks, 'the door closed a working input'
    assert not [r for r in loop.journal.rows if r['event'] == 'input_withheld']


def test_a_loop_without_a_tasker_still_sends_input(tmp_path, monkeypatch):
    loop = _runner(tmp_path, tasker=None)
    _run(loop, monkeypatch)
    assert loop.device.clicks, 'a loop with no tasker has nothing to ask'


def test_the_door_reads_the_framework_not_the_controller_id(tmp_path, monkeypatch):
    tasker = _Task(False)
    assert tasker.id == 'controller-1', 'the live stub reported a non-empty id'
    loop = _runner(tmp_path, tasker=tasker)
    _run(loop, monkeypatch)
    assert loop.device.clicks == []
    assert loop.state['session_ended'] == runner.INPUT_NEEDS_A_TASK


def test_the_withheld_reason_is_a_stop_kind():
    assert pages.kind_of(stopped_reason=runner.INPUT_NEEDS_A_TASK) == 'refused_by_policy'


def test_a_non_input_plan_is_never_withheld(tmp_path, monkeypatch):
    loop = _runner(tmp_path, tasker=_Task(False))
    monkeypatch.setattr(runner, 'plan_step', lambda *a, **k: {
        'page': 'HOME', 'action': 'record', 'target': None, 'node': None,
        'expect': (), 'reason': 'the_page_is_read_and_nothing_is_sent', 'advance': False})
    monkeypatch.setattr(runner, 'observe', lambda observer, deadline=None: {
        'scene': 'HOME', 'image_sha256': 'same', 'size': [1920, 1080], 'ocr': []})
    loop.run(steps=1, interval=0, round_limit=1)
    assert not [r for r in loop.journal.rows if r['event'] == 'input_withheld']
    assert loop.device.clicks == []
