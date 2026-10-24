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

D60 adds the second bound the settle loop was missing: the *page* budget counts rounds
that produced a frame and did not change it, while consecutive reads that never came back
have their own small budget (``settings.unreadable_rounds``), because a device that failed
once usually fails again and thirty patient rounds at the read window is nine hundred
seconds of a four hundred second budget.  The note also carries how long the read took, so
what wedged is retrievable afterwards.
"""
import json
from pathlib import Path

import pytest

import maalimbus.runner as runner
from maalimbus.runner import FakeDevice, MirrorRunner

PAGE = 'DRIVE'
PLAN = {'page': PAGE, 'action': 'click', 'target': [880, 520, 160, 48], 'node': None,
        'expect': ('MAP',), 'reason': 'a_word_with_a_successor', 'advance': False}
# The D60 cases end a step on an unreadable page on purpose, so their plan names it.
UNKNOWN_PLAN = dict(PLAN, expect=('MAP', 'UNKNOWN'), reason='a_word_that_may_stay_unreadable')


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


def _run(tmp_path, reads, monkeypatch, *, read_retries=None, steps=1, plan=None,
         unreadable_rounds=None, rounds=1):
    plan = dict(PLAN if plan is None else plan)
    monkeypatch.setattr(runner, 'plan_step', lambda *args, **kwargs: dict(plan))
    monkeypatch.setattr(runner, 'observe', reads)
    settings = {'rounds': rounds, 'interval': 0, 'steps': steps,
                'stall_seconds': 0, 'progress_seconds': 0}
    if read_retries is not None:
        settings['read_retries'] = read_retries
    if unreadable_rounds is not None:
        settings['unreadable_rounds'] = unreadable_rounds
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


# --------------------------------------------------------------------- D60: the read budget


def _notes(rows):
    return [row for row in rows if row['event'] == 'settle_read_never_returned']


def test_consecutive_unreadable_rounds_stop_at_their_own_budget(tmp_path, monkeypatch):
    # A device that failed once usually fails again: three settle reads in a row fail,
    # the budget is two, so the step stops asking after the third instead of spending the
    # remaining page rounds on the same dead call.
    reads = _Reads(_frame(PAGE), fail_at=(2, 3, 4, 5, 6, 7))
    loop, _, rows = _run(tmp_path, reads, monkeypatch, plan=UNKNOWN_PLAN,
                         unreadable_rounds=2, rounds=6)
    notes = _notes(rows)
    assert [note['consecutive'] for note in notes] == [1, 2, 3], notes
    assert [note['reads_failed'] for note in notes] == [1, 2, 3], notes
    assert reads.calls == 4, reads.calls          # one step read, three settle reads
    steps = loop.artifacts['steps']
    assert steps[-1]['page_after'] == 'UNKNOWN'
    assert steps[-1]['reads_failed'] == 3
    assert not [row for row in rows if row['event'] == 'mirror_session_ended']


def test_a_round_that_read_something_clears_the_read_budget(tmp_path, monkeypatch):
    # Consecutive, not lifetime: call 2 fails, call 3 reads an unchanged frame, call 4 fails
    # again -- with a budget of one neither failure may exhaust the loop, so call 5 must
    # still reach MAP.  A lifetime counter would have ended the step on the second failure.
    frames = [_frame(PAGE), _frame(PAGE), _frame(PAGE), _frame(PAGE),
              _frame('MAP', 'later')]
    reads = _Reads(*frames, fail_at=(2, 4))
    loop, _, rows = _run(tmp_path, reads, monkeypatch, plan=UNKNOWN_PLAN,
                         unreadable_rounds=1, rounds=6)
    assert len(_notes(rows)) == 2
    assert loop.artifacts['steps'][0]['page_after'] == 'MAP', loop.artifacts['steps'][:1]
    # Two reads were lost in this step, but never twice in a row, so the budget held.
    assert loop.artifacts['steps'][0]['reads_failed'] == 2


def test_the_note_says_how_long_the_read_took(tmp_path, monkeypatch):
    reads = _Reads(_frame(PAGE), fail_at=(2,))
    _, _, rows = _run(tmp_path, reads, monkeypatch, plan=UNKNOWN_PLAN, rounds=3)
    note = _notes(rows)[0]
    assert note['seconds'] is not None and note['seconds'] >= 0
    assert note['limit_seconds'] == runner.ONE_READ_SECONDS
    assert note['budget'] == runner.settings().unreadable_rounds


def test_a_zero_read_budget_stops_asking_immediately(tmp_path, monkeypatch):
    reads = _Reads(_frame(PAGE), _frame(PAGE), _frame(PAGE), fail_at=(2, 3, 4))
    loop, _, rows = _run(tmp_path, reads, monkeypatch, plan=UNKNOWN_PLAN,
                         unreadable_rounds=0, rounds=6)
    assert len(_notes(rows)) == 1
    assert loop.artifacts['steps'][0]['reads_failed'] == 1
    assert loop.artifacts['steps'][0]['page_after'] == 'UNKNOWN'
    assert not [row for row in rows if row['event'] == 'mirror_session_ended']


def test_the_page_budget_still_governs_rounds_that_did_read(tmp_path, monkeypatch):
    # The two bounds are separate: the map arrives on the fourth settle round, so a read
    # budget that shortened successful rounds would have ended this step on UNKNOWN.
    frames = [_frame(PAGE)] + [_frame(PAGE)] * 3 + [_frame('MAP', 'later')] * 4
    reads = _Reads(*frames)
    loop, _, rows = _run(tmp_path, reads, monkeypatch, plan=UNKNOWN_PLAN, rounds=4)
    assert _notes(rows) == []
    assert loop.artifacts['steps'][0]['page_after'] == 'MAP', loop.artifacts['steps'][:1]
    assert loop.artifacts['steps'][0]['reads_failed'] == 0


def test_the_read_budget_is_a_setting_with_a_small_default():
    assert runner.settings().unreadable_rounds == 2


def test_a_negative_read_budget_is_refused():
    with pytest.raises(ValueError):
        MirrorRunner(FakeDevice(), settings={'unreadable_rounds': -1})
    assert runner.settings({'unreadable_rounds': 30}).unreadable_rounds == 30
