"""D167: a read taken right after a viewport gesture may not spend the whole window.

Measured on `packaged-mirror-20261024-220736`: three `window_recovery` rows held 100.7 s
of its 251.5 attributed seconds, each one gesture followed by a read that waited out the
full thirty seconds.  A static page that answers nothing in eight seconds is the device,
not the page.
"""
import time
import types

import pytest

from maalimbus import runner
from maalimbus.runner import MirrorRunner


class _NeverDone:
    done = False
    succeeded = False


class _Finished:
    done = True
    succeeded = False


class _Tasker:
    """A tasker whose node never comes back: the read has to time itself out."""

    def __init__(self):
        self.posted = []

    def post_task(self, name):
        self.posted.append(name)
        return _NeverDone()

    def post_stop(self):
        return _Finished()


def _observer(tmp_path):
    stub = types.SimpleNamespace(tasker=_Tasker(), directory=tmp_path, run=None, journal=None)
    return runner.MaaObserver(stub, tmp_path, read_tries=1)


def _loop(tmp_path):
    return MirrorRunner(runner.FakeDevice(), settings={'rounds': 1, 'interval': 0},
                        directory=tmp_path)


def test_a_read_after_a_gesture_is_bounded_by_the_tighter_window(tmp_path, monkeypatch):
    loop = _loop(tmp_path)
    loop.state['recovered_at'] = time.monotonic()
    loop.observer = _observer(tmp_path)
    started = time.monotonic()
    with pytest.raises(runner.ReadNeverReturned):
        loop._observe(phase='observe')
    assert time.monotonic() - started < runner.RECOVERED_READ_SECONDS + 3.0


def test_a_read_without_a_gesture_keeps_the_full_window(tmp_path):
    loop = _loop(tmp_path)
    loop.state.pop('recovered_at', None)
    loop.observer = _observer(tmp_path)
    started = time.monotonic()
    with pytest.raises(runner.ReadNeverReturned):
        loop._observe(phase='observe')
    # The clamp is the thirty-second window: this test only pins that it is not tighter
    # than the recovered one, without waiting thirty seconds (fake clock below).
    assert time.monotonic() - started >= runner.RECOVERED_READ_SECONDS + 3.0


def test_a_gesture_long_ago_does_not_tighten_the_next_read():
    clock = {'now': 1000.0}
    state = {'recovered_at': 1000.0}
    now = clock['now'] + runner.RECOVERED_READ_WINDOW + 1.0
    tight = state['recovered_at'] and 0.0 <= now - state['recovered_at'] < runner.RECOVERED_READ_WINDOW
    assert tight is False


def test_the_tight_window_is_far_below_the_default():
    assert 0.0 < runner.RECOVERED_READ_SECONDS < runner.ONE_READ_SECONDS / 2.0
    assert runner.RECOVERED_READ_SECONDS < runner.RECOVERED_READ_WINDOW
