"""A read that does not come back is a failed observation, not a verdict (D59).

``dea7028`` and ``92be12e`` bounded every native read, so a wedged screenshot can no
longer spend the whole budget -- but the *bound* then became the ending: the error
unwound the step and the loop ended the run, which forfeits a 420 s window on one 30 s
hiccup.  The settle loop is where that hurt most, because the input is already out: 16 of
51 silent retained runs ended on ``window_no_progress`` with their last event a settle
read.

The contract these tests pin:

* a read that fails inside the settle loop is one unproductive round (the page is
  unreadable for that round, and the settle budget and run deadline still bound it);
* a read that fails at the top of a step is retried ``settings.read_retries`` times and
  then ends the run with the read's own reason -- bounded, never a retry loop;
* a *plain* ``RuntimeError`` is still somebody else's ending and is not retried.
"""
import json
from pathlib import Path

import pytest

import maalimbus.runner as runner
from maalimbus.runner import FakeDevice, MirrorRunner

PAGE = 'DRIVE'
PLAN = {'page': PAGE, 'action': 'click', 'target': [880, 520, 160, 48], 'node': None,
        'expect': ('MAP',), 'reason': 'a_word_with_a_successor', 'advance': False}


class _Journal:
    def __init__(self, directory):
        self.path = Path(directory) / 'events.jsonl'

    def record(self, event, **details):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(event=event, **details), ensure_ascii=False) + '\n')


def _events(directory, name=None):
    path = Path(directory) / 'events.jsonl'
    rows = ([json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
            if path.exists() else [])
    return [row for row in rows if name is None or row['event'] == name]


def _frame(scene, sha='same'):
    return {'scene': scene, 'image_sha256': sha, 'size': [1920, 1080], 'ocr': []}


class _Reads:
    """An observer whose reads succeed, fail at chosen call numbers, or always fail."""

    def __init__(self, *frames, fail_at=(), always=False):
        self.frames = list(frames) or [_frame(PAGE)]
        self.fail_at = set(fail_at)
        self.always = always
        self.calls = 0

    def __call__(self, observer, deadline=None):
        self.calls += 1
        if self.always or self.calls in self.fail_at:
            raise runner.ReadNeverReturned('the observation node recorded no page for this frame')
        return dict(self.frames[min(self.calls - 1, len(self.frames) - 1)])


def _run(tmp_path, reads, monkeypatch, *, read_retries=None, steps=1, plan=None):
    plan = dict(PLAN if plan is None else plan)
    monkeypatch.setattr(runner, 'plan_step', lambda *args, **kwargs: dict(plan))
    monkeypatch.setattr(runner, 'observe', reads)
    settings = {'rounds': 1, 'interval': 0, 'steps': steps,
                'stall_seconds': 0, 'progress_seconds': 0}
    if read_retries is not None:
        settings['read_retries'] = read_retries
    loop = MirrorRunner(FakeDevice(), settings=settings,
                        directory=tmp_path, journal=_Journal(tmp_path))
    result = loop.run(steps=steps, interval=0, round_limit=max(1, steps))
    return loop, result, _events(tmp_path)


def test_a_settle_read_that_never_came_back_is_one_unproductive_round(tmp_path, monkeypatch):
    # Call 1 is the step's own read, call 2 is the first settle read (the one that wedged
    # in the retained runs), call 3 is the second settle round.
    reads = _Reads(_frame(PAGE), None, _frame('MAP', 'later'), fail_at=(2,))
    _, result, rows = _run(tmp_path, reads, monkeypatch)
    notes = [row for row in rows if row['event'] == 'settle_read_never_returned']
    assert len(notes) == 1, [row['event'] for row in rows]
    assert notes[0]['page'] == PAGE
    assert notes[0]['round'] == 1
    assert notes[0]['reason'] == runner.ReadNeverReturned.reason
    # The run was not ended by it, and the step did see its successor on the next round.
    assert not [row for row in rows if row['event'] == 'mirror_session_ended']
    assert loop_ended_without_a_failure(rows)
    assert reads.calls == 3


def loop_ended_without_a_failure(rows):
    return not [row for row in rows if row['event'] == 'loop_read_failed']


def test_the_step_that_survived_a_failed_settle_read_still_records_its_successor(tmp_path, monkeypatch):
    reads = _Reads(_frame(PAGE), None, _frame('MAP', 'later'), fail_at=(2,))
    loop, _, _ = _run(tmp_path, reads, monkeypatch)
    steps = loop.artifacts['steps']
    assert steps and steps[-1]['page_after'] == 'MAP', steps


def test_a_read_that_fails_at_the_top_of_the_step_is_retried(tmp_path, monkeypatch):
    reads = _Reads(_frame(PAGE), fail_at=(1, 2))
    _, _, rows = _run(tmp_path, reads, monkeypatch)
    failures = [row for row in rows if row['event'] == 'loop_read_failed']
    assert [row['failures'] for row in failures] == [1, 2]
    assert all(row['retries'] == 2 for row in failures)
    assert not [row for row in rows if row['event'] == 'mirror_session_ended']
    assert len([row for row in rows if row['event'] == 'loop_heartbeat']) >= 3


def test_after_its_retries_a_failed_read_names_the_ending(tmp_path, monkeypatch):
    reads = _Reads(always=True)
    loop, result, rows = _run(tmp_path, reads, monkeypatch)
    failures = [row for row in rows if row['event'] == 'loop_read_failed']
    assert [row['failures'] for row in failures] == [1, 2, 3]
    assert loop.state['session_ended'] == runner.ReadNeverReturned.reason
    assert result['passed'] is False


def test_a_zero_retry_budget_ends_the_run_on_the_first_failure(tmp_path, monkeypatch):
    reads = _Reads(always=True)
    loop, _, rows = _run(tmp_path, reads, monkeypatch, read_retries=0)
    failures = [row for row in rows if row['event'] == 'loop_read_failed']
    assert len(failures) == 1 and failures[0]['failures'] == 1 and failures[0]['retries'] == 0
    assert loop.state['session_ended'] == runner.ReadNeverReturned.reason


def test_a_plain_runtime_error_is_still_fatal_and_not_retried(tmp_path, monkeypatch):
    calls = {'n': 0}

    def broken(observer, deadline=None):
        calls['n'] += 1
        raise RuntimeError('a pipeline node failed for its own reason')

    _, _, rows = _run(tmp_path, broken, monkeypatch)
    assert calls['n'] == 1
    assert not [row for row in rows if row['event'] == 'loop_read_failed']
    ended = [row for row in rows if row['event'] == 'mirror_session_ended']
    assert ended and ended[0]['reason'] == 'the_task_raised_before_the_next_input', ended


def test_a_successful_step_clears_the_failure_count(tmp_path, monkeypatch):
    # The count is consecutive failures, not a lifetime total: otherwise two hiccups early
    # in a run would leave the retry budget spent for every step after them.
    reads = _Reads(_frame(PAGE), _frame('MAP', 'later'))
    loop, _, _ = _run(tmp_path, reads, monkeypatch)
    assert loop.state['read_failures'] == 0
    assert not [row for row in _events(tmp_path) if row['event'] == 'loop_read_failed']


def test_an_unreadable_frame_is_the_unknown_page():
    loop = MirrorRunner.__new__(MirrorRunner)
    loop.state = {'page': PAGE, 'read_failures': 0}
    frame = loop._unreadable_frame('abc')
    assert frame['scene'] == 'UNKNOWN'
    assert frame['image_sha256'] == 'abc'      # unchanged, so the pixel rule sees no change
    assert frame['unreadable'] is True
    assert frame['reason'] == runner.ReadNeverReturned.reason


def test_the_retry_budget_is_a_setting_with_a_small_default():
    assert runner.settings().read_retries == 2
