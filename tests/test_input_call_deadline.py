"""A request that is never answered must not own the run (D88)."""

import threading
import time

import pytest

from maalimbus import jobs, runner


def test_an_answered_call_returns_its_value():
    box = jobs.call_with_a_deadline(lambda: 7, timeout=1.0)
    assert box == {'answered': True, 'value': 7, 'error': None}


def test_a_call_that_raises_is_reported_not_propagated():
    def boom():
        raise RuntimeError('Maa job failed')

    box = jobs.call_with_a_deadline(boom, timeout=1.0)
    assert box['answered'] is True
    assert isinstance(box['error'], RuntimeError)


def test_a_call_that_never_answers_is_abandoned_at_the_deadline():
    started = threading.Event()

    def hang():
        started.set()
        while True:
            time.sleep(0.01)

    began = time.monotonic()
    box = jobs.call_with_a_deadline(hang, timeout=0.2)
    assert box['answered'] is False
    assert box['value'] is None
    assert time.monotonic() - began < 2.0
    assert started.is_set()


def test_an_abandoned_call_cannot_keep_the_process_alive():
    from maalimbus import jobs as module

    worker = None
    box = module.call_with_a_deadline(lambda: time.sleep(0.5), timeout=0.05)
    assert box['answered'] is False
    for candidate in threading.enumerate():
        if candidate.name == 'maalimbus-call':
            worker = candidate
            break
    assert worker is None or worker.daemon


def _device_class():
    class Device(runner.MaaDevice):
        def __init__(self):
            self.controller = self
            self.tasker = None
            self.wait = None
            self.last_input_error = None
            self.route_suspect = False
            self.pipeline_inputs = 0
            self.inputs_abandoned = 0
            self.ended = False

        def _refuse_if_ended(self, what):
            return None

        def _refuse_binding_lost(self, what):
            return None

        def _limit(self, timeout):
            return None

    return Device


def test_an_unanswered_request_is_abandoned_and_the_carrier_tries_once(monkeypatch):
    """The failing case: `post_click` never returns, and the loop must not wait for it."""
    monkeypatch.setattr(runner, 'INPUT_CALL_SECONDS', 0.2)
    Device = _device_class()
    device = Device()
    carried = []

    def never():
        while True:
            time.sleep(0.01)

    def carrier(what, payload):
        carried.append((what, payload))
        return 'carried'

    device.send_through_a_task = carrier
    began = time.monotonic()
    assert device._send('click', never, ('click', 10, 20)) == 'carried'
    assert time.monotonic() - began < 3.0
    assert carried == [('click', ('click', 10, 20))]
    assert device.inputs_abandoned == 1
    assert device.route_suspect is True
    assert device.last_input_error == runner.ABANDONED_INPUT


def test_an_abandoned_request_without_a_payload_ends_by_name(monkeypatch):
    monkeypatch.setattr(runner, 'INPUT_CALL_SECONDS', 0.2)
    Device = _device_class()
    device = Device()

    def never():
        while True:
            time.sleep(0.01)

    with pytest.raises(runner.RouteLost) as caught:
        device._send('key', never, None)
    assert runner.ABANDONED_INPUT in str(caught.value)
    assert device.inputs_abandoned == 1


def test_a_refused_request_is_still_carried(monkeypatch):
    Device = _device_class()
    device = Device()

    def refuse():
        raise RuntimeError('controller not found [controller_id=]')

    device.send_through_a_task = lambda what, payload: 'carried'
    assert device._send('click', refuse, ('click', 1, 2)) == 'carried'
    assert device.route_suspect is False
    assert 'controller not found' in device.last_input_error


def test_a_non_controller_error_is_not_carried():
    Device = _device_class()
    device = Device()

    def broken():
        raise RuntimeError('something else entirely')

    with pytest.raises(RuntimeError, match='something else'):
        device._send('click', broken, ('click', 1, 2))
