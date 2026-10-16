"""A loop that stops producing frames ends the process loudly instead of hanging.

Live run pi-20261015-191205 wedged inside one recognition call at 19:16:07: no new
frame, no event, no result and twelve silent minutes, until the app was closed by
hand. No gesture can recover a call that never returns, so the loop is watched from
outside it (see ``MirrorRunner._start_stall_watch``).
"""
import json
import time
from pathlib import Path

from maalimbus.runner import FakeDevice, MirrorRunner, stall_watchdog


def test_the_watch_ends_a_loop_that_stopped_producing_frames():
    acted = []
    stall_watchdog(lambda: time.monotonic() - 400.0, limit=300.0, rounds=1,
                   sleep=lambda seconds: None,
                   on_stall=lambda: acted.append('stalled'),
                   exit=lambda code: acted.append(('exit', code)))
    assert acted == ['stalled', ('exit', 4)], 'the wedged process ends itself'


def test_the_watch_leaves_a_loop_that_keeps_producing_frames_alone():
    acted = []
    stall_watchdog(lambda: time.monotonic(), limit=300.0, rounds=3,
                   sleep=lambda seconds: None,
                   on_stall=lambda: acted.append('stalled'),
                   exit=lambda code: acted.append(('exit', code)))
    assert acted == [], 'a fresh frame is a heartbeat, not a stall'


def test_the_wedge_is_recorded_in_the_runs_own_directory(tmp_path):
    runner = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'interval': 0},
                          directory=tmp_path)
    runner.artifacts['heartbeat'] = time.monotonic() - 301.0
    record = runner._record_stall(300.0)
    written = json.loads((tmp_path / 'agent-stall.json').read_text(encoding='utf-8'))
    assert written == record
    assert record['reason'] == 'the_run_stalled_without_a_new_frame'
    assert record['limit_seconds'] == 300.0 and record['heartbeat_age_seconds'] > 300


def test_an_explicit_zero_leaves_the_watch_off(tmp_path):
    runner = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'stall_seconds': 0},
                          directory=tmp_path)
    assert runner._start_stall_watch() is None
