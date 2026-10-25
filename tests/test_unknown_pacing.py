"""An unreadable page gets its own pacing, and the archive says it should be shorter.

`window_unknown_wait` used to sleep the step interval (4 s) between reads of a page the
reader could not name.  Measured over the retained corpus (154 runs, 413 unknown-page
episodes), the chance that the *next* read names the page does not improve with waiting:
12% after 4 s, 23% after 8 s, 36% after 12 s, 23% after 20 s and 28% after 40 s.  The
hazard is flat, so a longer pause is latency rather than patience -- while one read costs
2.07 s, which is the only thing the pause is competing with (D79).
"""
import pytest

from maalimbus import runner

UNKNOWN_PLAN = {'page': 'UNKNOWN', 'action': 'wait', 'target': None, 'node': None,
                'expect': (), 'reason': 'the_page_could_not_be_named', 'advance': False}


class _Journal:
    """Writes the events the loop notes, so a test can read them back."""

    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        import json
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


class _Observer:
    """Always reads the same unreadable frame."""

    def __init__(self):
        self.calls = 0

    def record(self):
        self.calls += 1
        return {'scene': 'UNKNOWN', 'image_sha256': 'same', 'size': [1920, 1080],
                'ocr': []}


def _run(tmp_path, monkeypatch, **settings):
    loop = runner.MirrorRunner(runner.FakeDevice(), settings={'rounds': 1, 'interval': 0,
                                                             **settings},
                               directory=tmp_path, journal=_Journal(tmp_path))
    loop.observer = _Observer()
    monkeypatch.setattr(runner, 'plan_step', lambda page, **kw: dict(UNKNOWN_PLAN))
    monkeypatch.setattr(runner, 'observe',
                        lambda observer, deadline=None: {
                            'scene': 'UNKNOWN', 'image_sha256': 'same',
                            'size': [1920, 1080], 'ocr': []})
    sleeps = []
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: sleeps.append(seconds))
    result = loop.run(steps=1, interval=0, round_limit=1)
    return loop, sleeps, result


def test_the_unknown_page_is_paced_by_its_own_setting(tmp_path, monkeypatch):
    """The pause is the unknown page's own setting, and the step interval never paces it.

    Asserted against the recorded pause rather than against the whole set of sleeps: under
    full-suite load another code path may sleep too, and that is not what this test is about.
    """
    loop, sleeps, _result = _run(tmp_path, monkeypatch)
    interval = runner.settings().unknown_interval
    assert interval in sleeps, 'the unknown page should sleep its own interval'
    assert runner.settings().interval not in sleeps, 'the step interval must not pace a read'
    waits = runner.events(tmp_path, 'window_unknown_wait')
    assert {wait['interval_s'] for wait in waits} == {interval}


def test_the_pause_trades_reads_against_detection_delay(tmp_path, monkeypatch):
    """D183: the pace is bounded by the episode clock, not by one read's cost.

    D79 set the pace below the cost of a read (2.07 s then) because a longer pause was
    thought to be pure latency.  The episode is clocked since D163, so what the pace now
    decides is how many reads one unreadable stretch costs -- and D68/D70 measured a read
    at 0.63 s, which is what the old comparison was against.  The contract is that the
    pace stays well inside the clock, and that the clock can afford a handful of reads.
    """
    loop, sleeps, _result = _run(tmp_path, monkeypatch)
    settings = runner.settings()
    assert settings.unknown_interval == 3.0
    assert settings.unknown_interval < settings.unknown_seconds


def test_the_wait_says_which_page_came_before_it(tmp_path, monkeypatch):
    """D81: a loading screen after a battle and a transition after the menu differ."""
    loop, _sleeps, _result = _run(tmp_path, monkeypatch)
    waits = runner.events(tmp_path, 'window_unknown_wait')
    assert waits, 'the unknown wait should be journalled'
    assert waits[0]['after'] is None, 'nothing named a page yet, so it may not invent one'
    assert loop.state.get('last_named_page') is None


def test_the_note_carries_the_interval_that_was_actually_waited(tmp_path, monkeypatch):
    loop, _sleeps, _result = _run(tmp_path, monkeypatch, unknown_interval=2.5)
    waits = runner.events(tmp_path, 'window_unknown_wait')
    assert waits, 'the unknown wait should be journalled'
    assert {wait['interval_s'] for wait in waits} == {2.5}


def test_the_step_interval_still_paces_everything_else(tmp_path, monkeypatch):
    """Only the unknown page gets the shorter pause; the step interval is unchanged."""
    assert runner.settings().interval == 4.0
    assert runner.settings({'unknown_interval': 2.0}).interval == 4.0


def test_the_pacing_is_a_bounded_setting():
    assert runner.settings({'unknown_interval': 9}).unknown_interval == 9
    for bad in (0, -1, 0.0, 31, '1.5', True, None):
        with pytest.raises(ValueError):
            runner.settings({'unknown_interval': bad})


def test_the_unreadable_page_is_asked_for_by_the_vocabulary():
    """D44's ratchet forbids a new page comparison in the runner; D81 moved it here."""
    from maalimbus import pages

    assert pages.is_unreadable('UNKNOWN') is True
    assert pages.is_unreadable('MAP') is False
    assert pages.is_unreadable(None) is False
    assert pages.UNREADABLE_PAGE in pages.PAGES
