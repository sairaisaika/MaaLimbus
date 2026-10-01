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
