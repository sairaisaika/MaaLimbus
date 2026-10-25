"""A transition is a duration with a short poll, not a page wait (D110).

Measured over the retained corpus: 190 transitions after a submitted turn have median
27 s and p90 54 s, while a read costs about 1.2 s.  `window_transition_wait` used to sleep
the *page* interval (4 s) between reads and bound itself by a count of rounds, so the
window was spent asleep: live `evidence/runtime/packaged-mirror-20261024-085751` put
100.0 s of its 248.6 s into 23 transition waits (mean 4.35 s) and reached no floor.
"""
import itertools
import json

import pytest

from maalimbus import runner

TRANSITION_PLAN = {'page': 'UNKNOWN', 'action': 'wait', 'target': None, 'node': None,
                   'expect': (), 'reason': 'the_page_could_not_be_named', 'advance': False}


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


class _Observer:
    """A frame that changes every read but never names a page: a transition."""

    def __init__(self):
        self.calls = 0

    def record(self):
        self.calls += 1
        return {'scene': 'UNKNOWN', 'image_sha256': 'frame-%d' % self.calls,
                'size': [1920, 1080], 'ocr': []}


def _run(tmp_path, monkeypatch, **settings):
    loop = runner.MirrorRunner(runner.FakeDevice(), settings={'rounds': 1, 'interval': 4, **settings},
                               directory=tmp_path, journal=_Journal(tmp_path))
    loop.observer = _Observer()
    monkeypatch.setattr(runner, 'plan_step', lambda page, **kw: dict(TRANSITION_PLAN))
    monkeypatch.setattr(runner, 'observe',
                        lambda observer, deadline=None: observer.record())
    sleeps = []
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: sleeps.append(seconds))
    result = loop.run(steps=1, interval=4, round_limit=1)
    return loop, sleeps, result


def _waits(tmp_path):
    path = tmp_path / 'events.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and json.loads(line)['event'] == 'window_transition_wait']


def test_a_transition_is_paced_faster_than_a_page_wait(tmp_path, monkeypatch):
    # The pace travels on the result, so the loop's own pause is the 1 s poll and not a
    # second 4 s page wait on top of it.  Other pauses in the same run are the loop's
    # (its `_pause_between_steps` measures from the last input), so only the poll is
    # pinned here and `test_the_wait_it_notes_says_which_interval_it_used` pins the rest.
    _loop, sleeps, _result = _run(tmp_path, monkeypatch)
    # D128: the poll backs off, so the first pause is the short one and no poll may be
    # slower than the page interval the transition replaced.
    polls = [value for value in sleeps if value in (1.0, 2.0, 4.0)]
    assert polls and polls[0] == 2.0, sleeps          # the first poll is the short one
    assert max(sleeps) <= 4.0, sleeps                 # never slower than the page wait
    assert polls == sorted(polls), sleeps             # and it only ever backs off


def test_the_wait_it_notes_says_which_interval_it_used(tmp_path, monkeypatch):
    _loop, _sleeps, _result = _run(tmp_path, monkeypatch)
    rows = _waits(tmp_path)
    # D162: the row reports the pace this round actually took, so the backoff is
    # visible in the journal instead of a flat configured value.
    assert rows
    assert rows[0]['interval_s'] >= 1.0
    assert [row['interval_s'] for row in rows] == sorted(row['interval_s'] for row in rows)


def test_the_transition_ends_by_its_clock_not_by_its_rounds(tmp_path, monkeypatch):
    # The sleeps are monkeypatched out, so wall time barely moves and a wall-clock bound
    # can never be observed in this harness (41 rounds of 0.8 s real time). A fake clock
    # makes the assertion about the rule instead of about the machine: every monotonic
    # read costs 0.5 s, so a 5 s window is fifteen rounds, not a fixed count of 120.
    ticks = itertools.count()

    def clock():
        return next(ticks) * 0.5

    monkeypatch.setattr(runner.time, 'monotonic', clock)
    loop, sleeps, result = _run(tmp_path, monkeypatch, transition_seconds=5.0)
    waited = [row['waited'] for row in _waits(tmp_path)]
    assert waited and max(waited) < 5.0 + 1.0
    assert len(waited) <= 16
    assert len(sleeps) >= len(waited) - 1
    assert result.get('reason') != runner.PENDING_TRANSACTION_UNREADABLE


def test_the_poll_is_a_bounded_wait_of_its_own(tmp_path, monkeypatch):
    # It is a pace, not a page wait: the loop hands it to the next pause, so it has its
    # own bound rather than borrowing the page interval's.
    with pytest.raises(ValueError):
        runner.settings({'transition_interval': 0})
    with pytest.raises(ValueError):
        runner.settings({'transition_interval': 31})
    assert runner.settings({'transition_interval': 0.5}).transition_interval == 0.5


def test_the_transition_window_is_bounded_and_a_real_number(tmp_path, monkeypatch):
    assert runner.settings().transition_seconds == 90.0
    for bad in (0, 4.0, 601, True):
        with pytest.raises(ValueError):
            runner.settings({'transition_seconds': bad})
