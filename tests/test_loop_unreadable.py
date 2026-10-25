"""A page nobody can name never sends an input, and its pause grows.

The loop's own contract for an unreadable frame -- wait, do not act -- is only exercised
live, where a mistake costs a run.  These tests drive `MirrorRunner.step` over a scripted
observer, so the contract is pinned offline: the frame the loop cannot name produces a
wait, the wait backs off, and the first named page after the streak is the first input.
"""
import json

import maalimbus.runner as runner
from maalimbus.runner import MirrorRunner


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row) + '\n')


class _Script:
    """Hands out the pages in order, one per read."""

    def __init__(self, directory, pages):
        self.directory = directory
        self.pages = list(pages)
        self.reads = 0

    def observe(self, deadline=None):
        page = self.pages[min(self.reads, len(self.pages) - 1)]
        self.reads += 1
        return {'scene': page, 'image_sha256': 'sha-%d' % self.reads,
                'size': [1920, 1080], 'ocr': []}


def _loop(tmp_path, pages):
    device = runner.FakeDevice()
    loop = MirrorRunner(device, settings={'rounds': 1, 'interval': 0}, directory=tmp_path,
                        journal=_Journal(tmp_path))
    loop.observer = _Script(tmp_path, pages)
    return loop


def _events(tmp_path, name):
    rows = []
    path = tmp_path / 'events.jsonl'
    if not path.exists():
        return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get('event') == name:
                rows.append(row)
    return rows


def test_an_unreadable_page_never_sends_an_input(tmp_path):
    loop = _loop(tmp_path, ['UNKNOWN'])
    result = loop.step()
    assert result.get('waiting') is True
    assert loop.device.clicks == []
    waits = (_events(tmp_path, 'window_unknown_wait')
             + _events(tmp_path, 'window_transition_wait'))
    assert waits, 'an unreadable frame is waited on, not acted on'
    assert loop.state.get('unknown_since') or loop.state.get('transition_seen')


def test_the_pause_after_an_unreadable_page_grows(tmp_path):
    loop = _loop(tmp_path, ['UNKNOWN'])
    loop.state['last_named_page'] = 'DRIVE'
    pauses = []
    for _ in range(4):
        left = loop.state.pop('unknown_since', None)
        result = loop.step()
        pauses.append(round(float(result.get('pause') or 0.0), 2))
        if left is not None:
            loop.state['unknown_since'] = left
    assert pauses[0] > 0
    assert pauses[-1] >= pauses[0]


def test_the_transition_poll_ramps_while_the_page_stays_unreadable(tmp_path):
    loop = _loop(tmp_path, ['UNKNOWN'])
    intervals = []
    for _ in range(3):
        loop.step()
        rows = _events(tmp_path, 'window_transition_wait')
        if rows:
            intervals.append(round(float(rows[-1]['interval_s']), 2))
    assert intervals, 'an unreadable frame is polled, and the poll records its pace'
    assert intervals == sorted(intervals), 'the poll backs off rather than staying fixed'
    assert loop.device.clicks == []
