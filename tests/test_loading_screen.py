"""A scene loader is a duration with a name, not an unreadable page (D120).

Live `evidence/runtime/packaged-mirror-20261024-122522` read the loader as UNKNOWN for
100 s, was charged 41 waits by the no-progress budget, and ended a healthy run with
`the_loop_waited_without_a_new_page`.  The page has no control to take; the only honest
instruments are its own name and a clock.
"""
import json
import pathlib

import pytest

from maalimbus import pages, runner, vision
from maalimbus.vision import Text

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME = ROOT / 'evidence/runtime/packaged-mirror-20261024-122522/frame-0050.json'
LOCALE = json.loads((ROOT / 'assets/resource/en/locale.json').read_text(encoding='utf-8'))


def _record(path=FRAME):
    if not path.exists():
        pytest.skip('the retained loader frame is not in this checkout')
    raw = json.loads(path.read_text(encoding='utf-8'))
    return raw, [Text(t['text'], tuple(t['box']), t['score']) for t in raw['ocr']]


def test_the_live_loader_frame_is_its_own_page():
    raw, records = _record()
    assert vision.classify(records, LOCALE, tuple(raw['size'])) == 'LOADING'


def test_the_loader_is_a_wait_page_with_no_control():
    assert pages.PAGES['LOADING'] == ('vision', 'wait')
    assert pages.kind_of(reason='the_game_is_loading_the_next_scene') == 'missing_control'
    assert pages.RECOVERY_BY_KIND['missing_control'] in pages.WAIT_ONLY_ACTIONS


def test_a_page_without_the_caption_is_not_a_loader():
    raw, records = _record()
    without = [item for item in records if 'LOAD' not in item.text.upper()]
    assert vision.classify(without, LOCALE, tuple(raw['size'])) != 'LOADING'


def test_the_caption_outside_its_band_is_not_a_loader():
    raw, _ = _record()
    moved = [Text('NOW LOADING.', (100, 100, 300, 130), 0.99)]
    assert vision.classify(moved, LOCALE, tuple(raw['size'])) != 'LOADING'


def test_the_window_answers_a_loader_with_its_own_reason():
    plan = __import__('maalimbus.window', fromlist=['x']).plan_step('LOADING')
    assert plan['action'] == 'record'
    assert plan['reason'] == 'the_game_is_loading_the_next_scene'


class _Clock:
    """A monotonic clock the test can move."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class _Journal:
    def __init__(self):
        self.rows = []

    def record(self, event, **fields):
        self.rows.append(dict(fields, event=event))


def _loop(journal=None):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.state = {'step': 1}
    loop.journal = journal
    loop.artifacts = {'steps': []}
    loop.last_event = None
    loop.decision_log = False
    loop.settings = runner.settings()
    loop.settings.submit_seconds = 180
    loop.settings.transition_interval = 0
    return loop


def test_a_loader_is_waited_on_within_its_clock(monkeypatch):
    clock = _Clock()
    loop = _loop(_Journal())
    monkeypatch.setattr(runner.time, 'monotonic', clock)
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    first = loop._loading_wait('LOADING', loop.settings)
    assert first.get('waiting') is True
    clock.now += 60.0
    second = loop._loading_wait('LOADING', loop.settings)
    assert second.get('waiting') is True
    assert loop.state['loading_since'] == 100.0


def test_a_loader_that_never_leaves_ends_with_its_own_name(monkeypatch):
    clock = _Clock()
    journal = _Journal()
    loop = _loop(journal)
    monkeypatch.setattr(runner.time, 'monotonic', clock)
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    loop._loading_wait('LOADING', loop.settings)
    clock.now += 200.0
    done = loop._loading_wait('LOADING', loop.settings)
    assert done.get('done') is True
    assert loop.state['session_ended'] == 'the_loading_screen_never_left'
    assert pages.kind_of(stopped_reason='the_loading_screen_never_left') == 'refused_by_policy'
    assert 'loading_never_left' in [row['event'] for row in journal.rows]
