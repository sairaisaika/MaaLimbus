"""The payout is the reason a run exists, and it has to reach the journal.

Every other task action in `agent/recognition.py` ends with `main_task_stopped`, but the
reward branch returns before that line -- so the one outcome the whole loop exists for was
the one outcome the journal never held, and `clear_rate` could only ever measure the
exploration half.  These cases pin both halves: the decision is written by `reward_task`,
and `run_metrics` reads it back as a figure that says "not measured" when no run has one.
"""
from types import SimpleNamespace

import pytest

from maalimbus import run_metrics
from maalimbus.reward_task import execute
from maalimbus.storage import read_json, write_json


class Journal:
    def __init__(self):
        self.rows = []

    def record(self, event, **fields):
        self.rows.append(dict(fields, event=event))

    def named(self, event):
        return [row for row in self.rows if row['event'] == event]


class Observer:
    def __init__(self, record, directory=None):
        self.record = record
        self.calls = 0
        self.directory = directory

    def observe(self, **kwargs):
        self.calls += 1
        return self.record


def _device():
    return SimpleNamespace(click=lambda *args: True)


def test_a_run_with_no_completed_scope_writes_that_it_skipped():
    journal = Journal()
    config = write_config({})
    result = execute(config, config, Observer({}), _device(), journal)
    assert result['reason'] == 'completed_mirror_run_required'
    skipped = journal.named('reward_task_skipped')
    assert len(skipped) == 1
    assert skipped[0]['reason'] == 'completed_mirror_run_required'
    assert skipped[0]['inputs_sent'] is False


def test_a_reward_page_that_was_not_proven_ends_in_a_named_stop():
    journal = Journal()
    config = write_config({'active': {'id': 'run-1', 'floors': [1, 2, 3, 4, 5],
                                      'victory': True}})
    record = {'scene': 'UNKNOWN', 'size': [1920, 1080], 'ocr': [],
              'image_sha256': 'sha'}
    result = execute(config, config, Observer(record, config), _device(), journal)
    assert not result['passed']
    stopped = journal.named('reward_task_stopped')
    assert len(stopped) == 1
    assert stopped[0]['passed'] is False
    assert stopped[0]['reward_received'] is False
    assert 'not proven' in stopped[0]['error']


def test_a_verified_payout_is_written_as_claimed(monkeypatch, tmp_path):
    import maalimbus.reward_task as task
    journal = Journal()
    config = write_config({'active': {'id': 'run-1', 'floors': [1, 2, 3, 4, 5],
                                      'victory': True}})
    frame = config / 'frame-0001.json'
    write_json(frame, {'scene': 'HOME', 'size': [1920, 1080], 'ocr': []})
    monkeypatch.setattr(task.runner, 'frame_file', lambda directory: frame)
    monkeypatch.setattr(task, 'finish',
                        lambda c, scope, home: {'passed': True,
                                                'reason': 'mirror_payout_and_home_verified'})
    result = execute(config, config,
                     Observer({'scene': 'HOME', 'size': [1920, 1080], 'ocr': [],
                               'image_sha256': 'sha'}, config), _device(), journal)
    assert result['passed']
    executed = journal.named('reward_task_executed')
    assert len(executed) == 1
    assert executed[0]['passed'] is True
    assert executed[0]['reward_received'] is True
    assert executed[0]['scope'] == 'run-1'
    assert executed[0]['reason'] == 'mirror_payout_and_home_verified'


def test_a_caller_with_no_journal_still_runs():
    # Several callers (and the offline audits) pass a stand-in or nothing at all; the
    # note is optional rather than a new requirement on them.
    config = write_config({})
    result = execute(config, config, Observer({}), _device(), SimpleNamespace())
    assert result['reason'] == 'completed_mirror_run_required'
    result = execute(config, config, Observer({}), _device(), None)
    assert result['reason'] == 'completed_mirror_run_required'


def test_the_journal_carries_one_payout_event_per_run():
    rows = [{'event': 'loop_heartbeat'},
            {'event': 'reward_task_executed', 'scope': 'run-1', 'passed': True,
             'reward_received': True, 'reason': 'mirror_payout_and_home_verified'}]
    found = run_metrics.efficiency(rows)['payout']
    assert found == {'claimed': True, 'events': 1,
                     'reason': 'mirror_payout_and_home_verified'}


def test_a_stopped_payout_is_not_a_claim():
    rows = [{'event': 'reward_task_stopped', 'passed': False,
             'error': 'Reward page or successor not proven'}]
    found = run_metrics.efficiency(rows)['payout']
    assert found['claimed'] is False
    assert 'not proven' in found['reason']


def test_a_run_that_never_reached_rewards_has_no_payout():
    assert run_metrics.efficiency([{'event': 'loop_heartbeat'}])['payout'] is None


def test_the_payout_rate_is_a_rate_over_the_runs_that_recorded_one():
    runs = [{'explored': True, 'payout': {'claimed': True, 'events': 1, 'reason': 'x'},
             'seconds': None, 'steps': 1, 'reads': 1, 'recoveries': 0, 'advanced': 0,
             'unconfirmed_purchases': None,
             'ending': {'kind': 'stop', 'path': 'agent_loop', 'reason': 'x'}},
            {'explored': False, 'payout': {'claimed': False, 'events': 1, 'reason': 'y'},
             'seconds': None, 'steps': 1, 'reads': 1, 'recoveries': 0, 'advanced': 0,
             'unconfirmed_purchases': None,
             'ending': {'kind': 'stop', 'path': 'agent_loop', 'reason': 'y'}},
            {'explored': False, 'payout': None, 'seconds': None, 'steps': 1, 'reads': 1,
             'recoveries': 0, 'advanced': 0, 'unconfirmed_purchases': None,
             'ending': {'kind': 'died', 'path': 'process_died', 'reason': None}}]
    figures = run_metrics.metrics(runs)
    assert figures['payout_rate']['value'] == 0.5
    assert figures['payout_rate']['basis'] == '1 of 2 runs that recorded a payout outcome claimed it'
    assert figures['payout_rate']['note'] is None


def test_a_corpus_with_no_payout_says_it_was_not_measured():
    runs = [{'explored': False, 'payout': None, 'seconds': None, 'steps': 1, 'reads': 1,
             'recoveries': 0, 'advanced': 0, 'unconfirmed_purchases': None,
             'ending': {'kind': 'died', 'path': 'process_died', 'reason': None}}]
    figures = run_metrics.metrics(runs)
    assert figures['payout_rate']['value'] is None
    assert figures['payout_rate']['basis'] == '0 of 0 runs that recorded a payout outcome claimed it'
    assert 'not measured' in figures['payout_rate']['note'] or \
           'no payout was measured' in figures['payout_rate']['note']


def test_the_figure_has_one_owner_and_a_name_in_the_measure_list():
    assert 'payout_rate' in run_metrics.MEASURES
    assert run_metrics.PAYOUT_EVENTS == ('reward_task_executed', 'reward_task_stopped',
                                         'reward_task_skipped')


def write_config(ledger):
    import tempfile
    directory = _scratch()
    write_json(directory / 'user-run-ledger.json', ledger)
    return directory


_SCRATCH = {}


def _scratch():
    import pathlib
    import tempfile
    if 'root' not in _SCRATCH:
        _SCRATCH['root'] = pathlib.Path(tempfile.mkdtemp(prefix='maalimbus-payout-'))
        _SCRATCH['count'] = 0
    _SCRATCH['count'] += 1
    directory = _SCRATCH['root'] / ('case-%d' % _SCRATCH['count'])
    directory.mkdir(parents=True, exist_ok=True)
    return directory
