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
    # The record now names *what* the stillness is instead of only that time passed.
    assert record['reason'] == 'the_page_is_frozen_and_answered_nothing'
    assert record['stillness_kind'] == 'frozen_page'
    assert record['stillness_action'] == 'stop'
    assert record['limit_seconds'] == 300.0 and record['heartbeat_age_seconds'] > 300


def test_an_explicit_zero_leaves_the_watch_off(tmp_path):
    runner = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'stall_seconds': 0},
                          directory=tmp_path)
    assert runner._start_stall_watch() is None


class _Journal:
    """The smallest journal the watch needs: one JSON line per event."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def record(self, event, **details):
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'event': event, **details}, ensure_ascii=False))
            handle.write('\n')


def _watched_runner(tmp_path, **settings):
    return MirrorRunner(FakeDevice(), settings={'rounds': 1, 'interval': 0, **settings},
                        directory=tmp_path, journal=_Journal(tmp_path))


def _events(tmp_path, name):
    path = tmp_path / 'events.jsonl'
    if not path.exists():
        return []
    return [row for row in (json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
                            if line.strip())
            if row.get('event') == name]


def test_the_progress_watch_writes_the_same_canonical_stop(tmp_path):
    """Both watches end a run; neither may leave it silent.

    Measured on `evidence/runtime` 2026-10-23: 16 of 51 runs without a stop ended on
    `window_no_progress` (`packaged-mirror-20261023-153338` … `-163257`). Only the
    frame watch wrote `mirror_loop_stopped`, so the journal of those runs said what
    went quiet and never said the run had ended.
    """
    runner = _watched_runner(tmp_path)
    runner.state['step'] = 4
    runner.state['page'] = 'RESUME_DIALOG'
    runner.last_event = 'window_intent'
    runner.artifacts['event_heartbeat'] = time.monotonic() - 901.0
    runner.artifacts['reading'] = {'phase': 'settle', 'page': 'RESUME_DIALOG',
                                   'since': time.monotonic() - 380.0,
                                   'limit_seconds': 30.0}
    record = runner._record_no_progress(900.0)
    kinds = [row.get('event') for row in
             (json.loads(line) for line in
              (tmp_path / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())]
    assert kinds == ['window_no_progress', 'mirror_loop_stopped'], kinds
    stopped, = _events(tmp_path, 'mirror_loop_stopped')
    assert stopped['stop_path'] == 'no_progress_watchdog'
    assert stopped['reason'] == record['reason']
    assert stopped['page'] == 'RESUME_DIALOG' and stopped['step'] == 4
    # The silence belonged to a call, and only memory knew which one: the ending has
    # to name it, or the next reader re-reads the whole run to learn it.
    assert stopped['in_flight_phase'] == 'settle' and stopped['in_flight'] is True
    assert stopped['in_flight_seconds'] > 300
    written = json.loads((tmp_path / 'agent-no-progress.json').read_text(encoding='utf-8'))
    assert written['in_flight']['phase'] == 'settle'


def test_a_read_that_finished_is_not_reported_as_a_wedge(tmp_path):
    """Counter-example: a slow read that *did* return is not an in-flight call."""
    runner = _watched_runner(tmp_path)
    runner.artifacts['event_heartbeat'] = time.monotonic() - 901.0
    runner.artifacts['reading'] = {'phase': 'settle', 'page': 'MAP',
                                   'since': time.monotonic() - 380.0,
                                   'limit_seconds': 30.0, 'lasted_seconds': 29.0}
    record = runner._record_no_progress(900.0)
    assert record['in_flight']['phase'] == 'settle'
    assert 'in_flight' not in record['in_flight']
    stopped, = _events(tmp_path, 'mirror_loop_stopped')
    assert stopped['in_flight'] is False


def test_the_frame_watch_names_the_finished_read_too(tmp_path):
    """The stall record carries the same breadcrumb, so both endings read alike."""
    runner = _watched_runner(tmp_path)
    runner.artifacts['heartbeat'] = time.monotonic() - 301.0
    runner.artifacts['reading'] = {'phase': 'settle', 'page': 'MAP',
                                   'since': time.monotonic() - 301.0,
                                   'limit_seconds': 30.0}
    runner._record_stall(300.0)
    stopped, = _events(tmp_path, 'mirror_loop_stopped')
    assert stopped['stop_path'] == 'stall_watchdog'
    assert stopped['in_flight_phase'] == 'settle' and stopped['in_flight'] is True


def test_a_watch_is_never_longer_than_the_run_it_protects():
    """A watchdog may not outlive its run: 450 s budget, 1058 s run, 905 s block
    (`packaged-mirror-20261023-124006`, gap `window_intent -> window_no_progress`)."""
    from maalimbus.jobs import bounded_limit
    now = time.monotonic()
    assert bounded_limit(900.0, now + 100.0) <= 100.0
    assert bounded_limit(900.0, None) == 900.0
    assert bounded_limit(900.0, now + 5000.0) == 900.0


def test_a_screen_that_answers_a_reread_is_not_pronounced_frozen():
    """The probe is the only honest source for `probe_changed`; an alive page waits."""
    from maalimbus.runner import stall_watchdog
    seen = []
    exits = []
    ready = iter([0.0, 999.0, 999.0])

    def heartbeat():
        return next(ready, 999.0)

    def on_stall(probe_changed=None):
        seen.append(probe_changed)
        return {'stillness_action': 'keep_waiting', 'stillness_kind': 'the_page_still_answers_a_reread'}

    stall_watchdog(heartbeat, limit=1.0, on_stall=on_stall, every=0.0, rounds=2,
                   probe=lambda: True, sleep=lambda _s: None, exit=exits.append)
    assert seen == [True, True]      # the probe result reached the classifier
    assert exits == []               # and no exit was requested inside the bound


def test_the_third_wait_still_ends_the_process():
    from maalimbus.runner import stall_watchdog
    exits = []
    stall_watchdog(lambda: 0.0, limit=1.0,
                   on_stall=lambda probe_changed=None: {'stillness_action': 'keep_waiting'},
                   every=0.0, rounds=4, probe=lambda: True,
                   sleep=lambda _s: None, exit=exits.append)
    # The real `exit` is os._exit and terminates; this stub records every request, so
    # the assertion is about the first one and about the bound being reached at all.
    assert exits and exits[0] == 4


def test_a_watch_whose_run_is_over_never_ends_anything():
    """A watch outlives the run it protects; it may not outlive it *and* act.

    Measured 2026-10-23: `pytest tests/test_agent_loop.py` passed 18 tests in 5.7 s,
    returned 0, and the process was then killed by `os._exit(4)` from a progress
    watch that had been started by a run already finished -- twice, with no summary
    and no failed test to blame. `exit(4)` ends a *process*, and a process can hold
    several runs in sequence, so the only honest ending a retired watch may write is
    none.
    """
    acted, exits, slept = [], [], []
    looked = stall_watchdog(lambda: 0.0, limit=1.0, every=0.0, rounds=5,
                            on_stall=lambda **kw: acted.append('stalled'),
                            sleep=slept.append, exit=exits.append,
                            alive=lambda: False)
    assert looked == 0 and slept == []      # it never even waited
    assert acted == [] and exits == []      # and it wrote nothing


def test_a_watch_retires_between_two_waits():
    """The run can end while the watch sleeps; that check must exist too."""
    acted, exits = [], []
    alive = iter([True, False])
    stall_watchdog(lambda: 0.0, limit=1.0, every=0.0, rounds=5,
                   on_stall=lambda **kw: acted.append('stalled'),
                   sleep=lambda _s: None, exit=exits.append,
                   alive=lambda: next(alive, False))
    assert acted == [] and exits == []
    assert next(alive, False) is False


def test_the_loop_retires_its_watches_when_it_returns(tmp_path):
    """`run()` clears the token in a `finally`, so a finished run leaves no live watch."""
    runner = _watched_runner(tmp_path, stall_seconds=0.05, progress_seconds=0)
    runner.run(steps=1, interval=0, round_limit=0)
    assert runner._watch_live.is_set() is False, 'a finished run leaves no armed watch'
    # A second call re-arms it: the runner may be walked again by its caller.
    runner2 = _watched_runner(tmp_path, stall_seconds=0.05, progress_seconds=0)
    runner2._start_stall_watch()
    assert runner2._watch_live.is_set() is True
    runner2._retire_watches()
    assert runner2._watch_live.is_set() is False

