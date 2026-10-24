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
    loop, sleeps, _result = _run(tmp_path, monkeypatch)
    pacing = {seconds for seconds in sleeps if seconds}
    assert pacing == {runner.settings().unknown_interval}


def test_the_pause_is_shorter_than_the_read_it_precedes(tmp_path, monkeypatch):
    """A pause longer than the sample it precedes is pure latency."""
    loop, sleeps, _result = _run(tmp_path, monkeypatch)
    assert runner.settings().unknown_interval < 2.07


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
