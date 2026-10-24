"""A rejected input is the only reliable signal that the controller route is gone.

D84 asked `tasker.running` before posting input.  `tools/probe_route.py` then showed a
screenshot answering in 0.05 s with `controller.id` unset and no task running, so no
local predicate can predict a rejected click -- and the predicate that was there would
have withheld input between every two reads.  D85 replaces the prediction with one
repair: post, and if the framework refuses with a controller error, bind again and
retry exactly once.
"""
import json
from pathlib import Path

import pytest

from maalimbus import pages, runner


class Job:
    def __init__(self, done=True, succeeded=True):
        self.done = done
        self.succeeded = succeeded


class Refusing:
    """A controller that refuses the first N inputs with a route error."""

    def __init__(self, refusals=1, message='controller not found [controller_id=""]'):
        self.refusals = refusals
        self.message = message
        self.clicks = []
        self.bindings = 0
        self.cached_image = None
        self.id = None

    def post_click(self, x, y):
        if self.refusals > 0:
            self.refusals -= 1
            raise RuntimeError(self.message)
        self.clicks.append((x, y))
        return Job()

    def post_connection(self):
        self.bindings += 1
        return Job()


def _device(controller):
    device = runner.MaaDevice.__new__(runner.MaaDevice)
    device.controller = controller
    device.ended = None
    device.binding_lost = None
    device.rebinds = 0
    device.last_input_error = None
    device.clicks = []
    device.deadline = None
    return device


def test_a_refused_click_binds_again_and_lands(monkeypatch):
    controller = Refusing(refusals=1)
    device = _device(controller)
    monkeypatch.setattr(device, '_wait', lambda job, timeout=10: job)
    device.click(100, 200)
    assert controller.clicks == [(100, 200)]
    assert controller.bindings == 1
    assert device.rebinds == 1
    assert 'controller not found' in device.last_input_error


def test_a_second_refusal_is_a_named_ending():
    controller = Refusing(refusals=2)
    device = _device(controller)
    device._wait = lambda job, timeout=10: job
    with pytest.raises(runner.RouteLost) as raised:
        device.click(1, 2)
    assert raised.value.reason == runner.ROUTE_LOST
    assert controller.clicks == []
    assert controller.bindings == 1


def test_a_working_controller_is_never_bound_again():
    controller = Refusing(refusals=0)
    device = _device(controller)
    device._wait = lambda job, timeout=10: job
    device.click(3, 4)
    assert controller.bindings == 0
    assert device.rebinds == 0


def test_an_unrelated_error_is_not_retried():
    controller = Refusing(refusals=1, message='post_click needs a point')
    device = _device(controller)
    device._wait = lambda job, timeout=10: job
    with pytest.raises(RuntimeError) as raised:
        device.click(5, 6)
    assert not isinstance(raised.value, runner.RouteLost)
    assert controller.bindings == 0


def test_the_ending_has_a_kind():
    assert pages.kind_of(reason=runner.ROUTE_LOST) == 'refused_by_policy'
    assert runner.ROUTE_LOST in pages.STOP_KINDS


def test_the_walk_names_the_reason_and_the_repairs():
    """The ending is written where the loop can still say what happened."""
    source = __import__('inspect').getsource(runner.MirrorRunner._walk)
    handler = source[source.index('except RouteLost as error:'):]
    handler = handler[:handler.index('except (RuntimeError, OSError)')]
    assert "self.note('input_withheld'" in handler
    assert 'self._end_session(error.reason' in handler
    assert 'rebinds=' in handler
