from types import SimpleNamespace

import pytest

from maalimbus.jobs import wait_job, wait_task


class Clock:
    now = 0
    def read(self): return self.now
    def sleep(self, seconds): self.now += seconds


def test_pending_setup_job_has_finite_deadline_and_reports_failure():
    clock = Clock()
    pending = SimpleNamespace(done=False, succeeded=False)
    with pytest.raises(TimeoutError):
        wait_job(pending, timeout=10, deadline=2, clock=clock.read, sleep=clock.sleep)
    assert clock.now == 2
    with pytest.raises(RuntimeError):
        wait_job(SimpleNamespace(done=True,succeeded=False))


def test_task_timeout_stops_once_and_never_claims_clear():
    clock = Clock()
    pending = SimpleNamespace(done=False, succeeded=False)
    calls = []
    def stop():
        calls.append('stop')
        pending.done = True
        return SimpleNamespace(done=True,succeeded=True)
    result = wait_task(SimpleNamespace(post_stop=stop), pending, deadline=1,
                       clock=clock.read, sleep=clock.sleep)
    assert calls == ['stop']
    assert clock.now == 1
    assert result['timed_out'] and result['stop_confirmed']
    assert not result['verified_clear']


def test_unresponsive_stop_is_bounded_and_remains_unconfirmed():
    clock = Clock()
    pending = SimpleNamespace(done=False, succeeded=False)
    result = wait_task(SimpleNamespace(post_stop=lambda:pending), pending, deadline=1,
                       clock=clock.read, sleep=clock.sleep)
    assert clock.now == 6
    assert result['stop_error']
    assert not result['stop_confirmed'] and not result['verified_clear']


def test_interrupt_stops_before_returning_and_success_is_not_dungeon_clear():
    pending = SimpleNamespace(done=False, succeeded=False)
    def stop():
        pending.done = True
        return SimpleNamespace(done=True,succeeded=True)
    def interrupt(seconds): raise KeyboardInterrupt
    result = wait_task(SimpleNamespace(post_stop=stop), pending, deadline=10**12, sleep=interrupt)
    assert result['interrupted'] and result['stop_confirmed']
    succeeded = wait_task(None, SimpleNamespace(done=True,succeeded=True), deadline=0)
    assert succeeded['task_succeeded'] and not succeeded['verified_clear']


class _Job:
    def __init__(self, done=False, succeeded=False):
        self.done, self.succeeded = done, succeeded


class _Tasker:
    def __init__(self, stop_job):
        self._stop = stop_job

    def post_stop(self):
        return self._stop


def test_a_finished_task_says_completed():
    from maalimbus.jobs import wait_task
    out = wait_task(_Tasker(None), _Job(True, True), deadline=10.0)
    assert out['verdict'] == 'completed'


def test_a_respected_deadline_that_was_confirmed_says_stopped():
    from maalimbus.jobs import wait_task
    job = _Job(False, False)
    tasker = _Tasker(_Job(True, True))
    def fake_wait(target, **kw):
        job.done = True           # the stop landed
        return target
    import maalimbus.jobs as jobs
    original = jobs.wait_job
    jobs.wait_job = fake_wait
    try:
        out = wait_task(tasker, job, deadline=0.0)
    finally:
        jobs.wait_job = original
    assert out['verdict'] == 'stopped'


def test_a_stop_that_never_lands_is_named_not_hidden():
    import maalimbus.jobs as jobs
    out = jobs.wait_task(_Tasker(None), _Job(False, False), deadline=0.0,
                         clock=lambda: 0.0)
    assert out['verdict'] == 'the_controller_did_not_confirm_the_stop'
    assert out['stop_confirmed'] is False


class _Shot:
    def __init__(self, done, succeeded=True):
        self.done, self.succeeded = done, succeeded


class _Controller:
    def __init__(self, shots):
        self.shots = list(shots)
        self.stops = 0

    def post_screencap(self):
        return self.shots.pop(0)

    def post_stop(self):
        self.stops += 1
        return _Shot(True)


def test_a_normal_screen_comes_back_without_a_stop():
    from maalimbus.jobs import screencap
    ctl = _Controller([_Shot(True)])
    screencap(ctl, timeout=1)
    assert ctl.stops == 0


def test_a_timeout_drains_the_pending_capture_first():
    from maalimbus.jobs import ScreenshotNeverReturned, screencap
    ctl = _Controller([_Shot(False)])
    try:
        screencap(ctl, timeout=0.0, clock=lambda: 0.0)
    except ScreenshotNeverReturned:
        pass
    else:  # pragma: no cover
        raise AssertionError('a pending capture must be named, not swallowed')
    assert ctl.stops == 1, 'the pending request has to be drained before the next input'


class _ClickController:
    def __init__(self, click_done):
        self.click_done = click_done
        self.stops = 0

    def post_stop(self):
        self.stops += 1
        return _Shot(True)


def test_a_click_that_returns_is_not_treated_as_a_failure():
    from maalimbus.jobs import dispatch
    ctl = _ClickController(True)
    dispatch(ctl, _Shot(True), timeout=1)
    assert ctl.stops == 0


def test_a_click_that_never_returns_is_drained_and_named():
    from maalimbus.jobs import InputNeverReturned, dispatch
    ctl = _ClickController(False)
    try:
        dispatch(ctl, _Shot(False), timeout=0.0, clock=lambda: 0.0)
    except InputNeverReturned:
        pass
    else:  # pragma: no cover
        raise AssertionError('a pending click must be named')
    assert ctl.stops == 1, 'the pending click has to be drained'
